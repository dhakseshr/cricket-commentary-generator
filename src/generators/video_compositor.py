# src/generators/video_compositor.py
import logging
import ffmpeg
from pathlib import Path

def compose_video(
    avatar_video_path: Path,
    chart_image_path: Path,
    output_path: Path
) -> Path:
    """
    Uses FFmpeg to create the final video:
    1. Uses the chart image as the main background.
    2. Overlays the avatar video (scaled down) in a corner.
    3. Uses the audio from the avatar video.
    
    This is a SYNCHRONOUS, CPU-intensive function and should be run
    in asyncio.to_thread.
    """
    logging.info("Starting final video composition with FFmpeg...")
    
    try:
        # 1. Probe the avatar video to get its duration and dimensions
        probe = ffmpeg.probe(str(avatar_video_path))
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        duration = float(probe['format']['duration'])
        avatar_width = int(video_info['width'])
        
        # Calculate new width (e.g., 30% of 1280), maintain aspect ratio
        base_width = 1280 
        scale_width = int(base_width * 0.3) # 384px

        # 2. Define inputs
        # Input 1: The chart image, looped for the duration of the audio
        chart_input = ffmpeg.input(
            str(chart_image_path),
            loop=1,
            framerate=25,
            t=duration
        )
        
        # Input 2: The avatar video
        avatar_input = ffmpeg.input(str(avatar_video_path))

        # 3. Define video and audio streams
        v_chart = chart_input['v']
        v_avatar = avatar_input['v']
        a_avatar = avatar_input['a']

        # 4. Create the filter complex
        # Scale the avatar video down to 'scale_width' (e.g., 384)
        v_avatar_scaled = v_avatar.filter('scale', scale_width, -1)
        
        # Overlay the scaled avatar on the chart video
        # 'main_w-overlay_w-20' = main width - overlay width - 20px padding (Top Right)
        # '20' = 20px padding from top
        final_video = v_chart.overlay(
            v_avatar_scaled,
            x='main_w-overlay_w-20',
            y=20
        )

        # 5. Define the output and run the command
        (
            ffmpeg
            .output(
                final_video,       # The combined video stream
                a_avatar,          # The audio stream from the avatar
                str(output_path),
                vcodec='libx264',  # Standard video codec
                acodec='aac',      # Standard audio codec
                t=duration,        # Set total duration
                pix_fmt='yuv420p'  # Standard pixel format for compatibility
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        logging.info(f"Successfully composed final video: {output_path}")
        return output_path

    except ffmpeg.Error as e:
        logging.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        raise
    except Exception as e:
        logging.error(f"Error during video composition: {e}")
        raise