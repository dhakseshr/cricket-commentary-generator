# src/services/did_client.py
import logging
import httpx
import asyncio
from src import config

async def start_video_generation(client: httpx.AsyncClient, audio_url: str, image_url: str) -> str:
    """
    Starts the D-ID talk generation job.
    Returns the 'talk_id' for polling.
    """
    logging.info("Connecting to D-ID API to start job...")
    url = f"{config.DID_API_URL}/talks"
    headers = {
        "Authorization": config.DID_AUTH_HEADER_VALUE,
        "Content-Type": "application/json"
    }
    payload = {
        "source_url": image_url,
        "script": {
            "type": "audio",
            "audio_url": audio_url
        },
        "config": {
            "result_format": "mp4",
            "driver": "clv" # Use 'clv' for standard, high-quality driver
        }
    }

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()  # Raise exception for 4xx/5xx errors
        
        result = response.json()
        talk_id = result.get("id")
        
        if not talk_id:
            raise ValueError(f"D-ID API did not return a talk ID. Response: {result}")
            
        logging.info(f"D-ID job started successfully. Talk ID: {talk_id}")
        return talk_id
        
    except httpx.HTTPStatusError as e:
        logging.error(f"D-ID API HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logging.error(f"Error starting D-ID video generation: {e}")
        raise

async def get_video_result(client: httpx.AsyncClient, talk_id: str, poll_interval: int = 5) -> str:
    """
    Polls the D-ID API until the video is ready and returns the result_url.
    """
    logging.info(f"Polling D-ID for result (Talk ID: {talk_id})...")
    url = f"{config.DID_API_URL}/talks/{talk_id}"
    headers = {"Authorization": config.DID_AUTH_HEADER_VALUE}

    while True:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status")
            
            if status == "done":
                result_url = result.get("result_url")
                if not result_url:
                    raise ValueError(f"D-ID job is 'done' but no 'result_url' found. {result}")
                
                logging.info(f"D-ID video generation is complete. URL: {result_url}")
                return result_url
                
            elif status in ("created", "started", "pending"):
                logging.debug(f"Video status is '{status}'. Waiting {poll_interval}s...")
                await asyncio.sleep(poll_interval)
                
            elif status == "error":
                raise RuntimeError(f"D-ID video generation failed. Error: {result.get('error')}")
            else:
                raise RuntimeError(f"Unknown status from D-ID: {status}. Full response: {result}")

        except httpx.HTTPStatusError as e:
            logging.error(f"D-ID polling HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logging.error(f"Error while polling D-ID: {e}")
            raise