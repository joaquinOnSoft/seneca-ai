import logging
import os
import sys
import tempfile
import uuid

import whisper
from faster_whisper import WhisperModel
from flasgger import Swagger
from flask import Flask, request, jsonify, g, has_app_context
from pythonjsonlogger.json import JsonFormatter

from seneca.utils.config import config


# --- Structured Logging Configuration ---
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if has_app_context():
            record.correlation_id = g.get('correlation_id', 'no-correlation-id')
        else:
            record.correlation_id = 'no-app-context' # Default for logs outside of request context
        record.service = 'seneca-api' # Add service field to LogRecord
        return True

# Initialize Flask app here to ensure api.logger is available for configuration
api = Flask(__name__)

# Remove default Flask handlers to avoid duplicate logs and format conflicts
# This needs to be done after Flask app initialization
for handler in list(api.logger.handlers):
    api.logger.removeHandler(handler)
for handler in list(logging.getLogger().handlers):
    logging.getLogger().removeHandler(handler)

# Configure JSON formatter
formatter = JsonFormatter(
    fmt='%(levelname)s %(message)s %(asctime)s %(module)s %(funcName)s %(lineno)d %(pathname)s',
    rename_fields={
        'levelname': 'level',
        'message': 'message',
        'asctime': 'timestamp',
        'module': 'module',
        'funcName': 'funcName',
        'lineno': 'lineno',
        'pathname': 'pathname'
    }
)

# Configure stream handler for console output
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

# Apply the handler to the Flask app logger and root logger
api.logger.addHandler(handler)
logging.getLogger().addHandler(handler)

# Initialize faster-whisper model globally to avoid reloading on each request
try:
    model = WhisperModel(
        config.whisper_model_size,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type
    )
    api.logger.info(f"Faster-Whisper model '{config.whisper_model_size}' loaded successfully on {config.whisper_device} with compute type {config.whisper_compute_type}.")
except Exception as e:
    api.logger.error(f"Failed to load Faster-Whisper model with config: size={config.whisper_model_size}, device={config.whisper_device}, compute_type={config.whisper_compute_type}. Error: {e}", exc_info=True)
    model = None

# Apply the RequestIdFilter AFTER module-level initialization that might log errors
# This ensures that logs during module import (like WhisperModel loading errors)
# do not attempt to access Flask's g before an app context is established.
api.logger.addFilter(RequestIdFilter())
api.logger.setLevel(logging.INFO)

logging.getLogger().addFilter(RequestIdFilter())
logging.getLogger().setLevel(logging.INFO)

Swagger(api)

# --- Request Hooks for Correlation ID ---
@api.before_request
def before_request_func():
    correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
    g.correlation_id = correlation_id
    api.logger.info(f"Request started: {request.method} {request.path}", extra={'event': 'request_start', 'method': request.method, 'path': request.path})

@api.after_request
def after_request_func(response):
    response.headers['X-Correlation-ID'] = g.correlation_id
    api.logger.info(f"Request finished with status {response.status_code}", extra={'event': 'request_end', 'status_code': response.status_code})
    return response

@api.route('/seneca/v1/stt', methods=['POST'])
def stt():
    """
    Speech-to-Text (STT) Endpoint
    This endpoint receives an audio file and transcribes it into text using Faster-Whisper.
    ---
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: The audio file to transcribe (WAV or MP3 format).
      - name: lang
        in: formData
        type: string
        required: false
        default: en
        description: The language of the audio. e.g., 'en', 'es', 'fr'.
    responses:
      200:
        description: Successfully transcribed text.
        schema:
          type: object
          properties:
            text:
              type: string
              description: The transcribed text.
      400:
        description: Bad request, e.g., no file provided, empty file, or unsupported file type.
      503:
        description: Service unavailable, Faster-Whisper model not loaded.
      500:
        description: Internal server error during transcription.
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

    audio_file.seek(0, os.SEEK_END)
    file_size = audio_file.tell()
    audio_file.seek(0)
    if file_size == 0:
        api.logger.error("Received an empty audio file.")
        return jsonify({"error": "Empty audio file"}), 400

    api.logger.info(f"Input file name: {audio_file.filename}")

    allowed_extensions = ['wav', 'mp3']
    filename_parts = audio_file.filename.rsplit('.', 1)
    if len(filename_parts) < 2 or filename_parts[1].lower() not in allowed_extensions:
        api.logger.error(f"Invalid file type received: {audio_file.filename}. Only .wav and .mp3 are supported.")
        return jsonify({"error": "Invalid file type. Only .wav and .mp3 are supported."}), 400

    lang = request.form.get('lang', 'en')
    if '-' in lang:
        lang = lang.split('-')[0]
    api.logger.info(f"Language for transcription: {lang}")

    temp_audio_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename_parts[1].lower()}") as temp_audio_file:
            audio_file.save(temp_audio_file.name)
            temp_audio_file_path = temp_audio_file.name
        api.logger.info(f"Audio file saved temporarily to {temp_audio_file_path}")

        segments, info = model.transcribe(temp_audio_file_path, language=lang)
        api.logger.info(f"Detected language by Whisper: {info.language} with probability {info.language_probability:.2f}")

        full_text = "".join([segment.text for segment in segments])

        truncated_text = (full_text[:100] + '...') if len(full_text) > 100 else full_text
        api.logger.info(f"Transcription successful. Text: '{truncated_text}'")

        return jsonify({"text": full_text}), 200

    except Exception as e:
        api.logger.error(f"An error occurred during faster-whisper transcription for file: {audio_file.filename}.", exc_info=True)
        return jsonify({"error": "An internal server error occurred during transcription."}), 500
    finally:
        if temp_audio_file_path and os.path.exists(temp_audio_file_path):
            os.remove(temp_audio_file_path)
            api.logger.info(f"Temporary file {temp_audio_file_path} removed.")

@api.route('/seneca/v1/stt/languages', methods=['GET'])
def get_supported_languages():
    """
    Get Supported STT Languages
    Returns a list of languages supported by the Speech-to-Text service.
    ---
    responses:
      200:
        description: A list of supported languages.
        schema:
          type: array
          items:
            type: object
            properties:
              code:
                type: string
                description: The language code (e.g., 'en', 'es').
              name:
                type: string
                description: The full name of the language (e.g., 'English', 'Spanish').
    """
    api.logger.info("Request received for supported STT languages.")
    supported_languages = [{"code": code, "name": name} for code, name in whisper.tokenizer.LANGUAGES.items()]
    return jsonify(supported_languages), 200

@api.route('/seneca/v1/health', methods=['GET'])
def health_check():
    """
    Health Check Endpoint
    Checks the health of the API and the Faster-Whisper model.
    ---
    responses:
      200:
        description: API is healthy and model is loaded.
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [ok]
            model_status:
              type: string
              enum: [loaded]
      503:
        description: API is degraded, Faster-Whisper model is not loaded.
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [degraded]
            model_status:
              type: string
              enum: [not loaded]
    """
    api.logger.info("Health check request received.")
    if model is not None:
        return jsonify({"status": "ok", "model_status": "loaded"}), 200
    else:
        api.logger.warning("Health check: Faster-Whisper model is not loaded.")
        return jsonify({"status": "degraded", "model_status": "not loaded"}), 503

if __name__ == '__main__':
    from waitress import serve
    serve(api, host="0.0.0.0", port=1414)