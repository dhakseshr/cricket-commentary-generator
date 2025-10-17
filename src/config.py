# src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Project Root ---
# This assumes your 'src' folder is one level down from the root
ROOT_DIR = Path(__file__).parent.parent.parent
print(f"Project Root: {ROOT_DIR}")

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DID_AUTH_HEADER_VALUE = os.getenv("DID_AUTH_HEADER_VALUE")

# --- D-ID API ---
DID_API_URL = "https://api.d-id.com"

# --- ElevenLabs Settings ---
# Find Voice IDs in your ElevenLabs VoiceLab
# Example: "Rachel" (21m00Tcm4TlvDq8ikWAM)
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# --- File Paths ---
ASSETS_DIR = ROOT_DIR / "assets"
TEMP_DIR = ROOT_DIR / "temp"
OUTPUT_DIR = ROOT_DIR / "output"
TEMPLATES_DIR = ROOT_DIR / "src" / "templates"

# --- Static Asset Paths ---
AVATAR_IMAGE_PATH = ASSETS_DIR / "avatar.png"
CHART_TEMPLATE_PATH = TEMPLATES_DIR / "chart_template.html"

# --- Validation ---
if not all([GEMINI_API_KEY, ELEVENLABS_API_KEY, DID_AUTH_HEADER_VALUE]):
    raise EnvironmentError(
        "Missing one or more API keys in your .env file. "
        "Please check GEMINI_API_KEY, ELEVENLABS_API_KEY, and DID_AUTH_HEADER_VALUE."
    )

if not AVATAR_IMAGE_PATH.exists():
    raise FileNotFoundError(
        f"Avatar image not found at {AVATAR_IMAGE_PATH}. "
        "Please add 'avatar.png' to the 'assets' directory."
    )