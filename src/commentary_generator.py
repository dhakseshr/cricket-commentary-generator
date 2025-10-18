import google.generativeai as genai
import google.api_core.exceptions # For specific retry handling
import os
import json
import time
from src.utils import load_api_keys

# --- Configuration ---
API_KEYS = load_api_keys()
model = None
# Use Flash for cost/speed, switch to 'gemini-1.5-pro-latest' if higher quality needed
GEMINI_MODEL_NAME = 'models/gemini-2.5-flash-lite'

# Configure Gemini Client (handle potential errors)
if API_KEYS.get("gemini"):
    try:
        genai.configure(api_key=API_KEYS["gemini"])
        # Set up the model configuration
        generation_config = {
            "temperature": 0.75, # Slightly more creative
            "top_p": 0.95,
            "top_k": 40, # Adjusted top_k
            "max_output_tokens": 2048, # Max length for JSON response
            "response_mime_type": "application/json", # Crucial for JSON output
        }
        safety_settings = [ # Standard safety blocks
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL_NAME,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        print(f"Gemini API configured successfully with model: {GEMINI_MODEL_NAME}")
    except Exception as e:
        print(f"ERROR: Failed to configure Gemini API: {e}")
        print("Please ensure your GEMINI_API_KEY is correct and valid.")
else:
    print("WARNING: GEMINI_API_KEY not found in .env file. Commentary generation will use placeholders.")

# --- Helper to parse JSON (less critical with mime_type but good fallback) ---
def parse_llm_json_response(response_text):
    """Attempts to parse JSON from the LLM response text."""
    try:
        # Gemini 1.5 with mime_type should provide clean JSON, but check anyway
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON from LLM response: {e}")
        print(f"LLM Response Text Snippet:\n{response_text[:500]}...") # Log beginning of text
        # Attempt to find JSON within markdown fences as a fallback
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                print("Found JSON within markdown fences, attempting to parse fallback.")
                return json.loads(json_match.group(1))
        except Exception:
            pass # Ignore errors during fallback parsing attempt
        return None # Return None if primary and fallback parsing fail
    except Exception as e:
        print(f"Unexpected Python error parsing LLM JSON response: {e}")
        return None

# --- Main Analysis and Generation Function ---
def analyze_inning_and_generate_scripts(inning_llm_data, match_summary, inning_number, num_highlights=3, max_retries=3):
    """
    Uses Gemini to analyze inning data, identify highlights, and generate commentary.
    Handles retries for rate limits and potential API errors. Returns structured JSON.
    """
    if not model:
        print("LLM not configured, cannot analyze inning.")
        return {"events": [{"ball": f"{inning_number}.placeholder", "description": "Placeholder event", "commentary": "Placeholder commentary - LLM not configured."}]}

    team = inning_llm_data.split('\n')[0].split(': ')[-1].split(' ')[0] # Robust team extraction

    prompt = f"""
    Analyze the following cricket inning data for {team} (Inning {inning_number}).
    Match Context: {match_summary}

    Ball-by-Ball Data (condensed format: B over.ball: bowler to batter, runs scored (total); Extras; WICKET! details):
    {inning_llm_data}

    Your task is to act as an expert cricket commentator and analyst:
    1. Identify the top {num_highlights} most significant or exciting moments in this inning based ONLY on the provided ball-by-ball data. Focus on wickets (especially key players), bursts of boundaries (multiple 4s/6s in quick succession), potential turning points, or notable individual performances visible in the sequence. Prioritize impact and excitement.
    2. For EACH of these {num_highlights} moments, write a brief, exciting, and natural-sounding commentary script (strictly 1-2 sentences, roughly 25-40 words per script). The tone should be engaging for a video highlights package.
    3. Return your analysis STRICTLY as a valid JSON object matching this exact structure:
       {{
         "events": [
           {{
             "ball": "over.ball_number",
             "description": "Brief description of why this moment is significant (max 15 words)",
             "commentary": "Your generated commentary script for this specific moment."
           }}
           // ... (repeat for each of the {num_highlights} identified moments)
         ]
       }}
    Ensure the "ball" field correctly corresponds to the moment described. Only output the JSON structure. Use double quotes for all keys and string values.
    """

    print(f"Sending analysis prompt for Inning {inning_number} to Gemini {GEMINI_MODEL_NAME}...")

    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(prompt)

            # Check for blocks or empty responses
            if not response.candidates or not response.candidates[0].content.parts:
                block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown reason (empty response)'
                print(f"Warning: Prompt blocked or empty response from Gemini for Inning {inning_number}. Reason: {block_reason}")
                # Don't retry on safety blocks, just return empty
                return {"events": []}

            llm_response_text = response.text
            parsed_json = parse_llm_json_response(llm_response_text)

            if parsed_json and "events" in parsed_json and isinstance(parsed_json["events"], list):
                # Basic validation
                if all("ball" in evt and "description" in evt and "commentary" in evt for evt in parsed_json["events"]):
                    print(f"Successfully received and parsed {len(parsed_json['events'])} events from LLM for Inning {inning_number}.")
                    return parsed_json
                else:
                    print(f"Error: LLM JSON response for Inning {inning_number} has missing keys in events (Attempt {attempt+1}/{max_retries+1}). Response:\n{llm_response_text[:500]}")
                    # Retry on malformed JSON structure
            else:
                print(f"Error: LLM response for Inning {inning_number} was not valid JSON or parsing failed (Attempt {attempt+1}/{max_retries+1}). Response:\n{llm_response_text[:500]}")
                # Retry on parsing failure

        except google.api_core.exceptions.ResourceExhausted as e: # Specific error for rate limiting
            wait_time = (2 ** attempt) + (time.time() % 1) # Exponential backoff with jitter
            print(f"Rate limit exceeded (429) for Gemini Inning {inning_number} (Attempt {attempt+1}/{max_retries+1}). Waiting {wait_time:.1f}s. Error: {e}")
            if attempt == max_retries: return {"events": []} # Give up after last retry
            time.sleep(wait_time)
            continue # Go to next attempt

        except Exception as e:
            print(f"Error during Gemini analysis call for Inning {inning_number} (Attempt {attempt+1}/{max_retries+1}): {e}")
            if attempt == max_retries: return {"events": []} # Give up after last retry
            wait_time = (2 ** attempt) + (time.time() % 1)
            time.sleep(wait_time) # Wait before retrying on other errors too
            continue

        # If we got here due to parsing/validation failure, wait before retrying
        if attempt < max_retries:
             wait_time = (2 ** attempt) + (time.time() % 1)
             print(f"Retrying Gemini call for Inning {inning_number} due to response issue in {wait_time:.1f}s...")
             time.sleep(wait_time)

    print(f"Failed to get valid analysis from Gemini for Inning {inning_number} after {max_retries+1} attempts.")
    return {"events": []} # Return empty list after all retries fail


# --- Functions for Intro/Outro ---
def generate_simple_text(prompt, purpose="text generation", max_retries=2):
    """Generates simple text using a basic text model config, with retries."""
    if not model: return f"Placeholder for {purpose}: LLM not configured."

    # Use a simpler config for plain text generation if needed, or reuse main model
    # For simplicity, reuse main model but expect text (won't use JSON mime type here)
    text_model = genai.GenerativeModel(GEMINI_MODEL_NAME) # Re-init without JSON mime type? Or just parse text

    for attempt in range(max_retries + 1):
        try:
            # print(f"Sending simple prompt for {purpose}...") # Debug
            response = text_model.generate_content(prompt) # Use default safety settings? Add if needed.

            if not response.parts:
                block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown (empty)'
                print(f"Warning: Prompt blocked or empty response for {purpose}. Reason: {block_reason}")
                return f"Placeholder for {purpose} (Blocked/Empty Response)"

            result_text = response.text.strip()
            if result_text:
                return result_text
            else: # Empty string received
                 print(f"Warning: Received empty text response for {purpose} (Attempt {attempt+1}).")
                 if attempt == max_retries: return f"Placeholder for {purpose} (Empty Response)"


        except google.api_core.exceptions.ResourceExhausted as e:
            wait_time = (2 ** attempt) + (time.time() % 1)
            print(f"Rate limit exceeded (429) for Gemini {purpose} (Attempt {attempt+1}). Waiting {wait_time:.1f}s.")
            if attempt == max_retries: return f"Placeholder for {purpose} (Rate Limit)"
            time.sleep(wait_time)

        except Exception as e:
            print(f"Error generating {purpose} with Gemini (Attempt {attempt+1}): {e}")
            if attempt == max_retries: return f"Placeholder for {purpose} (API Error)"
            wait_time = (2 ** attempt) + (time.time() % 1)
            time.sleep(wait_time)

    return f"Placeholder for {purpose} (Failed Retries)"


def create_intro_script(match_summary):
    prompt = f"""
    Generate a short, enthusiastic opening commentary (around 30-50 words) suitable for starting a video highlights package, based on this cricket match summary. Output only the commentary text.

    Match Summary: {match_summary}

    Opening Commentary:
    """
    return generate_simple_text(prompt, purpose="intro script")

def create_summary_commentary(match_summary):
     prompt = f"""
     Generate a brief concluding commentary (2-3 sentences, around 40-60 words) suitable for ending a video highlights package, summarizing the result of this cricket match. Output only the commentary text.

     Match Summary: {match_summary}

     Concluding Commentary:
     """
     return generate_simple_text(prompt, purpose="summary script")