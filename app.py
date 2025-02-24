import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Import OCR functions from our module
from ocr_script.ocr_function import extract_text_from_image, parse_lab_report
# Import our database functions from the separate file
from database import store_data_to_mongo, store_data_to_supabase

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key for production

# Configure upload folder path
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET", "POST"])
def index():
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
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
