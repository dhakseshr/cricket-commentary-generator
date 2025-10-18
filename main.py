import os
import time
import argparse
import re # For cleaning segment names
from src.utils import ensure_dir, get_timestamp
from src.data_processor import load_match_data, get_match_summary, format_inning_for_llm
from src.commentary_generator import (
    analyze_inning_and_generate_scripts,
    create_intro_script,
    create_summary_commentary
)
from src.chart_generator import plot_run_rate, plot_manhattan
from src.avatar_handler import get_avatar_clip
from src.video_composer import compose_video_ffmpeg_with_crossfade

# --- Configuration ---
DEFAULT_MATCH_DATA_FILE = "data/example_match.json"
OUTPUT_DIR = "output"
CHARTS_DIR = os.path.join(OUTPUT_DIR, "charts")
AVATAR_CLIPS_DIR = os.path.join(OUTPUT_DIR, "avatar_clips")
FINAL_VIDEOS_DIR = os.path.join(OUTPUT_DIR, "final_videos")
COMMENTARY_DIR = os.path.join(OUTPUT_DIR, "commentary_scripts")

# Ensure base output directories exist
ensure_dir(OUTPUT_DIR); ensure_dir(CHARTS_DIR); ensure_dir(AVATAR_CLIPS_DIR);
ensure_dir(FINAL_VIDEOS_DIR); ensure_dir(COMMENTARY_DIR)

# HeyGen/D-ID Config from .env (with fallback check)
DEFAULT_AVATAR_ID_FROM_ENV = os.getenv("DEFAULT_AVATAR_ID")
DEFAULT_VOICE_ID_FROM_ENV = os.getenv("DEFAULT_VOICE_ID")

# Composition Settings
TRANSITION_DURATION = 0.6
CHART_DISPLAY_DURATION = 6.0
LLM_HIGHLIGHTS_PER_INNING = 3
MAX_BALLS_FOR_LLM = 150 # Limit data sent to LLM per inning

# --- Main Workflow Function ---
def run_commentary_pipeline(match_data_filepath, avatar_id, voice_id):
    """Executes the full pipeline for a given match data file using LLM analysis."""
    start_time = time.time()
    print(f"--- Starting Cricket Commentary Pipeline (LLM Analysis) ---")
    print(f"Input file: {os.path.basename(match_data_filepath)}")
    print(f"Using Avatar ID: {avatar_id}, Voice ID: {voice_id}")


    # --- Step 1: Parse Data & Get Summary ---
    print("\n[1/6] Parsing Match Data...")
    match_data = load_match_data(match_data_filepath)
    if not match_data:
        print("❌ ERROR: Failed to load match data. Exiting.")
        return
    match_summary = get_match_summary(match_data)
    print("Match Summary:", match_summary)

    # --- Step 2: Generate Intro Commentary ---
    print("\n[2/6] Generating Intro Commentary...")
    commentary_segments = {} # { segment_name: commentary_text }
    segment_order = []       # [ segment_name, ... ] in desired final order

    intro_script = create_intro_script(match_summary)
    # Check if script is valid (not None and not placeholder/error)
    is_intro_valid = intro_script and not intro_script.startswith("Placeholder") and not intro_script.startswith("Error")
    if is_intro_valid:
        segment_name = "00_intro"
        commentary_segments[segment_name] = intro_script
        segment_order.append(segment_name)
        print(f"  -> Generated Intro script (len: {len(intro_script)}).")
        # Save script
        script_path = os.path.join(COMMENTARY_DIR, f'{segment_name}_{get_timestamp()}.txt')
        try:
            with open(script_path, 'w', encoding='utf-8') as f: f.write(intro_script)
        except IOError as e: print(f"  Warning: Error saving script {os.path.basename(script_path)}: {e}")
    else:
        print(f"  Warning: Could not generate valid intro script. Received: '{str(intro_script)[:100]}...'")

    # --- Step 3: LLM Analysis & Highlight Commentary ---
    print("\n[3/6] Analyzing Innings & Generating Highlight Commentary via LLM...")
    llm_events_ordered = []
    if 'innings' in match_data and isinstance(match_data['innings'], list):
        for i, inning_data in enumerate(match_data['innings']):
            if not isinstance(inning_data, dict):
                 print(f"  Skipping invalid inning data (index {i}).")
                 continue
            inning_num = i + 1
            team = inning_data.get('team', f'Inning_{inning_num}')
            print(f"  Processing Inning {inning_num} ({team})...")

            inning_llm_data = format_inning_for_llm(inning_data, inning_num, max_balls=MAX_BALLS_FOR_LLM)
            if not inning_llm_data or len(inning_llm_data.split('\n')) < 2:
                print(f"    Warning: Could not format data sufficiently for Inning {inning_num}.")
                continue

            analysis_result = analyze_inning_and_generate_scripts(
                inning_llm_data, match_summary, inning_number=inning_num, num_highlights=LLM_HIGHLIGHTS_PER_INNING
            )

            if analysis_result and analysis_result.get("events"):
                inning_events = analysis_result["events"]
                print(f"    LLM identified {len(inning_events)} highlights for Inning {inning_num}.")
                try: # Sort by ball number string numerically
                     inning_events.sort(key=lambda x: [int(p) for p in str(x.get('ball', '999.9')).split('.')])
                except ValueError:
                     print("    Warning: Could not numerically sort events by ball number.")

                for event in inning_events:
                    ball_val = event.get('ball', f'event{len(llm_events_ordered)}')
                    ball_str = str(ball_val).replace('.', '_')
                    # Sanitize description for filename
                    desc_short = re.sub(r'\W+', '_', event.get('description', 'highlight'))[:20].lower()
                    segment_name = f"{inning_num:02d}_{ball_str}_{desc_short}"
                    commentary = event.get('commentary')

                    is_commentary_valid = commentary and not commentary.startswith("Placeholder") and not commentary.startswith("Error")
                    if is_commentary_valid:
                         if segment_name not in commentary_segments:
                              llm_events_ordered.append({'segment_name': segment_name, 'commentary': commentary})
                              commentary_segments[segment_name] = commentary
                              # Optional: Save script
                              # ... (save script code) ...
                    else:
                         print(f"    Warning: Invalid/Placeholder commentary received for {segment_name}")
            else:
                 print(f"    No valid events returned from LLM analysis for Inning {inning_num}.")
    else:
        print("  No valid 'innings' list found in JSON to analyze.")

    # Add sorted event segment names to the main order list
    segment_order.extend([event['segment_name'] for event in llm_events_ordered])

    # --- Generate Outro ---
    print("  Generating Outro Commentary...")
    outro_script = create_summary_commentary(match_summary)
    is_outro_valid = outro_script and not outro_script.startswith("Placeholder") and not outro_script.startswith("Error")
    if is_outro_valid:
         segment_name = "99_conclusion"
         commentary_segments[segment_name] = outro_script
         segment_order.append(segment_name)
         print(f"  -> Generated Outro script (len: {len(outro_script)}).")
         # Optional: Save script
         # ... (save script code) ...
    else:
        print(f"  Warning: Could not generate valid conclusion script. Received: '{str(outro_script)[:100]}...'")

    print(f"Total commentary segments identified/generated: {len(segment_order)}")

    # --- Step 4: Generate Charts ---
    print("\n[4/6] Generating Charts...")
    chart_paths = {} # { chart_type_name: path }
    run_rate_chart_path = plot_run_rate(match_data, CHARTS_DIR)
    if run_rate_chart_path: chart_paths['run_rate'] = run_rate_chart_path
    manhattan_chart_path = plot_manhattan(match_data, CHARTS_DIR)
    if manhattan_chart_path: chart_paths['manhattan'] = manhattan_chart_path
    print(f"Generated {len(chart_paths)} charts.")

    # --- Step 5: Generate Avatar Video Clips ---
    print("\n[5/6] Generating Avatar Video Clips (using HeyGen)...")
    avatar_clip_paths = {} # { segment_name: path }
    generated_avatar_count = 0
    segments_to_generate_avatar_for = [s for s in segment_order if s in commentary_segments and not commentary_segments[s].startswith("Placeholder") and not commentary_segments[s].startswith("Error")]


    if not avatar_id or not voice_id:
         print("❌ ERROR: HeyGen Avatar or Voice ID is missing. Skipping avatar generation.")
    elif not segments_to_generate_avatar_for:
         print("  No valid commentary segments found to generate avatar clips for.")
    else:
        print(f"Attempting to generate {len(segments_to_generate_avatar_for)} avatar clips...")
        for segment_name in segments_to_generate_avatar_for:
            script_text = commentary_segments[segment_name] # Already checked validity
            print(f"  Processing avatar clip for: {segment_name}...")
            clip_path = get_avatar_clip(
                text=script_text, avatar_id=avatar_id, voice_id=voice_id, output_dir=AVATAR_CLIPS_DIR
            )
            if clip_path:
                avatar_clip_paths[segment_name] = clip_path
                generated_avatar_count += 1
            else:
                print(f"    -> ❌ Failed/Timeout generating clip for {segment_name}")
            # Optional short delay
            # time.sleep(1)

    print(f"Finished avatar clip processing. Successful generations/downloads: {generated_avatar_count} / {len(segments_to_generate_avatar_for)}.")

    # --- Step 6: Compose Final Video ---
    print("\n[6/6] Composing Final Video using FFmpeg...")

    # Define the sequence of assets (paths) - crucial for order
    final_sequence_paths = []

    # Simple Sequence: Intro -> RR Chart -> Event Clips -> Manhattan Chart -> Outro
    # Add Intro (if generated)
    if "00_intro" in avatar_clip_paths: final_sequence_paths.append(avatar_clip_paths["00_intro"])
    # Add Run Rate Chart (if generated)
    if "run_rate" in chart_paths: final_sequence_paths.append(chart_paths["run_rate"])

    # Add Event Clips (in order, only those successfully generated)
    event_segments_in_order = [s for s in segment_order if s != "00_intro" and s != "99_conclusion"]
    insert_manhattan_at_index = len(event_segments_in_order) // 2
    added_manhattan = False
    added_event_clips_count = 0
    for i, segment_name in enumerate(event_segments_in_order):
         # Insert Manhattan chart
         if i == insert_manhattan_at_index and "manhattan" in chart_paths:
              final_sequence_paths.append(chart_paths["manhattan"])
              added_manhattan = True
         # Add the event avatar clip if it exists
         if segment_name in avatar_clip_paths:
              final_sequence_paths.append(avatar_clip_paths[segment_name])
              added_event_clips_count += 1

    # Add Manhattan chart before outro if not inserted earlier
    if not added_manhattan and "manhattan" in chart_paths:
         final_sequence_paths.append(chart_paths["manhattan"])

    # Add Conclusion (if generated)
    if "99_conclusion" in avatar_clip_paths: final_sequence_paths.append(avatar_clip_paths["99_conclusion"])

    # --- Final Check & Composition ---
    if not final_sequence_paths:
        print("❌ ERROR: No valid clips (avatar or charts) available to compose the final video. Check generation steps.")
        return # Exit if nothing to compose

    print("\nFinal composition sequence ({} items):".format(len(final_sequence_paths)))
    for i, path in enumerate(final_sequence_paths): print(f"  {i+1}: {os.path.basename(path)}")

    match_file_base = os.path.splitext(os.path.basename(match_data_filepath))[0]
    output_filename = f"{match_file_base}_commentary_{get_timestamp()}.mp4"
    output_filepath = os.path.join(FINAL_VIDEOS_DIR, output_filename)

    composition_success = compose_video_ffmpeg_with_crossfade(
        clip_paths=final_sequence_paths,
        output_filepath=output_filepath,
        transition_duration=TRANSITION_DURATION,
        default_chart_duration=CHART_DISPLAY_DURATION,
        target_width=1280, # 720p
        target_height=720,
        target_fps=25
        # bg_music_path="path/to/music.mp3" # Optional: Add background music
    )

    end_time = time.time()
    total_duration_secs = end_time - start_time
    print(f"\n--- Pipeline Finished in {total_duration_secs // 60:.0f}m {total_duration_secs % 60:.1f}s ---")

    if composition_success:
        print(f"✅ Final video generated successfully:")
        print(f"   {output_filepath}")
    else:
        print(f"❌ Video composition failed. Check FFmpeg logs printed above.")

# --- Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Automated Cricket Commentary Video using LLM Analysis")
    parser.add_argument(
        "match_file",
        nargs='?',
        default=DEFAULT_MATCH_DATA_FILE,
        help=f"Path to the match data JSON file (default: {DEFAULT_MATCH_DATA_FILE})"
    )
    parser.add_argument("--avatar", default=DEFAULT_AVATAR_ID_FROM_ENV, help="HeyGen Avatar ID (overrides .env)")
    parser.add_argument("--voice", default=DEFAULT_VOICE_ID_FROM_ENV, help="HeyGen Voice ID (overrides .env)")

    args = parser.parse_args()

    # Final check for essential HeyGen IDs
    final_avatar_id = args.avatar
    final_voice_id = args.voice
    if not final_avatar_id or not final_voice_id or final_avatar_id.startswith("your_") or final_voice_id.startswith("your_"):
         print("❌ CRITICAL ERROR: HeyGen Avatar or Voice ID is missing or uses placeholder values.")
         print("   Please set DEFAULT_AVATAR_ID and DEFAULT_VOICE_ID in the .env file")
         print("   or provide valid IDs using --avatar and --voice arguments.")
         exit(1)

    # Check if the input file exists
    if not os.path.exists(args.match_file):
        print(f"❌ ERROR: Input match data file not found at '{args.match_file}'")
        print("   Please place your JSON file in the 'data' directory or provide the correct path.")
    else:
        run_commentary_pipeline(args.match_file, final_avatar_id, final_voice_id)