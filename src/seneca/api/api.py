import os
from flask import Flask, request, jsonify
import tempfile
import logging
from faster_whisper import WhisperModel
import whisper # Import the original whisper library to access LANGUAGES
from seneca.utils.config import config # Import the global config object
from flasgger import Swagger # Import Swagger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
api = Flask(__name__)
Swagger(api) # Initialize Swagger with the Flask app

# Initialize faster-whisper model globally to avoid reloading on each request
try:
    model = WhisperModel(
        config.whisper_model_size,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type
    )
    api.logger.info(f"Faster-Whisper model '{config.whisper_model_size}' loaded successfully on {config.whisper_device} with compute type {config.whisper_compute_type}.")
except Exception as e:
    api.logger.error(f"Failed to load Faster-Whisper model with config: size={config.whisper_model_size}, device={config.whisper_device}, compute_type={config.whisper_compute_type}. Error: {e}")
    model = None # Ensure model is None if loading fails

@api.route('/seneca/v1/stt', methods=['POST'])
def stt():
    """
    Speech-to-Text (STT) Endpoint
    This endpoint converts an audio file (WAV or MP3) to text using Faster-Whisper.
    ---
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: The audio file to transcribe (.wav or .mp3).
      - name: lang
        in: formData
        type: string
        required: false
        default: en
        description: The language code (ISO 639-1) of the audio to transcribe (e.g., 'en', 'es').
    responses:
      200:
        description: Successful transcription.
        schema:
          type: object
          properties:
            text:
              type: string
              description: The transcribed text.
      400:
        description: Bad request (e.g., no file, invalid file type).
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error (e.g., transcription failed).
        schema:
          type: object
          properties:
            error:
              type: string
      503:
        description: Service unavailable (Faster-Whisper model not loaded).
        schema:
          type: object
          properties:
            error:
              type: string
    tags:
      - Speech-to-Text
    """
    api.logger.info("STT request received.")

    if model is None:
        api.logger.error("Faster-Whisper model is not loaded. Cannot process request.")
        return jsonify({"error": "Speech-to-Text service is unavailable."}), 503

    if 'file' not in request.files:
        api.logger.error("No audio file provided in the request.")
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['file']
    if audio_file.filename == '':
        api.logger.error("No selected file in the request.")
        return jsonify({"error": "No selected file"}), 400

    api.logger.info(f"Input file name: {audio_file.filename}")

    # Validate file extension
    allowed_extensions = ['wav', 'mp3']
    filename_parts = audio_file.filename.rsplit('.', 1)
    if len(filename_parts) < 2 or filename_parts[1].lower() not in allowed_extensions:
        api.logger.error(f"Invalid file type received: {audio_file.filename}. Only .wav and .mp3 are supported.")
        return jsonify({"error": "Invalid file type. Only .wav and .mp3 are supported."}), 400

    lang = request.form.get('lang', 'en') # Default to 'en' for faster-whisper
    # Convert 'en-US' or similar to 'en' for faster-whisper
    if '-' in lang:
        lang = lang.split('-')[0]
    api.logger.info(f"Language for transcription: {lang}")

    temp_audio_file_path = None # Initialize to None for cleanup in case of early error
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename_parts[1].lower()}") as temp_audio_file:
            audio_file.save(temp_audio_file.name)
            temp_audio_file_path = temp_audio_file.name
        api.logger.info(f"Audio file saved temporarily to {temp_audio_file_path}")

        segments, info = model.transcribe(temp_audio_file_path, language=lang)
        api.logger.info(f"Detected language by Whisper: {info.language} with probability {info.language_probability:.2f}")

        full_text = ""
        for segment in segments:
            full_text += segment.text

        # Log transcription success
        truncated_text = (full_text[:100] + '...') if len(full_text) > 100 else full_text
        api.logger.info(f"Transcription successful. Text: '{truncated_text}'")

        return jsonify({"text": full_text}), 200

    except Exception as e:
        api.logger.error(f"An error occurred during faster-whisper transcription for file: {audio_file.filename}; Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if temp_audio_file_path and os.path.exists(temp_audio_file_path):
            os.remove(temp_audio_file_path) # Clean up the temporary file
            api.logger.info(f"Temporary file {temp_audio_file_path} removed.")

@api.route('/seneca/v1/stt/languages', methods=['GET'])
def get_supported_languages():
    """
    Get Supported STT Languages
    Returns a list of languages supported by the Faster-Whisper model.
    ---
    responses:
      200:
        description: A list of supported language codes and names.
        schema:
          type: array
          items:
            type: object
            properties:
              code:
                type: string
                description: ISO 639-1 language code (e.g., 'en', 'es').
              name:
                type: string
                description: Full language name (e.g., 'English', 'Spanish').
    tags:
      - Speech-to-Text
    """
    api.logger.info("Request received for supported STT languages.")
    # The 'whisper' library (original OpenAI implementation) provides a LANGUAGES dictionary.
    # Faster-whisper supports the same set of languages.
    supported_languages = [{"code": code, "name": name} for code, name in whisper.tokenizer.LANGUAGES.items()]
    return jsonify(supported_languages), 200

if __name__ == '__main__':
    api.run(debug=True)