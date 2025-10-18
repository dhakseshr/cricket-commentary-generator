import gradio as gr
import main  # Imports your main.py
import os
import time
from src.utils import ensure_dir

# Get default IDs from environment (will be set by HF Secrets)
DEFAULT_AVATAR = os.getenv("DEFAULT_AVATAR_ID", "")
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE_ID", "")

# Ensure the data directory exists for uploads
ensure_dir("data")

def generate_video(json_file_upload, avatar_id, voice_id):
    """
    A wrapper function for your main pipeline to be called by Gradio.
    """
    if json_file_upload is None:
        raise gr.Error("Please upload a match JSON file.")
    if not avatar_id or not voice_id:
        raise gr.Error("Avatar ID and Voice ID are required.")

    # Gradio uploads a temp file. We need to save it to a
    # predictable path that main.py can read.
    uploaded_filepath = json_file_upload.name
    
    # Save the uploaded file to the data directory
    # (We can't just use the temp path, as our script expects a file)
    # Let's give it a unique name to avoid conflicts
    temp_filename = f"data/upload_{int(time.time())}_{os.path.basename(uploaded_filepath)}"
    
    with open(temp_filename, 'wb') as f_out, open(uploaded_filepath, 'rb') as f_in:
        f_out.write(f_in.read())
    
    print(f"File saved to: {temp_filename}")

    try:
        # --- This is where we call your existing code ---
        # We pass the path to the file we just saved
        # This will run the entire pipeline and return the output path
        output_video_path = main.run_commentary_pipeline(
            match_data_filepath=temp_filename,
            avatar_id=avatar_id,
            voice_id=voice_id
        )
        
        if output_video_path and os.path.exists(output_video_path):
            print(f"Pipeline finished. Output: {output_video_path}")
            # Return the path to the video file for Gradio to display
            return output_video_path
        else:
            print("Pipeline did not return a valid video path.")
            raise gr.Error("Video generation failed. Check logs.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        raise gr.Error(f"An error occurred: {e}")
    finally:
        # Clean up the uploaded file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


# --- Define the Gradio Interface ---
with gr.Blocks(title="Cricket Commentary Generator") as demo:
    gr.Markdown("# 🏏 Cricket Commentary Generator")
    gr.Markdown(
        "Upload a match JSON file (like the examples in the `data/` folder) "
        "to generate an automated video highlights package."
    )
    
    with gr.Row():
        with gr.Column(scale=1):
            json_file = gr.File(label="Upload Match JSON")
            avatar_id_input = gr.Textbox(
                label="HeyGen Avatar ID", 
                value=DEFAULT_AVATAR
            )
            voice_id_input = gr.Textbox(
                label="HeyGen Voice ID", 
                value=DEFAULT_VOICE
            )
            submit_btn = gr.Button("Generate Video", variant="primary")
            
        with gr.Column(scale=2):
            video_output = gr.Video(label="Generated Commentary")

    submit_btn.click(
        fn=generate_video,
        inputs=[json_file, avatar_id_input, voice_id_input],
        outputs=[video_output]
    )
    
    gr.Examples(
        examples=[
            ["data/980931.json", DEFAULT_AVATAR, DEFAULT_VOICE],
            ["data/980925.json", DEFAULT_AVATAR, DEFAULT_VOICE],
        ],
        inputs=[json_file, avatar_id_input, voice_id_input],
        outputs=video_output,
        fn=generate_video,
        cache_examples=False, # Set to True for faster demo, False for real runs
    )

demo.launch()