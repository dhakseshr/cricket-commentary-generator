# src/video_composer.py

import ffmpeg
import os
import subprocess
from src.utils import ensure_dir
import math

def get_video_info(filepath):
    """Gets video duration, dimensions, and audio presence using ffprobe. Ensures absolute path."""
    # Ensure the path is absolute before probing
    abs_filepath = os.path.abspath(filepath) if filepath else None

    if not abs_filepath or not os.path.exists(abs_filepath):
        # File doesn't exist at the resolved absolute path
        print(f"  Warning: File not found at absolute path, cannot probe: '{abs_filepath}' (from input '{filepath}')")
        return None, None, None, False
    if os.path.getsize(abs_filepath) < 100: # Check if file has minimal size
        print(f"  Warning: File is too small, likely invalid: {os.path.basename(filepath)}")
        return None, None, None, False

    try:
        # print(f"Probing: {abs_filepath}") # Verbose
        probe_v = ffmpeg.probe(abs_filepath, select_streams='v', loglevel="warning") # Use abs_path
        video_stream = probe_v['streams'][0] if probe_v.get('streams') else None

        probe_a = ffmpeg.probe(abs_filepath, select_streams='a', loglevel="warning") # Use abs_path
        audio_stream = probe_a['streams'][0] if probe_a.get('streams') else None

        probe_f = ffmpeg.probe(abs_filepath, loglevel="warning") # Use abs_path
        format_info = probe_f.get('format', {})

        duration = 0
        width = None
        height = None
        has_audio = bool(audio_stream)

        # Get duration
        if video_stream and 'duration' in video_stream and float(video_stream['duration']) > 0:
            duration = float(video_stream['duration'])
        elif audio_stream and 'duration' in audio_stream and float(audio_stream['duration']) > 0:
            duration = float(audio_stream['duration'])
        elif 'duration' in format_info and float(format_info['duration']) > 0:
            duration = float(format_info['duration'])

        if video_stream:
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            if width <= 0 or height <= 0: width, height = None, None

        if duration <= 0.01:
             print(f"  Warning: Invalid duration ({duration:.3f}s) in {os.path.basename(filepath)}. Skipping.")
             return None, None, None, False

        return duration, width, height, has_audio

    except ffmpeg.Error as e:
        stderr_str = e.stderr.decode(errors='ignore') if e.stderr else str(e)
        print(f"  ❌ FFprobe Error for {os.path.basename(filepath)}: {stderr_str[:300]}...")
        return None, None, None, False
    except Exception as e:
         print(f"  ❌ Unexpected Python error in get_video_info for {os.path.basename(filepath)}: {e}")
         return None, None, None, False

def cleanup_temp_files(temp_files):
     """Removes temporary files created during the process."""
     if temp_files:
         print("\n--- [Composer] Cleaning up temporary files ---")
         cleaned_count = 0
         for temp_path in temp_files:
             abs_temp_path = os.path.abspath(temp_path) # Ensure absolute for removal too
             if os.path.exists(abs_temp_path):
                 try:
                     os.remove(abs_temp_path)
                     cleaned_count += 1
                 except OSError as e:
                     print(f"  Warning: Error removing temp file {os.path.basename(abs_temp_path)}: {e}")
         print(f"Cleaned up {cleaned_count} temporary file(s).")


def compose_video_ffmpeg_with_crossfade(
    clip_paths, # List of paths (relative or absolute)
    output_filepath, # Can be relative or absolute
    transition_duration=0.6,
    default_chart_duration=5.0,
    target_width=1280,
    target_height=720,
    target_fps=25,
    bg_music_path=None,
    bg_music_volume=0.08
):
    """Composes video using FFmpeg with crossfade. Uses absolute paths internally."""
    # Ensure output directory exists and output path is absolute from the start
    output_abs_filepath = os.path.abspath(output_filepath)
    output_dir = os.path.dirname(output_abs_filepath)
    ensure_dir(output_dir)

    if not clip_paths:
        print("Error: No input clip paths provided for composition.")
        return False

    inputs_info = []
    temp_files = []
    final_video_width = target_width
    final_video_height = target_height

    print("\n--- [Composer] Pre-processing Inputs ---")
    valid_clips_exist = False
    first_video_dims_found = False
    project_root = os.getcwd() # Get root for resolving relative paths

    for i, path in enumerate(clip_paths):
        # --- *** ENSURE ABSOLUTE PATH FOR PROCESSING *** ---
        if path and not os.path.isabs(path):
            abs_input_path = os.path.abspath(os.path.join(project_root, path))
        elif path:
            abs_input_path = os.path.abspath(path)
        else:
            abs_input_path = None
        # --- ****************************************** ---

        if not abs_input_path or not os.path.exists(abs_input_path):
            print(f"Warning: File path invalid or not found, skipping: '{path}' -> '{abs_input_path}'")
            continue

        _, ext = os.path.splitext(abs_input_path.lower())
        is_image = ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
        base_name = os.path.basename(abs_input_path)

        if is_image:
            img_width, img_height = target_width, target_height
            # Use default_chart_duration for images
            duration = default_chart_duration 
            
            safe_base = "".join([c if c.isalnum() else "_" for c in base_name])[:50]
            # Use absolute path for temp file in the output directory
            temp_video_path = os.path.join(output_dir, f"temp_img_{i}_{safe_base}.mp4")
            print(f"Converting image '{base_name}' to video ({duration:.1f}s)...")
            try:
                # Use abs_input_path for the input image
                (
                    ffmpeg
                    .input(abs_input_path, loop=1, framerate=target_fps, t=duration)
                    .filter('scale', size=f'{img_width}x{img_height}', force_original_aspect_ratio='decrease', flags='bicubic')
                    .filter('pad', w=img_width, h=img_height, x='(ow-iw)/2', y='(oh-ih)/2', color='black')
                    .filter('setsar', sar='1/1')
                    .filter('fps', fps=target_fps)
                    .output(temp_video_path, pix_fmt='yuv420p', video_bitrate='4000k', preset='medium', an=None)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True, quiet=False) # Log stderr
                )

                if os.path.exists(temp_video_path):
                     # Probe the temp video using its absolute path
                     temp_duration, _, _, _ = get_video_info(temp_video_path)
                     # Use the *probed* duration, which should be very close to default_chart_duration
                     if temp_duration is not None and temp_duration > 0:
                          inputs_info.append({'path': temp_video_path, 'duration': temp_duration, 'width': img_width, 'height': img_height, 'has_audio': False, 'is_temp': True})
                          temp_files.append(temp_video_path)
                          print(f"  -> Created temp video: {os.path.basename(temp_video_path)} (Duration: {temp_duration:.2f}s)")
                          valid_clips_exist = True
                          if not first_video_dims_found:
                               final_video_width, final_video_height = img_width, img_height
                               first_video_dims_found = True
                     else: 
                          print(f"  -> ❌ Failed probe/validate temp video from {base_name}")
                          # Even if probe fails, add a placeholder with the intended duration
                          inputs_info.append({'path': temp_video_path, 'duration': duration, 'width': img_width, 'height': img_height, 'has_audio': False, 'is_temp': True})
                          temp_files.append(temp_video_path) # Still need to clean it up
                          print(f"  -> ⚠️ Warning: Using fallback duration ({duration:.2f}s) for {base_name}")
                          valid_clips_exist = True # Assume it's valid
                else: 
                    print(f"  -> ❌ Failed: Temp video not created for {base_name}")

            except ffmpeg.Error as e:
                stderr_text = e.stderr.decode(errors='ignore') if e.stderr else str(e)
                print(f"  -> ❌ FFmpeg Error converting image {base_name}: {stderr_text[:500]}...")
            except Exception as e:
                print(f"  -> ❌ Unexpected Python error converting image {base_name}: {e}")

        else: # It's a video
            # Probe using the absolute path
            duration, width, height, has_audio = get_video_info(abs_input_path)
            if duration is not None and duration > 0:
                clip_width = width if width and width > 0 else target_width
                clip_height = height if height and height > 0 else target_height
                # Store the absolute path
                inputs_info.append({'path': abs_input_path, 'duration': duration, 'width': clip_width, 'height': clip_height, 'has_audio': has_audio, 'is_temp': False})
                valid_clips_exist = True
                if not first_video_dims_found and clip_width and clip_height:
                     final_video_width, final_video_height = clip_width, clip_height
                     first_video_dims_found = True
                     print(f"  -> Using resolution of first valid video ({clip_width}x{clip_height}) as target.")
            else:
                 print(f"Warning: Skipping video due to invalid info or zero duration: {base_name}")


    if not valid_clips_exist or not inputs_info:
        print("❌ ERROR: No valid input clips found after pre-processing.")
        cleanup_temp_files(temp_files)
        return False

    if not first_video_dims_found:
        print("⚠️ Warning: No video dimensions found; defaulting to target.")
        
    target_width, target_height = final_video_width, final_video_height
    print(f"Using target resolution: {target_width}x{target_height}, FPS: {target_fps}")

    # --- CALCULATE MASTER TIMELINE ---
    print("\n--- [Composer] Calculating master timeline ---")
    clip_start_times = [] # This will hold the start time (in seconds) for each clip
    current_offset_s = 0.0
    for i, info in enumerate(inputs_info):
        clip_start_times.append(current_offset_s)
        print(f"  Clip {i} ({os.path.basename(info['path'])}) starts at {current_offset_s:.2f}s")
        
        # Add the effective duration of this clip to the offset
        # The last clip adds its *full* duration
        clip_effective_duration = info['duration'] - (transition_duration if i < len(inputs_info) - 1 else 0)
        clip_effective_duration = max(0.01, clip_effective_duration)
        current_offset_s += clip_effective_duration
    
    final_duration_estimate = current_offset_s # The final offset is the total duration
    print(f"  Total estimated duration: {final_duration_estimate:.2f}s")


    print("\n--- [Composer] Building Filtergraph ---")
    video_inputs_processed = []
    audio_streams_for_mixing = []
    target_sample_rate = '44100'

    for i, info in enumerate(inputs_info):
        try:
            # Input uses the absolute path stored in info['path']
            # Add 't' (duration) to the input args for safety, esp. for images
            stream = ffmpeg.input(info['path'], t=info['duration'])
            v_stream = stream['v']
            
            # Scale/Pad if needed
            stream_w = info.get('width', 0)
            stream_h = info.get('height', 0)
            if stream_w != target_width or stream_h != target_height:
                 v_stream = v_stream.filter('scale', size=f'{target_width}x{target_height}', force_original_aspect_ratio='decrease', flags='bicubic')
                 v_stream = v_stream.filter('pad', w=target_width, h=target_height, x='(ow-iw)/2', y='(oh-ih)/2', color='black')
            
            # Standardize video
            v_stream = v_stream.filter('fps', fps=target_fps, round='near') \
                               .filter('setsar', sar='1/1') \
                               .filter('format', pix_fmts='yuv420p')
            
            video_inputs_processed.append(v_stream)

            # --- AUDIO SYNCHRONIZATION LOGIC ---
            
            # 1. Get base audio stream (or silence for images/silent videos)
            actual_duration = info.get('duration', default_chart_duration)
            if info['has_audio']:
                a_stream = stream['a'].filter('aformat', sample_fmts='fltp', sample_rates=target_sample_rate, channel_layouts='stereo')
                a_stream = a_stream.filter('aresample')
            else:
                 # Create silence *only* for this clip's duration
                 silence = ffmpeg.input(f'anullsrc=channel_layout=stereo:sample_rate={target_sample_rate}', format='lavfi', t=actual_duration)['a']
                 a_stream = silence
            
            # 2. Get the pre-calculated start time for this clip
            start_time_s = clip_start_times[i]
            start_time_ms = int(start_time_s * 1000)

            # 3. Apply 'adelay' to shift this audio to its correct start time
            #    The 'delays' param needs a value for each channel (e.g., "1000|1000" for stereo)
            delayed_audio = a_stream.filter('adelay', delays=f'{start_time_ms}|{start_time_ms}')
            
            # 4. Add the *delayed* stream to the list for final mixing
            audio_streams_for_mixing.append(delayed_audio)
            
        except Exception as e:
            print(f"  ❌ Error processing input stream for {os.path.basename(info['path'])}: {e}")
            cleanup_temp_files(temp_files)
            return False

    # Apply transitions
    if len(inputs_info) > 1:
        # --- VIDEO FADE (using master timeline) ---
        processed_video = video_inputs_processed[0]
        for i in range(1, len(inputs_info)):
             # Use the start time from our master timeline as the offset
             offset_s = clip_start_times[i] 
             processed_video = ffmpeg.filter(
                [processed_video, video_inputs_processed[i]], 'xfade',
                transition='fade', duration=transition_duration, offset=offset_s
            )
        
        # --- *** THE CRITICAL FIX IS HERE *** ---
        print("  Mixing audio streams...")
        processed_audio = ffmpeg.filter(
            audio_streams_for_mixing, 'amix',
            inputs=len(audio_streams_for_mixing),
            duration='longest' # <-- FIX: Was 'first', now 'longest'
        )
        # --- *** END CRITICAL FIX *** ---

    elif len(inputs_info) == 1:
        processed_video = video_inputs_processed[0]
        processed_audio = audio_streams_for_mixing[0] # Use the (undelayed) stream
    else:
        print("❌ ERROR: No processed inputs available for composition.")
        cleanup_temp_files(temp_files)
        return False

    # Optional Background Music
    # This logic is now correct, as 'processed_audio' is the synced master track
    final_audio_stream = processed_audio
    abs_bgm_path = os.path.abspath(bg_music_path) if bg_music_path and not os.path.isabs(bg_music_path) else bg_music_path
    if abs_bgm_path and os.path.exists(abs_bgm_path):
        print(f"Adding background music: {os.path.basename(abs_bgm_path)}")
        try:
             bgm_duration, _, _, has_bgm_audio = get_video_info(abs_bgm_path) # Use absolute path
             if not has_bgm_audio: raise ValueError("Background music file has no audio stream.")

             loop_needed = bgm_duration and bgm_duration > 0 and final_duration_estimate > bgm_duration
             bgm_input = ffmpeg.input(abs_bgm_path, stream_loop=-1 if loop_needed else 0) # Use absolute path

             bgm_audio = (
                 bgm_input['a']
                 .filter('atrim', duration=final_duration_estimate)
                 .filter('volume', volume=bg_music_volume)
                 .filter('aformat', sample_fmts='fltp', sample_rates=target_sample_rate, channel_layouts='stereo')
                 .filter('aresample')
             )
             # This amix is correct with 'duration=first' because 'processed_audio'
             # is the first input and defines the final, correct length.
             final_audio_stream = ffmpeg.filter(
                  [processed_audio, bgm_audio], 'amix', inputs=2, duration='first', dropout_transition=transition_duration*2
             )
             print("  -> Background music prepared for mixing.")
        except Exception as e:
            print(f"  ⚠️ Warning: Error processing background music: {e}. Skipping BGM.")
            final_audio_stream = processed_audio

    # Output
    print("\n--- [Composer] Starting FFmpeg Composition ---")
    try:
        output_args = {
            'vcodec': 'libx264', 'pix_fmt': 'yuv420p', 'r': target_fps,
            'crf': 23, 'preset': 'medium', 'b:v': '4000k','movflags': '+faststart',
            'acodec': 'aac', 'audio_bitrate': '128k', 'ar': int(target_sample_rate),
            'strict': '-2',
            #'shortest': None, # Do not use 'shortest' with this timeline logic
            'y': None # Overwrite output without asking
        }
        # Use output_abs_filepath
        stream = ffmpeg.output(processed_video, final_audio_stream, output_abs_filepath, **output_args)

        print(f"Outputting to: {output_abs_filepath}")
        print("Executing FFmpeg command (this may take time)...")
        stdout, stderr = stream.run(capture_stdout=True, capture_stderr=True, quiet=False) # quiet=False is essential
        print("FFmpeg process finished.")
        stderr_output = stderr.decode(errors='ignore')

        error_keywords = ["error", "failed", "unable", "invalid", "unknown", "can not", "cannot", "no such file"]
        error_lines = [line for line in stderr_output.splitlines() if any(keyword in line.lower() for keyword in error_keywords)]

        if error_lines:
             print("❌ Potential errors detected in FFmpeg stderr:")
             for line in error_lines[-15:]: print(f"   {line}")
        elif len(stderr_output) > 50:
             print("FFmpeg stderr (last 15 lines):\n...\n" + "\n".join(stderr_output.splitlines()[-15:]))
        elif stderr_output: # Print short stderr logs completely
             print("FFmpeg stderr:\n" + stderr_output)


        if os.path.exists(output_abs_filepath) and os.path.getsize(output_abs_filepath) > 1000:
             print(f"✅ Successfully composed video: {output_filepath}")
             return True
        else:
             print(f"❌ ERROR: Output file not found or is too small after FFmpeg execution: {output_filepath}")
             # Print full log if no specific errors found and it wasn't already printed
             if not error_lines and len(stderr_output.splitlines()) > 15:
                  print("\nFull FFmpeg stderr:\n" + stderr_output)
             return False

    except ffmpeg.Error as e:
        print("❌ FATAL: Error during FFmpeg composition execution:")
        stderr_decoded = e.stderr.decode(errors='ignore') if e.stderr else "N/A"
        print(f"FFmpeg command failed. Stderr:\n{stderr_decoded}") # Print full stderr on ffmpeg.Error
        return False
    except Exception as e:
         print(f"❌ FATAL: Unexpected Python error during composition execution: {e}")
         return False
    finally:
        cleanup_temp_files(temp_files)