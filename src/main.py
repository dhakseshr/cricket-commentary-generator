# src/main.py
import asyncio
import logging
import shutil
import httpx
from pathlib import Path

# Import project-specific modules
from src import config
from src.services import gemini_client, elevenlabs_client, did_client
from src.generators import chart_generator, video_compositor
from src.utils import downloader, file_hosting

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(module)s] %(message)s",
)

def setup_workspace():
    """Creates or clears the temp and output directories."""
    logging.info("Setting up workspace...")
    config.TEMP_DIR.mkdir(exist_ok=True)
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Clean the temp directory
    for f in config.TEMP_DIR.glob('*'):
        if f.is_file():
            f.unlink()
    logging.info("Workspace is clean.")


async def main_pipeline():
    """Runs the complete AI video generation pipeline."""
    setup_workspace()
    
    # Define paths for intermediate and final files
    commentary_text_path = config.TEMP_DIR / "1_commentary.txt"
    audio_path = config.TEMP_DIR / "2_commentary.mp3"
    chart_path = config.TEMP_DIR / "3_chart.png"
    avatar_video_path = config.TEMP_DIR / "4_avatar_video.mp4"
    final_video_path = config.OUTPUT_DIR / "final_commentary_video.mp4"
    
    # --- Mock Data for the pipeline ---
    # (In a real app, you'd fetch this from your Task 2 API)
    mock_match_data = {
        "title": "T20 Final: Titans vs Blasters",
        "scores": [182, 178],
        "labels": ["Titans (182/5)", "Blasters (178/8)"],
        "datasetLabel": "Runs Scored",
        "key_player": "J. Smith (Titans)",
        "key_stat": "95 runs off 48 balls"
    }
    
    try:
        # --- Step 1: Generate Commentary (Async) ---
        logging.info("--- [Step 1/6] Generating Commentary ---")
        prompt = (
            f"You are an excited cricket commentator. "
            f"Generate a 30-second summary for a match highlight video. "
            f"Match: {mock_match_data['title']}. "
            f"Stats: {mock_match_data['labels'][0]} vs {mock_match_data['labels'][1]}. "
            f"The player of the match was {mock_match_data['key_player']} with {mock_match_data['key_stat']}. "
            f"Keep it energetic and concise!"
        )
        commentary_text = await gemini_client.generate_commentary(prompt)
        with open(commentary_text_path, "w") as f:
            f.write(commentary_text)
        logging.info(f"Commentary: {commentary_text}")

        # --- Step 2: Synthesize Voice (Sync, run in thread) ---
        logging.info("--- [Step 2/6] Synthesizing Voice ---")
        await asyncio.to_thread(
            elevenlabs_client.synthesize_voice,
            text=commentary_text,
            output_path=audio_path
        )

        # --- Step 3: Generate Chart (Async) ---
        logging.info("--- [Step 3/6] Generating Chart ---")
        await chart_generator.create_chart_image(
            chart_data=mock_match_data,
            output_path=chart_path
        )

        # --- Step 4: Get Public URLs for D-ID (Sync, run in thread) ---
        logging.info("--- [Step 4/6] Getting Public URLs for D-ID ---")
        # This step uses the STUB function. It must be replaced.
        public_audio_url = await asyncio.to_thread(
            file_hosting.get_public_url, audio_path
        )
        public_image_url = await asyncio.to_thread(
            file_hosting.get_public_url, config.AVATAR_IMAGE_PATH
        )

        # --- Step 5: Generate Avatar Video (Async, 3-part) ---
        logging.info("--- [Step 5/6] Generating Avatar Video ---")
        async with httpx.AsyncClient() as client:
            # 5a: Start the job
            talk_id = await did_client.start_video_generation(
                client=client,
                audio_url=public_audio_url,
                image_url=public_image_url
            )
            # 5b: Poll for the result
            result_url = await did_client.get_video_result(
                client=client,
                talk_id=talk_id
            )
            # 5c: Download the video
            await downloader.download_file(
                url=result_url,
                output_path=avatar_video_path
            )

        # --- Step 6: Compose Final Video (Sync, run in thread) ---
        logging.info("--- [Step 6/6] Composing Final Video ---")
        await asyncio.to_thread(
            video_compositor.compose_video,
            avatar_video_path=avatar_video_path,
            chart_image_path=chart_path,
            output_path=final_video_path
        )
        
        logging.info("========================================")
        logging.info(f"🎉 PIPELINE COMPLETE! 🎉")
        logging.info(f"Final video saved to: {final_video_path}")
        logging.info("========================================")

    except Exception as e:
        logging.error(f"--- PIPELINE FAILED ---")
        logging.error(f"An error occurred: {e}")
        # In a real app, you might want more specific error handling
        # and cleanup here.

if __name__ == "__main__":
    try:
        asyncio.run(main_pipeline())
    except Exception as e:
        logging.critical(f"A top-level error occurred: {e}")