import os
import time
from dotenv import load_dotenv

# Load .env file at the start when utils is imported
load_dotenv()

def load_api_keys():
    """Loads API keys from environment variables (already loaded by load_dotenv)."""
    keys = {
        "gemini": os.getenv("GEMINI_API_KEY"),
        "heygen": os.getenv("HEYGEN_API_KEY")
    }
    # Warnings moved to where keys are actually checked/used for clarity
    return keys

def ensure_dir(directory_path):
    """Creates a directory if it doesn't exist."""
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            # print(f"Created directory: {directory_path}") # Keep commented unless debugging needed
        except OSError as e:
            # Handle potential race condition if dir is created between check and makedirs
            if not os.path.isdir(directory_path):
                print(f"Error creating directory {directory_path}: {e}")

def get_timestamp():
    """Returns a formatted timestamp string for filenames."""
    return time.strftime("%Y%m%d_%H%M%S")

def exponential_backoff_retry(api_call_func, max_retries=3, initial_delay=2):
    """Decorator or helper function for retrying API calls with backoff."""
    # This is a conceptual structure. Integrate directly into API handler functions.
    # The actual implementation is now within the handler functions below
    # to better manage specific API responses (like 429).
    pass

# You can add more utilities like safe file writing, logging configuration etc. here.