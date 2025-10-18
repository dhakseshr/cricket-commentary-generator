import requests
import time
import os
import uuid
import json # Added for potential JSON parsing errors
from src.utils import load_api_keys, ensure_dir

# --- Configuration ---
API_KEYS = load_api_keys()
HEYGEN_API_KEY = API_KEYS.get("heygen")
# V2 for generation, but V1 for status based on provided docs
HEYGEN_V2_API_URL = "https://api.heygen.com/v2"
HEYGEN_V1_API_URL = "https://api.heygen.com/v1" # <--- Added V1 URL
REQUEST_TIMEOUT = 30 # Timeout for API requests (seconds)
DOWNLOAD_TIMEOUT = 300 # Timeout for downloading video file (seconds)

# --- Functions ---

def request_avatar_video(text, avatar_id, voice_id, max_retries=2):
    """Sends text to HeyGen API V2 to generate an avatar video, with retries."""
    if not HEYGEN_API_KEY:
        print("ERROR: HeyGen API Key not configured in .env file.")
        return None
    # Basic check for placeholder IDs
    if not avatar_id or not voice_id or avatar_id.startswith("your_") or voice_id.startswith("your_") or "PLACEHOLDER" in avatar_id or "PLACEHOLDER" in voice_id:
        print(f"ERROR: Invalid HeyGen Avatar ID ('{avatar_id}') or Voice ID ('{voice_id}') provided. Check .env file or arguments.")
        return None


    headers = {
        # Confirmed from docs: Use X-Api-Key for V2 Authentication
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }
    # Payload structure based on V2 Text-to-Speech example
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal", # Adjust style: "normal", "circle", "closeup"
                },
                "voice": {
                    "type": "text",
                    "input_text": text, # V2 uses 'input_text'
                    "voice_id": voice_id
                    # "speed": 1.0 # Optional speed adjustment
                }
                # Optional background:
                # "background": { "type": "color", "value": "#FFFFFF" },
            }
        ],
        "test": False, # Set to False for actual credit usage
        "dimension": { # Use dimension for V2 TTS
             "width": 1280,
             "height": 720
         }
    }
    generate_url = f"{HEYGEN_V2_API_URL}/video/generate" # Correct V2 endpoint
    print(f"  Requesting video generation (POST {generate_url})...")

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(generate_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            print(f"    -> HeyGen generate request status: {response.status_code} (Attempt {attempt+1})")

            # Handle Rate Limiting (429)
            if response.status_code == 429:
                wait_time = (2 ** attempt) * 2 + (time.time() % 1) # Exponential backoff + jitter
                print(f"    Rate limit hit (429). Waiting {wait_time:.1f}s before retry...")
                if attempt == max_retries:
                    print("    Max retries reached for rate limit.")
                    return None
                time.sleep(wait_time)
                continue # Retry

            response.raise_for_status() # Raise HTTPError for other bad responses (4xx, 5xx)
            data = response.json()

            # Check V2 API error structure
            # Updated check based on user-provided success example (no 'code' field needed)
            if data.get('error'):
                error_msg = data.get('message', str(data.get('error', 'Unknown API Error')))
                print(f"    ❌ HeyGen API Error on generate: {error_msg}")
                # Handle specific errors if possible (e.g., concurrency)
                if "concurrency limit" in error_msg.lower():
                     print("    -> Concurrency limit reached. Waiting longer...")
                     if attempt < 1: # Retry concurrency once
                          time.sleep(30 + (time.time() % 5))
                          continue
                     else: return None
                return None

            video_id = data.get('data', {}).get('video_id')
            if not video_id:
                print("    ❌ ERROR: video_id not found in successful HeyGen response.")
                print("      Response snippet:", str(data)[:500])
                return None

            print(f"    Successfully submitted job. Video ID: {video_id}")
            return video_id # Success

        except requests.exceptions.Timeout:
            print(f"    ❌ Error: Timeout occurred requesting HeyGen generation (Attempt {attempt+1}).")
            if attempt == max_retries: return None
            time.sleep(3 * (attempt + 1)) # Wait before retrying timeout
        except requests.exceptions.RequestException as e:
            print(f"    ❌ Error requesting HeyGen video generation (Attempt {attempt+1}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                 print(f"      Response status: {e.response.status_code}")
                 print(f"      Response body: {e.response.text[:500]}...")
            if attempt == max_retries: return None
            wait_time = (2 ** attempt) * 2 + (time.time() % 1) # Longer wait for network issues
            print(f"      Waiting {wait_time:.1f}s before retry...")
            time.sleep(wait_time)
        except json.JSONDecodeError as json_err:
             print(f"    ❌ Error decoding HeyGen JSON response (Attempt {attempt+1}): {json_err}")
             # Check if response exists before trying to access .text
             resp_text = response.text[:500] if 'response' in locals() and hasattr(response, 'text') else 'N/A'
             print(f"      Response text: {resp_text}")
             if attempt == max_retries: return None
             time.sleep(2 * (attempt + 1)) # Wait before retry on decode error
        except Exception as e:
             print(f"    ❌ Unexpected Python error during HeyGen request (Attempt {attempt+1}): {e}")
             if attempt == max_retries: return None
             time.sleep(2 * (attempt + 1))

    print(f"  ❌ Failed video generation request after {max_retries+1} attempts.")
    return None

def check_video_status(video_id, max_retries=3):
    """Checks the status using the V1 ENDPOINT specified in docs, with retries."""
    if not video_id or not HEYGEN_API_KEY:
        print("  Error: Cannot check status without video_id or API key.")
        return None, None, "Missing video_id or API key"

    headers = {"X-Api-Key": HEYGEN_API_KEY} # V1 uses X-Api-Key
    # --- *** CORRECTED V1 STATUS ENDPOINT *** ---
    status_url = f"{HEYGEN_V1_API_URL}/video_status.get"
    params = {'video_id': video_id}
    # --- ****************************************** ---

    for attempt in range(max_retries + 1):
        try:
            # print(f"  Checking status: GET {status_url} with params {params} (Attempt {attempt+1})") # More verbose debug
            response = requests.get(status_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            # print(f"    -> HeyGen status check response: {response.status_code}") # Verbose

            if response.status_code == 429:
                wait_time = (2 ** attempt) + (time.time() % 1)
                print(f"    Rate limit hit (429) checking status. Waiting {wait_time:.1f}s...")
                if attempt == max_retries: return "error", None, "Max retries for rate limit"
                time.sleep(wait_time)
                continue

            # V1 returns 404 if ID invalid
            if response.status_code == 404:
                 print(f"    ❌ Error: Video ID {video_id} not found on HeyGen (404). Check if ID is correct or job expired.")
                 return "failed", None, f"Video ID not found (404)"

            response.raise_for_status() # Raise for other 4xx/5xx errors

            data = response.json()
            # Check V1 response structure (usually has 'code' and 'data')
            if data.get('code') == 100: # Assuming 100 means success for V1 status calls
                 status_data = data.get('data', {})
                 status = status_data.get('status')
                 # V1 typically provides video_url upon completion
                 video_url = status_data.get('video_url')
                 # Check for V1 error field (might just be 'error')
                 error_message = status_data.get('error')

                 return status, video_url, error_message
            else:
                 # V1 API reported an error in the body
                 error_msg = data.get('message', 'Unknown V1 API Error')
                 print(f"    ❌ HeyGen V1 API Error checking status: {error_msg}")
                 # Decide if retryable? Assume not for now.
                 return "failed", None, error_msg


        except requests.exceptions.Timeout:
            print(f"    Warning: Timeout checking status for video {video_id} (Attempt {attempt+1}).")
            if attempt == max_retries: return "error", None, "Timeout after max retries"
            time.sleep(3 * (attempt + 1))
        except requests.exceptions.RequestException as e:
            print(f"    Error checking HeyGen status for {video_id} (Attempt {attempt+1}): {e}")
            if attempt == max_retries: return "error", None, f"HTTP Error after retries: {str(e)[:100]}"
            wait_time = (2 ** attempt) * 2 + (time.time() % 1)
            print(f"    Waiting {wait_time:.1f}s before retry...")
            time.sleep(wait_time)
        except json.JSONDecodeError as json_err:
             print(f"    ❌ Error decoding HeyGen V1 status JSON response (Attempt {attempt+1}): {json_err}")
             resp_text = response.text[:500] if 'response' in locals() and hasattr(response, 'text') else 'N/A'
             print(f"      Response text: {resp_text}")
             if attempt == max_retries: return "error", None, "JSON decode error"
             time.sleep(2 * (attempt + 1))
        except Exception as e:
             print(f"    ❌ Unexpected Python error during HeyGen status check (Attempt {attempt+1}): {e}")
             if attempt == max_retries: return "error", None, f"Unexpected error after retries: {str(e)[:100]}"
             time.sleep(2 * (attempt + 1))

    print(f"  ❌ Failed status check for {video_id} after all retries.")
    return "error", None, "Failed status check after all retries"

# --- download_video function remains the same ---
def download_video(video_url, output_path):
    """Downloads the generated video from the URL with error checks."""
    if not video_url or not video_url.startswith('http'):
        print(f"  ❌ ERROR: Invalid video URL provided for download: '{str(video_url)[:100]}...'")
        return False
    try:
        print(f"  Attempting to download video...") # Avoid logging sensitive URLs
        response = requests.get(video_url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        print(f"    -> Download request status: {response.status_code}")
        response.raise_for_status()

        content_type = response.headers.get('content-type', '').lower()
        if not any(ct in content_type for ct in ['video', 'octet-stream']):
            print(f"    ❌ ERROR: Unexpected content type '{content_type}' received. Expected video.")
            try:
                error_detail = response.content[:1024].decode('utf-8', errors='ignore')
                print(f"      Response start: {error_detail}")
            except Exception: pass
            return False

        file_size = int(response.headers.get('content-length', 0))
        size_str = f"{file_size / (1024*1024):.2f} MB" if file_size > 0 else "Unknown size"
        print(f"    File size: {size_str}")

        with open(output_path, 'wb') as f:
            downloaded_bytes = 0
            start_time = time.time()
            for chunk in response.iter_content(chunk_size=1024*1024): # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded_bytes += len(chunk)

        elapsed_time = time.time() - start_time
        if file_size > 0 and downloaded_bytes < file_size * 0.9:
             print(f"\n    ⚠️ WARNING: Downloaded size ({downloaded_bytes / (1024*1024):.2f} MB) < expected ({size_str}). File might be incomplete.")
        elif downloaded_bytes == 0 and file_size > 100:
            print(f"\n    ❌ ERROR: Downloaded 0 bytes but Content-Length was {size_str}. Download failed.")
            if os.path.exists(output_path): os.remove(output_path)
            return False
        elif downloaded_bytes == 0 and file_size == 0:
             print(f"\n    ⚠️ WARNING: Downloaded 0 bytes (Content-Length was 0). File might be empty.")

        print(f"\n    ✅ Successfully downloaded to {os.path.basename(output_path)} ({downloaded_bytes / (1024*1024):.2f} MB in {elapsed_time:.1f}s)")
        return True

    except requests.exceptions.Timeout:
        print(f"    ❌ ERROR: Timeout after {DOWNLOAD_TIMEOUT}s while downloading video.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"    ❌ ERROR downloading video: {e}")
        return False
    except Exception as e:
         print(f"    ❌ ERROR: Unexpected Python error during video download: {e}")
         return False

# --- get_avatar_clip function (with NameError fix in polling loop) ---
def get_avatar_clip(text, avatar_id, voice_id, output_dir, retry_delay_status=20, max_wait_minutes=10):
    """Manages the full process: request, poll status, download. Returns filepath or None."""
    ensure_dir(output_dir)
    segment_log_id = str(uuid.uuid4())[:8]

    print(f"\n--- [Avatar] Processing segment {segment_log_id} (Text len: {len(text)}) ---")

    # 1. Request Video Generation
    video_id = request_avatar_video(text, avatar_id, voice_id)
    if not video_id:
        print(f"Segment {segment_log_id}: ❌ Failed to initiate video generation.")
        return None

    output_path = os.path.join(output_dir, f"{video_id}.mp4")

    # 2. Poll for Status
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    poll_count = 0 # Track poll attempts for increasing delay slightly
    print(f"Segment {segment_log_id}: Polling status for Video ID: {video_id} (Max wait: {max_wait_minutes} mins)...")

    while True:
        current_wait = time.time() - start_time
        if current_wait >= max_wait_seconds:
             print(f"  ❌ Timeout: Waited over {max_wait_minutes} minutes for video {video_id}.")
             return None

        status, video_url, error_message = check_video_status(video_id)
        status_str = status if status else "Unknown"
        print(f"  Status check ({current_wait:.0f}s): {status_str}")

        if status == 'completed':
            if video_url:
                print(f"  Video {video_id} completed. Proceeding to download...")
                if download_video(video_url, output_path):
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000: # Check > 1KB
                         print(f"Segment {segment_log_id}: ✅ Successfully processed.")
                         return output_path
                    else:
                         print(f"  ❌ ERROR: Download reported success, but file '{os.path.basename(output_path)}' is missing or empty.")
                         return None
                else:
                    print(f"  ❌ ERROR: Failed to download completed video {video_id}.")
                    return None
            else:
                print(f"  ❌ ERROR: Video {video_id} status is 'completed' but download URL is missing!")
                return None

        elif status == 'failed' or status == 'error':
            err_msg = error_message or 'Unknown error from API'
            print(f"  ❌ ERROR: Video generation failed or error occurred for {video_id}. Reason: {err_msg}")
            return None

        # Handle known wait/retry states (pending, processing, waiting) and None/timeout from check_video_status
        elif status in ['processing', 'pending', 'waiting', None, 'timeout']:
             poll_count += 1
             remaining_time = max(0, max_wait_seconds - current_wait - 1)
             # *** CORRECTED NameError: Use poll_count instead of attempt ***
             # Slightly increase delay for subsequent polls
             current_delay = retry_delay_status + min(poll_count * 2, 40) # Cap extra delay
             wait_time = min(current_delay, remaining_time)
             # *** --------------------------------------------------- ***
             if wait_time <= 0: continue # Check again immediately if very close to timeout
             print(f"  Waiting {int(wait_time)}s before next status check...")
             time.sleep(wait_time)
        else: # Handle truly unexpected statuses from API
            print(f"  Warning: Received unexpected status '{status}' for video {video_id}. Waiting {retry_delay_status}s...")
            time.sleep(retry_delay_status)