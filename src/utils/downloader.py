# src/utils/downloader.py
import logging
from pathlib import Path
import httpx

async def download_file(url: str, output_path: Path) -> Path:
    """
    Downloads a file from a URL to a specified path.
    """
    logging.info(f"Downloading file from {url}...")
    try:
        async with httpx.AsyncClient() as client:
            # Use a streaming response for potentially large video files
            async with client.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
                        
        logging.info(f"Successfully downloaded file to {output_path}")
        return output_path
        
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error while downloading {url}: {e}")
        raise
    except Exception as e:
        logging.error(f"Failed to download {url}: {e}")
        raise