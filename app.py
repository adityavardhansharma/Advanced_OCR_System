import os
import json
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Import OCR functions from our module
from ocr_script.ocr_function import extract_text_from_image, parse_lab_report
from ocr_script.voice_processor import VoiceProcessor
# Import our database functions from the separate file
from database import store_data_to_mongo, store_data_to_supabase

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key for production

# Configure upload folder path
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Create folder if it doesn't exist
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Initialize the voice processor
voice_processor = VoiceProcessor()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def landing():
    """Landing page with options for image or voice processing"""
    return render_template("index.html")


@app.route("/image", methods=["GET", "POST"])
def image_upload():
    """Handle image uploads and processing"""
    if request.method == "POST":
        if 'image' not in request.files:
            flash("No file part")
            return redirect(request.url)
        file = request.files["image"]
        if file.filename == "":
            flash("No file selected")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            # Extract text and parse the OCR content
            extracted_text = extract_text_from_image(file_path)
            parsed_data = parse_lab_report(extracted_text)

            # Store data in MongoDB Atlas
            mongo_id = store_data_to_mongo(parsed_data)
            # Store data in Supabase
            supabase_response = store_data_to_supabase(parsed_data)

            if mongo_id:
                flash("Data stored to MongoDB successfully!")
            else:
                flash("Error storing data to MongoDB.")

            if supabase_response:
                flash("Data stored to Supabase successfully!")
            else:
                flash("Error storing data to Supabase.")

            return render_template("result.html", parsed_data=parsed_data)
        else:
            flash("Invalid file type. Please upload a supported image file.")
            return redirect(request.url)
    return render_template("image_upload.html")


@app.route("/voice")
def voice_upload():
    """Page for voice recording"""
    return render_template("voice.html")


@app.route("/process_voice", methods=["POST"])
def process_voice():
    """Process voice recording and extract test information"""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    mime_type = request.form.get('mime_type', 'audio/webm')

    # Create a temporary file to store the audio
    extension = audio_file.filename.split('.')[-1] if '.' in audio_file.filename else 'webm'
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{extension}')
    temp_file_path = temp_file.name
    temp_file.close()

    try:
        # Save the audio file
        audio_file.save(temp_file_path)
        app.logger.info(f"Saved audio file to {temp_file_path} with mime type {mime_type}")

        # Process the audio file
        measurements = voice_processor.process_audio_file(temp_file_path, mime_type)

        # Check if there was an error
        if isinstance(measurements, dict) and "error" in measurements:
            flash(measurements["error"])
            return redirect(url_for('voice_upload'))

        # Return a JSON response for AJAX or redirect to result page
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'measurements': measurements})
        else:
            return render_template("voice_result.html", tests=measurements)

    except Exception as e:
        app.logger.error(f"Error processing voice: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': str(e)}), 500
        else:
            flash(f"Error processing voice: {str(e)}")
            return redirect(url_for('voice_upload'))

    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                app.logger.info(f"Removed temporary file: {temp_file_path}")
            except Exception as e:
                app.logger.error(f"Error removing temporary file: {str(e)}")


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('index.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    app.logger.error(f"Server error: {str(e)}")
    flash("An internal server error occurred. Please try again later.")
    return redirect(url_for('landing'))


if __name__ == "__main__":
    # Create upload directory if it doesn't exist
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # Configure logging
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    app.run(debug=True)
