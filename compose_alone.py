import os
import time
from src.video_composer import compose_video_ffmpeg_with_crossfade
from src.utils import ensure_dir

# --- 1. Define Asset Locations ---
# (These are the directories where your files were saved by main.py)
AVATAR_DIR = os.path.join("output", "avatar_clips")
CHARTS_DIR = os.path.join("output", "charts")
FINAL_VIDEOS_DIR = os.path.join("output", "final_videos")

# --- 2. Define the exact sequence of files ---
# (I've copied these filenames directly from your log output)
# We add the correct directory path to each one.
clip_paths = [
    os.path.join(AVATAR_DIR, "79c195a5f847479a81e25c54b7052f5b.mp4"), # Intro
    os.path.join(CHARTS_DIR, "run_rate_comparison.png"),             # Chart 1
    os.path.join(AVATAR_DIR, "39a0585bdfcb401b84c97bceb26837db.mp4"), # Event 1
    os.path.join(AVATAR_DIR, "9e77d94f38ad40c398688335b6a560df.mp4"), # Event 2
    os.path.join(AVATAR_DIR, "6b7ba773ea0f4e1481a9f105c48e7ec6.mp4"), # Event 3
    os.path.join(CHARTS_DIR, "manhattan_chart.png"),                 # Chart 2
    os.path.join(AVATAR_DIR, "5a58a15993bd41aea4e0f47276f39bff.mp4"), # Event 4
    os.path.join(AVATAR_DIR, "62e51d2030d64f4f84b7974391e52b09.mp4"), # Event 5
    os.path.join(AVATAR_DIR, "6143d79a26fa4c75a99e4765af43bcb0.mp4"), # Event 6
    os.path.join(AVATAR_DIR, "27aa64dcaea345ce9cda7433048739e9.mp4")  # Outro
]

# --- 3. Define Composition Settings ---
# (These are copied from your main.py)
TRANSITION_DURATION = 0.6
CHART_DISPLAY_DURATION = 6.0
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_FPS = 25

# --- 4. Define Output File Path ---
ensure_dir(FINAL_VIDEOS_DIR)
timestamp = time.strftime("%Y%m%d_%H%M%S")
output_filepath = os.path.join(FINAL_VIDEOS_DIR, f"standalone_composition_{timestamp}.mp4")

# --- 5. Run the Composition ---
print(f"--- [Standalone Composer] ---")
print(f"Found {len(clip_paths)} assets to compose.")
print(f"Outputting to: {output_filepath}")

# First, check if all the files actually exist
all_files_found = True
for f_path in clip_paths:
    if not os.path.exists(f_path):
        print(f"❌ ERROR: Cannot find file: {f_path}")
        all_files_found = False

if all_files_found:
    print("\nAll files found. Starting composition...")
    
    # This calls the exact same function from video_composer.py
    composition_success = compose_video_ffmpeg_with_crossfade(
        clip_paths=clip_paths,
        output_filepath=output_filepath,
        transition_duration=TRANSITION_DURATION,
        default_chart_duration=CHART_DISPLAY_DURATION,
        target_width=TARGET_WIDTH,
        target_height=TARGET_HEIGHT,
        target_fps=TARGET_FPS
    )

    if composition_success:
        print(f"✅ Successfully composed video: {output_filepath}")
    else:
        print(f"❌ Video composition failed. Check FFmpeg logs above.")
else:
    print("\nComposition failed: One or more input files are missing.")