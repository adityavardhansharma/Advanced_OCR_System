import os
import json
import tempfile
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from bson import ObjectId

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# Import OCR and voice processing functions
from ocr_script.ocr_function import extract_text_from_image, parse_lab_report
from ocr_script.voice_processor import VoiceProcessor

# Import our database and authentication functions
from database import db, supabase, store_test_result, get_user_test_results
from auth import register_user, login_user, logout_user, is_logged_in, get_logged_in_user

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# Initialize voice processor
voice_processor = VoiceProcessor()


# Custom JSON encoder (for API responses)
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(MongoJSONEncoder, self).default(obj)


app.json_encoder = MongoJSONEncoder


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route("/")
def landing():
    return render_template("index.html", user=get_logged_in_user(db) if is_logged_in() else None)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if is_logged_in():
        return redirect(url_for('profile'))
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        age = request.form.get('age')
        gender = request.form.get('gender')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('signup'))

        success, message = register_user(name, email, age, gender, mobile, password, db, supabase)
        if success:
            flash(f'Registration successful! Your ID is {message}', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')
            return redirect(url_for('signup'))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect(url_for('profile'))
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        success, message = login_user(email, password, db)
        if success:
            flash('Login successful!', 'success')
            return redirect(url_for('profile'))
        else:
            flash(message, 'error')
            return redirect(url_for('login'))
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('landing'))


@app.route("/profile")
@login_required
def profile():
    user = get_logged_in_user(db)
    test_results = get_user_test_results(user['_id'], db)
    return render_template("profile.html", user=user, test_results=test_results)


@app.route("/image", methods=["GET", "POST"])
@login_required
def image_upload():
    if request.method == "POST":
        if 'image' not in request.files:
            flash("No file part", "error")
            return redirect(request.url)
        file = request.files["image"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            try:
                # Extract text by OCR and then parse only the test results.
                extracted_text = extract_text_from_image(file_path)
                test_results = parse_lab_report(extracted_text)

                # Save the test results using the registration details from the user record.
                user_id = ObjectId(session['user_id'])
                mongo_id, supabase_response = store_test_result(user_id, test_results, db, supabase)

                if mongo_id:
                    flash("Test results stored successfully!", "success")
                    # Pass only the tests part to the template
                    return render_template("result.html", test_results=test_results.get("tests", {}),
                                           user=get_logged_in_user(db))
                else:
                    flash("Error storing test results.", "error")
                    return redirect(request.url)
            except Exception as e:
                logger.error(f"Error processing image: {e}")
                flash(f"Error processing image: {str(e)}", "error")
                return redirect(request.url)
        else:
            flash("Invalid file type. Please upload a supported image file.", "error")
            return redirect(request.url)
    return render_template("image_upload.html", user=get_logged_in_user(db))


@app.route("/voice")
@login_required
def voice_upload():
    return render_template("voice.html", user=get_logged_in_user(db))


@app.route("/process_voice", methods=["POST"])
@login_required
def process_voice():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    mime_type = request.form.get('mime_type', 'audio/webm')
    extension = audio_file.filename.split('.')[-1] if '.' in audio_file.filename else 'webm'

    # Create a temporary file to store the audio
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{extension}')
    temp_file_path = temp_file.name
    temp_file.close()

    try:
        # Save the uploaded audio to the temporary file
        audio_file.save(temp_file_path)
        logger.info(f"Saved audio file to {temp_file_path} with mime type {mime_type}")

        # Process the audio file to extract test results
        test_results = voice_processor.process_audio_file(temp_file_path, mime_type)

        # Check if there was an error in processing
        if isinstance(test_results, dict) and "error" in test_results:
            flash(test_results["error"], "error")
            return redirect(url_for('voice_upload'))

        # Store the test results in the database
        user_id = ObjectId(session['user_id'])
        mongo_id, supabase_response = store_test_result(user_id, test_results, db, supabase)

        if mongo_id:
            flash("Voice test results stored successfully!", "success")
        else:
            flash("Error storing voice test results.", "error")
            return redirect(url_for('voice_upload'))

        # Return the results based on the request type
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'test_results': test_results.get("tests", {})})
        else:
            return render_template("voice_result.html", tests=test_results.get("tests", {}),
                                   user=get_logged_in_user(db))

    except Exception as e:
        logger.error(f"Error processing voice: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': str(e)}), 500
        else:
            flash(f"Error processing voice: {str(e)}", "error")
            return redirect(url_for('voice_upload'))

    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Removed temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error removing temporary file: {str(e)}")


@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html', user=get_logged_in_user(db) if is_logged_in() else None), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {str(e)}")
    flash("An internal server error occurred. Please try again later.", "error")
    return redirect(url_for('landing'))


@app.context_processor
def inject_user():
    """Make current_user available to all templates"""
    if is_logged_in():
        return {'current_user': get_logged_in_user(db)}
    return {'current_user': None}


if __name__ == "__main__":
    # Ensure upload directory exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # Run the Flask app
    app.run(debug=True)
