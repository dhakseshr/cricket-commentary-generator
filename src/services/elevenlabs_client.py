# src/services/elevenlabs_client.py
import logging
from pathlib import Path
from elevenlabs.client import ElevenLabs
from elevenlabs.exceptions import ElevenLabsError
from src import config

def synthesize_voice(text: str, output_path: Path) -> Path:
    """
    Converts text to speech using ElevenLabs and saves it to a file.
    
    This is a SYNCHRONOUS function and should be run in a separate
    thread using asyncio.to_thread to avoid blocking.
    """
    logging.info("Connecting to ElevenLabs API...")
    try:
        client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
        
        # Call the API to convert text to speech
        audio_data = client.text_to_speech.convert(
            text=text,
            model_id=config.ELEVENLABS_MODEL,
            voice_id=config.ELEVENLABS_VOICE_ID,
        )
        
        # Write the binary audio data to the output file
        with open(output_path, "wb") as f:
            f.write(audio_data)
            
        logging.info(f"Successfully synthesized audio to {output_path}")
        return output_path
        
    except ElevenLabsError as e:
        logging.error(f"ElevenLabs API error: {e.message}")
        raise
    except Exception as e:
        logging.error(f"Error during voice synthesis: {e}")
        raise