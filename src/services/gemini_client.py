# src/services/gemini_client.py
import logging
import google.generativeai as genai
from src import config

# Configure the SDK with the API key
try:
    genai.configure(api_key=config.GEMINI_API_KEY)
except Exception as e:
    logging.error(f"Failed to configure Gemini: {e}")
    raise

async def generate_commentary(prompt: str) -> str:
    """
    Generates text content using the Gemini 1.5 Pro model.
    """
    logging.info("Connecting to Gemini API...")
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = await model.generate_content_async(prompt)
        
        if not response.parts:
            raise ValueError("Gemini API returned an empty response.")
            
        logging.info("Successfully generated commentary.")
        return response.text
        
    except Exception as e:
        logging.error(f"Error during Gemini content generation: {e}")
        raise