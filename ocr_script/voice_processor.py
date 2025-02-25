import re
import json
import speech_recognition as sr
import spacy
from pathlib import Path
import tempfile
import subprocess
import os


class VoiceProcessor:
    def __init__(self):
        # Load model lazily when needed
        self.nlp = None

    def load_model(self):
        if self.nlp is None:
            print("Loading spaCy model...")
            try:
                self.nlp = spacy.load("en_core_sci_sm")
            except OSError:
                # If model not installed, use a more common model
                print("en_core_sci_sm not found, using en_core_web_sm")
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                except OSError:
                    # Fall back to a small English model that should be available
                    print("en_core_web_sm not found, using en_core_web_md")
                    self.nlp = spacy.load("en_core_web_md")
        return self.nlp

    def process_audio_file(self, audio_file_path, mime_type=None):
        """Process a saved audio file and extract medical measurements"""
        # Convert audio to WAV format using FFmpeg if it's not already in a compatible format
        if not audio_file_path.lower().endswith(('.wav', '.aiff', '.flac')):
            try:
                # Create temporary WAV file
                wav_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                wav_file.close()

                # Use FFmpeg to convert (if available)
                try:
                    print(f"Converting {audio_file_path} to WAV format at {wav_file.name}")
                    subprocess.run(
                        ['ffmpeg', '-i', audio_file_path, '-y', wav_file.name],
                        check=True,
                        capture_output=True
                    )
                    audio_file_path = wav_file.name
                    print(f"Conversion successful")
                except (subprocess.SubprocessError, FileNotFoundError) as e:
                    print(f"FFmpeg conversion failed: {e}")
                    # If conversion fails, try direct processing
                    print("Trying direct processing...")
            except Exception as e:
                print(f"Error creating temporary file: {e}")
                # Continue with original file

        # Process the audio file
        recognizer = sr.Recognizer()
        try:
            print(f"Opening audio file: {audio_file_path}")
            with sr.AudioFile(audio_file_path) as source:
                audio_data = recognizer.record(source)

            try:
                print("Recognizing speech with Google...")
                text = recognizer.recognize_google(audio_data, language="en-US")
                print(f"Recognized text: {text}")
                return self.extract_medical_measurements(text)
            except sr.UnknownValueError:
                print("Could not understand audio")
                return {"error": "Could not understand the audio. Please speak clearly and try again."}
            except sr.RequestError as e:
                print(f"Could not request results from Google Speech Recognition service: {e}")
                return {"error": f"Speech recognition service error: {str(e)}"}
        except Exception as e:
            print(f"Error processing audio file: {str(e)}")
            return {"error": f"Error processing audio: {str(e)}"}
        finally:
            # Clean up temporary file
            if 'wav_file' in locals() and os.path.exists(wav_file.name):
                try:
                    os.unlink(wav_file.name)
                    print(f"Removed temporary file: {wav_file.name}")
                except Exception as e:
                    print(f"Error removing temporary file: {e}")

    def extract_medical_measurements(self, text):
        """Extract test names and values from transcribed text"""
        if not text:
            return {}

        # Load spaCy model if not already loaded
        nlp = self.load_model()
        doc = nlp(text)

        # Dictionary to store results
        measurements = {}

        # Method 1: Entity recognition with value extraction
        for ent in doc.ents:
            if ent.label_ in ["CHEMICAL", "ORG", "GPE", "DISEASE", "CONDITION"]:
                # Look for numbers after the entity
                substring = text[ent.end_char:]
                match = re.search(r"(?:\s*(?:is|=|:|of)?\s*)(\d+(?:\.\d+)?)", substring)
                if match:
                    value = match.group(1)
                    key = ent.text.strip()
                    measurements[key] = value

        # Method 2: Pattern-based extraction for common lab test formats
        # Look for patterns like "X is Y" or "X level is Y" where Y is a number
        patterns = [
            r"([a-zA-Z\s]+(?:level|count|rate|pressure))\s+(?:is|was|of|:|=)\s+(\d+(?:\.\d+)?)",
            r"([a-zA-Z\s]+)\s+(?:is|was|:|=)\s+(\d+(?:\.\d+)?)",
            r"my\s+([a-zA-Z\s]+(?:level|count|rate|pressure))\s+(?:is|was|:|=)\s+(\d+(?:\.\d+)?)"
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                key = match.group(1).strip().lower()
                value = match.group(2)

                # Clean up the key - remove "my" prefix if present
                key = re.sub(r"^my\s+", "", key)

                # Avoid adding personal pronouns or common words as keys
                skip_words = ["i", "me", "my", "mine", "it", "there", "here", "that"]
                if key not in skip_words and len(key) > 2:
                    measurements[key] = value

        return measurements
