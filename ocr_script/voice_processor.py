import re
import json
import logging
import speech_recognition as sr
import spacy
from pathlib import Path
import tempfile
import subprocess
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VoiceProcessor:
    def __init__(self):
        # Load model lazily when needed
        self.nlp = None

    def load_model(self):
        if self.nlp is None:
            logger.info("Loading spaCy model...")
            try:
                self.nlp = spacy.load("en_core_sci_sm")
                logger.info("Loaded en_core_sci_sm model")
            except OSError:
                # If model not installed, use a more common model
                logger.info("en_core_sci_sm not found, using en_core_web_sm")
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                    logger.info("Loaded en_core_web_sm model")
                except OSError:
                    # Fall back to a small English model that should be available
                    logger.info("en_core_web_sm not found, using en_core_web_md")
                    self.nlp = spacy.load("en_core_web_md")
                    logger.info("Loaded en_core_web_md model")
        return self.nlp

    def process_audio_file(self, audio_file_path, mime_type=None):
        """Process a saved audio file and extract medical measurements"""
        temp_files = []  # Track temporary files for cleanup

        try:
            # Convert audio to WAV format using FFmpeg if it's not already in a compatible format
            if not audio_file_path.lower().endswith(('.wav', '.aiff', '.flac')):
                try:
                    # Create temporary WAV file
                    wav_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                    wav_file.close()
                    temp_files.append(wav_file.name)

                    # Use FFmpeg to convert (if available)
                    try:
                        logger.info(f"Converting {audio_file_path} to WAV format at {wav_file.name}")
                        subprocess.run(
                            ['ffmpeg', '-i', audio_file_path, '-y', wav_file.name],
                            check=True,
                            capture_output=True
                        )
                        audio_file_path = wav_file.name
                        logger.info(f"Conversion successful")
                    except (subprocess.SubprocessError, FileNotFoundError) as e:
                        logger.error(f"FFmpeg conversion failed: {e}")
                        # If conversion fails, try direct processing
                        logger.info("Trying direct processing...")
                except Exception as e:
                    logger.error(f"Error creating temporary file: {e}")
                    # Continue with original file

            # Process the audio file
            recognizer = sr.Recognizer()
            try:
                logger.info(f"Opening audio file: {audio_file_path}")
                with sr.AudioFile(audio_file_path) as source:
                    audio_data = recognizer.record(source)

                try:
                    logger.info("Recognizing speech with Google...")
                    text = recognizer.recognize_google(audio_data, language="en-US")
                    logger.info(f"Recognized text: {text}")

                    # Extract medical measurements and add source information
                    measurements = self.extract_medical_measurements(text)
                    return {
                        "tests": measurements,
                        "source": "voice"
                    }
                except sr.UnknownValueError:
                    logger.error("Could not understand audio")
                    return {"error": "Could not understand the audio. Please speak clearly and try again."}
                except sr.RequestError as e:
                    logger.error(f"Could not request results from Google Speech Recognition service: {e}")
                    return {"error": f"Speech recognition service error: {str(e)}"}
            except Exception as e:
                logger.error(f"Error processing audio file: {str(e)}")
                return {"error": f"Error processing audio: {str(e)}"}
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                        logger.info(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.error(f"Error removing temporary file: {e}")

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
