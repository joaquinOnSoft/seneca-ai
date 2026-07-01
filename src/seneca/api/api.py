import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
import json
from unittest.mock import MagicMock

import whisper
from faster_whisper import WhisperModel
from flasgger import Swagger
from flask import Flask, request, jsonify, g, has_app_context, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pythonjsonlogger.json import JsonFormatter

# --- MongoDB Imports ---
from pymongo import MongoClient
from bson.objectid import ObjectId
from pymongo.errors import ConnectionFailure, PyMongoError

from seneca.utils.config import config


# --- Structured Logging Configuration ---
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if has_app_context():
            record.correlation_id = g.get('correlation_id', 'no-correlation-id')
        else:
            record.correlation_id = 'no-app-context'  # Default for logs outside of request context
        record.service = 'seneca-api'  # Add service field to LogRecord
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

# Initialize STT model globally to avoid reloading on each request
model = None
try:
    if config.stt_backend == 'faster-whisper':
        model = WhisperModel(
            config.whisper_model_size,
            device=config.whisper_device,
            compute_type=config.whisper_compute_type
        )
        api.logger.info(
            f"Faster-Whisper model '{config.whisper_model_size}' loaded successfully on {config.whisper_device} with compute type {config.whisper_compute_type}.")
    elif config.stt_backend == 'google':
        api.logger.info("Google Web Speech STT backend selected.")
    else:
        api.logger.warning(f"Unknown STT_BACKEND '{config.stt_backend}'.")

except Exception as e:
    api.logger.error(f"Failed to load STT backend '{config.stt_backend}'. Error: {e}", exc_info=True)
    model = None

# Apply the RequestIdFilter AFTER module-level initialization that might log errors
# This ensures that logs during module import (like WhisperModel loading errors)
# do not attempt to access Flask's g before an app context is established.
api.logger.addFilter(RequestIdFilter())
api.logger.setLevel(logging.INFO)

logging.getLogger().addFilter(RequestIdFilter())
logging.getLogger().setLevel(logging.INFO)

# --- MongoDB Configuration ---
from src.seneca.api.database import MongoDatabase

db_client = MongoDatabase(config.mongodb_uri)

# Defer MongoDB connection to a function to be called within app context or mocked
def init_mongodb():
    # Only attempt to connect if not already connected and not mocked
    if isinstance(db_client, MagicMock) or getattr(db_client, '_is_mock', False):
        return

    if not db_client.is_connected():
        db_client.connect()


# Call init_mongodb before each request
@api.before_request  # Changed from before_first_request
def setup_mongodb():
    init_mongodb()


# --- Custom JSON Encoder for MongoDB ObjectId and datetime ---
class MongoJsonEncoder(json.JSONEncoder):  # Inherit from standard json.JSONEncoder
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            # Ensure datetime objects are timezone-aware for ISO format, or convert to UTC
            if obj.tzinfo is None:
                return obj.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
            return obj.isoformat().replace('+00:00', 'Z')
        return json.JSONEncoder.default(self, obj)  # Call parent's default


api.json_encoder = MongoJsonEncoder


# Helper function to recursively convert ObjectId and datetime objects in a document
def _prepare_response_data(data):
    if isinstance(data, list):
        return [_prepare_response_data(item) for item in data]
    if isinstance(data, dict):
        processed_data = {}
        for key, value in data.items():
            if isinstance(value, ObjectId):
                processed_data[key] = str(value)
            elif isinstance(value, datetime):
                if value.tzinfo is None:
                    processed_data[key] = value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
                else:
                    processed_data[key] = value.isoformat().replace('+00:00', 'Z')
            elif isinstance(value, (dict, list)):
                processed_data[key] = _prepare_response_data(value)
            else:
                processed_data[key] = value
        return processed_data
    return data


# --- Swagger Configuration ---
swagger_config = {
    "swagger": "2.0",
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,  # all in
            "model_filter": lambda tag: True,  # all in
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs",
    "securityDefinitions": {
        "APIKeyHeader": {
            "type": "apiKey",
            "name": "X-SENECA-AI-API-KEY",
            "in": "header",
            "description": "API Key required for authentication"
        }
    },
    "definitions": {
        "Message": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["user", "assistant"],
                         "description": "Role of the message sender (user or assistant)"},
                "content": {"type": "string", "description": "Content of the message"},
                "timestamp": {"type": "string", "format": "date-time",
                              "description": "ISO 8601 timestamp of the message"}
            },
            "required": ["role", "content", "timestamp"]
        },
        "ConversationSchema": {
            "type": "object",
            "properties": {
                "_id": {"type": "string", "description": "Unique identifier of the conversation (MongoDB ObjectId)"},
                "user_id": {"type": "string", "description": "ID of the user who owns the conversation"},
                "title": {"type": "string", "description": "Title of the conversation"},
                "created_at": {"type": "string", "format": "date-time",
                               "description": "ISO 8601 timestamp when the conversation was created"},
                "messages": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Message"},
                    "description": "List of messages in the conversation"
                }
            },
            "required": ["_id", "user_id", "title", "created_at", "messages"]
        },
        "NewConversationSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the new conversation"},
                "messages": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Message"},
                    "description": "Initial list of messages for the conversation"
                }
            },
            "required": ["title", "messages"]
        },
        "PartialConversationUpdateSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "New title for the conversation (optional)"},
                "messages": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Message"},
                    "description": "New list of messages to replace or append (optional). If provided, it will replace the existing messages array."
                }
            }
        }
    }
}

Swagger(api, config=swagger_config)


# --- Rate Limiting Configuration ---
def custom_key_func():
    if request.path in ['/apidocs', '/apispec_1.json'] or request.path.startswith('/flasgger_static'):
        return request.path  # Use path as key to effectively disable rate limit for these
    return get_remote_address()


limiter = Limiter(
    key_func=custom_key_func,
    default_limits=["5 per second"]
)
limiter.init_app(api)


# --- API Key Validation ---
def validate_api_key():
    # Exclude health check and Swagger UI paths from API key validation
    if request.path in ['/senecaai/v1/health', '/apidocs', '/apispec_1.json'] or request.path.startswith(
            '/flasgger_static'):
        return None  # No API key needed for these paths

    api_key = request.headers.get('X-SENECA-AI-API-KEY')
    if not api_key:
        api.logger.warning("API Key missing in request header.",
                           extra={'event': 'auth_failed', 'reason': 'missing_key'})
        return jsonify({"error": "Unauthorized: API Key missing"}), 401

    if not config.seneca_ai_api_key:
        api.logger.error("SENECA_AI_API_KEY is not configured in the application.", exc_info=True,
                         extra={'event': 'auth_error'})
        return jsonify({"error": "Server configuration error: API Key not set"}), 500

    if api_key != config.seneca_ai_api_key:
        api.logger.warning("Invalid API Key provided.", extra={'event': 'auth_failed', 'reason': 'invalid_key'})
        return jsonify({"error": "Unauthorized: Invalid API Key"}), 401

    return None  # Validation successful


# --- Request Hooks for Correlation ID and API Key Validation ---
@api.before_request
def before_request_func():
    # Explicitly bypass all before_request logic for Swagger UI and spec generation paths
    if request.path in ['/apidocs', '/apispec_1.json'] or request.path.startswith('/flasgger_static'):
        return None

    # Correlation ID handling
    correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
    g.correlation_id = correlation_id
    api.logger.info(f"Request started: {request.method} {request.path}",
                    extra={'event': 'request_start', 'method': request.method, 'path': request.path})

    # API Key validation
    validation_response = validate_api_key()
    if validation_response:
        return validation_response  # If validation fails, return the error response

    # Placeholder for g.user_id. In a real app, this would be determined by the auth system
    # after successful API key validation or user authentication.
    # For this exercise, we'll use a fixed user_id for demonstration.
    g.user_id = "test_user_123"
    api.logger.debug(f"User ID set to: {g.user_id}")


@api.after_request
def after_request_func(response):
    # Safely get correlation_id, providing a default if not set (e.g., for bypassed Swagger requests)
    correlation_id_to_log = g.get('correlation_id', 'no-correlation-id')
    response.headers['X-Correlation-ID'] = correlation_id_to_log
    api.logger.info(f"Request finished with status {response.status_code}",
                    extra={'event': 'request_end', 'status_code': response.status_code})
    return response


@api.route('/senecaai/v1/stt', methods=['POST'])
def stt():
    """
    Speech-to-Text (STT) Endpoint
    This endpoint receives an api file and transcribes it into text using Faster-Whisper.
    ---
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: "The api file to transcribe (WAV or MP3 format)."
      - name: lang
        in: formData
        type: string
        required: false
        default: en
        description: "The language of the api. e.g., 'en', 'es', 'fr'."
    security:
      - APIKeyHeader: []
    responses:
      200:
        description: "Successfully transcribed text."
        schema:
          type: object
          properties:
            text:
              type: string
              description: "The transcribed text."
      400:
        description: "Bad request, e.g., no file provided, empty file, or unsupported file type."
      401:
        description: "Unauthorized: API Key missing or invalid."
      503:
        description: "Service unavailable, Faster-Whisper model not loaded."
      500:
        description: "Internal server error during transcription."
    """
    api.logger.info("STT request received.")

    if config.stt_backend == 'faster-whisper' and model is None:
        api.logger.error("Faster-Whisper model is not loaded. Cannot process request.")
        return jsonify({"error": "Speech-to-Text service is unavailable."}), 503

    if 'file' not in request.files:
        api.logger.error("No api file provided in the request.")
        return jsonify({"error": "No api file provided"}), 400

    audio_file = request.files['file']
    if audio_file.filename == '':
        api.logger.error("No selected file in the request.")
        return jsonify({"error": "No selected file"}), 400

    audio_file.seek(0, os.SEEK_END)
    file_size = audio_file.tell()
    audio_file.seek(0)
    if file_size == 0:
        api.logger.error("Received an empty api file.")
        return jsonify({"error": "Empty api file"}), 400

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

        if config.stt_backend == 'faster-whisper':
            segments, info = model.transcribe(temp_audio_file_path, language=lang)
            api.logger.info(
                f"Detected language by Whisper: {info.language} with probability {info.language_probability:.2f}")
            full_text = "".join([segment.text for segment in segments])
        elif config.stt_backend == 'google':
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(temp_audio_file_path) as source:
                audio_data = recognizer.record(source)
            full_text = recognizer.recognize_google(audio_data, language=lang)
        else:
            api.logger.error(f"Unsupported STT backend: {config.stt_backend}")
            return jsonify({"error": "Unsupported STT backend configured."}), 500

        truncated_text = (full_text[:100] + '...') if len(full_text) > 100 else full_text
        api.logger.info(f"Transcription successful. Text: '{truncated_text}'")

        return jsonify({"text": full_text}), 200

    except Exception as e:
        api.logger.error(f"An error occurred during faster-whisper transcription for file: {audio_file.filename}.",
                         exc_info=True)
        return jsonify({"error": "An internal server error occurred during transcription."}), 500
    finally:
        if temp_audio_file_path and os.path.exists(temp_audio_file_path):
            os.remove(temp_audio_file_path)
            api.logger.info(f"Temporary file {temp_audio_file_path} removed.")


@api.route('/senecaai/v1/stt/languages', methods=['GET'])
def get_supported_languages():
    """
    Get Supported STT Languages
    Returns a list of languages supported by the Speech-to-Text service.
    ---
    security:
      - APIKeyHeader: []
    responses:
      200:
        description: "A list of supported languages."
        schema:
          type: array
          items:
            type: object
            properties:
              code:
                type: string
                description: "The language code (e.g., 'en', 'es')."
              name:
                type: string
                description: "The full name of the language (e.g., 'English', 'Spanish')."
      401:
        description: "Unauthorized: API Key missing or invalid."
    """
    api.logger.info("Request received for supported STT languages.")
    supported_languages = [{"code": code, "name": name} for code, name in whisper.tokenizer.LANGUAGES.items()]
    return jsonify(supported_languages), 200


@api.route('/senecaai/v1/health', methods=['GET'])
def health_check():
    """
    Health Check Endpoint
    Checks the health of the API and the Faster-Whisper model.
    ---
    responses:
      200:
        description: "API is healthy and model is loaded."
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
        description: "API is degraded, Faster-Whisper model is not loaded."
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
    if config.stt_backend == 'google':
        return jsonify({"status": "ok", "model_status": "google_online"}), 200
    elif config.stt_backend == 'faster-whisper' and model is not None:
        return jsonify({"status": "ok", "model_status": "loaded"}), 200
    else:
        api.logger.warning("Health check: Faster-Whisper model is not loaded or backend is unsupported.")
        return jsonify({"status": "degraded", "model_status": "not loaded"}), 503


# --- Conversation Management Endpoints ---

def validate_message_structure(messages):
    """Helper function to validate the structure of messages."""
    if not isinstance(messages, list):
        return False, "Messages must be a list."
    for msg in messages:
        if not isinstance(msg, dict) or not all(k in msg for k in ['role', 'content', 'timestamp']):
            return False, "Each message must have 'role', 'content', and 'timestamp'."
        if not isinstance(msg['role'], str) or msg['role'] not in ["user", "assistant"]:
            return False, "Message role must be 'user' or 'assistant'."
        if not isinstance(msg['content'], str):
            return False, "Message content must be a string."
        if not isinstance(msg['timestamp'], str):
            return False, "Message timestamp must be a string."
        try:
            # Attempt to parse to validate format
            datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            return False, "Message timestamp must be in ISO 8601 format."
    return True, None


@api.route('/senecaai/v1/conversations', methods=['GET'])
def get_conversations():
    """
    Get User Conversations
    Retrieves a paginated list of conversations for the authenticated user.
    ---
    parameters:
      - name: convPerPage
        in: query
        type: integer
        required: false
        default: 20
        description: "Number of conversations per page."
      - name: numPage
        in: query
        type: integer
        required: false
        default: 1
        description: "Page number (1-based)."
    security:
      - APIKeyHeader: []
    responses:
      200:
        description: "List of user conversations."
        schema:
          type: array
          items:
            $ref: '#/definitions/ConversationSchema'
      400:
        description: "Bad Request: Invalid pagination parameters."
      401:
        description: "Unauthorized: API Key missing or invalid."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info(f"Request to get conversations for user: {g.user_id}")
    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        return jsonify({"error": "Database service unavailable."}), 500

    try:
        conv_per_page = int(request.args.get('convPerPage', 20))
        num_page = int(request.args.get('numPage', 1))

        if conv_per_page <= 0 or num_page <= 0:
            return jsonify({"error": "convPerPage and numPage must be positive integers."}), 400

        skip = (num_page - 1) * conv_per_page
        limit = conv_per_page

        conversations = db_client.get_conversations(g.user_id, skip=skip, limit=limit)

        api.logger.info(f"Found {len(conversations)} conversations for user {g.user_id} on page {num_page}.")
        # Use json.dumps with custom encoder and then Response to ensure correct serialization
        return Response(json.dumps(_prepare_response_data(conversations), cls=MongoJsonEncoder),
                        mimetype='application/json'), 200
    except ValueError:
        api.logger.error("Invalid pagination parameters provided.", exc_info=True)
        return jsonify({"error": "Invalid pagination parameters. convPerPage and numPage must be integers."}), 400
    except PyMongoError as e:
        api.logger.error(f"MongoDB error while fetching conversations: {e}", exc_info=True)
        return jsonify({"error": "Database error while fetching conversations."}), 500
    except Exception as e:
        api.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@api.route('/senecaai/v1/conversations/<_id>', methods=['GET'])
def get_conversation_by_id(_id):
    """
    Get Specific Conversation
    Retrieves a specific conversation by its ID for the authenticated user.
    ---
    parameters:
      - name: _id
        in: path
        type: string
        required: true
        description: "Unique identifier of the conversation (MongoDB ObjectId)."
    security:
      - APIKeyHeader: []
    responses:
      200:
        description: "The requested conversation."
        schema:
          $ref: '#/definitions/ConversationSchema'
      400:
        description: "Bad Request: Invalid conversation ID format."
      401:
        description: "Unauthorized: API Key missing or invalid."
      403:
        description: "Forbidden: User does not have access to this conversation."
      404:
        description: "Not Found: Conversation with the given ID not found."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info(f"Request to get conversation with _id: {_id} for user: {g.user_id}")
    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        return jsonify({"error": "Database service unavailable."}), 500

    try:
        if not ObjectId.is_valid(_id):
            api.logger.warning(f"Invalid ObjectId format for _id: {_id}")
            return jsonify({"error": "Invalid conversation ID format."}), 400

        conversation = db_client.get_conversation_by_id(_id, user_id=g.user_id)

        if not conversation:
            # Check if it exists but belongs to another user
            if db_client.check_conversation_exists(_id):
                api.logger.warning(f"User {g.user_id} attempted to access conversation {_id} owned by another user.")
                return jsonify({"error": "Forbidden: User does not have access to this conversation."}), 403
            api.logger.info(f"Conversation with _id: {_id} not found for user: {g.user_id}")
            return jsonify({"error": "Conversation not found."}), 404

        api.logger.info(f"Conversation {_id} retrieved successfully for user {g.user_id}.")
        # Use json.dumps with custom encoder and then Response to ensure correct serialization
        return Response(json.dumps(_prepare_response_data(conversation), cls=MongoJsonEncoder),
                        mimetype='application/json'), 200
    except PyMongoError as e:
        api.logger.error(f"MongoDB error while fetching conversation {_id}: {e}", exc_info=True)
        return jsonify({"error": "Database error while fetching conversation."}), 500
    except Exception as e:
        api.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@api.route('/senecaai/v1/conversations', methods=['POST'])
def create_conversation():
    """
    Create New Conversation
    Creates a new conversation for the authenticated user.
    The _id and created_at fields will be generated by the server.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/NewConversationSchema'
    security:
      - APIKeyHeader: []
    responses:
      201:
        description: "The conversation created successfully."
        schema:
          $ref: '#/definitions/ConversationSchema'
        headers:
          Location:
            type: string
            description: "URL of the newly created resource."
      400:
        description: "Bad Request: Invalid conversation data provided."
      401:
        description: "Unauthorized: API Key missing or invalid."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info(f"Request to create new conversation for user: {g.user_id}")

    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        return jsonify({"error": "Database service unavailable."}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No input data provided."}), 400

        title = data.get('title')
        messages = data.get('messages')

        if not title or not isinstance(title, str):
            return jsonify({"error": "Title is required and must be a string."}), 400

        is_valid_messages, error_msg = validate_message_structure(messages)
        if not is_valid_messages:
            return jsonify({"error": error_msg}), 400

        new_conversation = db_client.create_conversation(g.user_id, title, messages)

        location_header = f"{request.url}/{new_conversation['_id']}"
        api.logger.info(f"Conversation created successfully with _id: {new_conversation['_id']} for user {g.user_id}.")
        # Use json.dumps with custom encoder and then Response to ensure correct serialization
        return Response(json.dumps(_prepare_response_data(new_conversation), cls=MongoJsonEncoder),
                        mimetype='application/json'), 201, {'Location': location_header}
    except PyMongoError as e:
        api.logger.error(f"MongoDB error while creating conversation: {e}", exc_info=True)
        return jsonify({"error": "Database error while creating conversation."}), 500
    except Exception as e:
        api.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@api.route('/senecaai/v1/conversations/<_id>', methods=['PATCH'])
def update_conversation(_id):
    """
    Update Existing Conversation
    Partially updates an existing conversation identified by its ID for the authenticated user.
    Allows updating fields like 'title' or replacing the 'messages' array.
    ---
    parameters:
      - name: _id
        in: path
        type: string
        required: true
        description: "Unique identifier of the conversation (MongoDB ObjectId)."
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/PartialConversationUpdateSchema'
    security:
      - APIKeyHeader: []
    responses:
      200:
        description: "The updated conversation."
        schema:
          $ref: '#/definitions/ConversationSchema'
      400:
        description: "Bad Request: Invalid update data provided or invalid conversation ID format."
      401:
        description: "Unauthorized: API Key missing or invalid."
      403:
        description: "Forbidden: User does not have access to modify this conversation."
      404:
        description: "Not Found: Conversation with the given ID not found."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info(f"Request to update conversation with _id: {_id} for user: {g.user_id}")
    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        return jsonify({"error": "Database service unavailable."}), 500

    try:
        if not ObjectId.is_valid(_id):
            api.logger.warning(f"Invalid ObjectId format for _id: {_id}")
            return jsonify({"error": "Invalid conversation ID format."}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "No update data provided."}), 400

        update_fields = {}
        if 'title' in data:
            if not isinstance(data['title'], str):
                return jsonify({"error": "Title must be a string."}), 400
            update_fields['title'] = data['title']

        if 'messages' in data:
            is_valid_messages, error_msg = validate_message_structure(data['messages'])
            if not is_valid_messages:
                return jsonify({"error": error_msg}), 400
            update_fields['messages'] = data['messages']

        if not update_fields:
            return jsonify({"error": "No valid fields to update provided (e.g., 'title', 'messages')."}), 400

        updated = db_client.update_conversation(_id, g.user_id, update_fields)

        if not updated:
            # Check if it exists but belongs to another user
            if db_client.check_conversation_exists(_id):
                api.logger.warning(f"User {g.user_id} attempted to update conversation {_id} owned by another user.")
                return jsonify({"error": "Forbidden: User does not have access to modify this conversation."}), 403

            api.logger.info(f"Conversation with _id: {_id} not found for user: {g.user_id}")
            return jsonify({"error": "Conversation not found."}), 404

        updated_conversation = db_client.get_conversation_by_id(_id)
        api.logger.info(f"Conversation {_id} updated successfully for user {g.user_id}.")
        # Use json.dumps with custom encoder and then Response to ensure correct serialization
        return Response(json.dumps(_prepare_response_data(updated_conversation), cls=MongoJsonEncoder),
                        mimetype='application/json'), 200
    except PyMongoError as e:
        api.logger.error(f"MongoDB error while updating conversation {_id}: {e}", exc_info=True)
        return jsonify({"error": "Database error while updating conversation."}), 500
    except Exception as e:
        api.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


if __name__ == '__main__':
    from urllib.parse import urlparse
    from waitress import serve

    _parsed = urlparse(config.seneca_api_base_url)
    _host = _parsed.hostname or "0.0.0.0"
    _port = _parsed.port or 1414
    serve(api, host="0.0.0.0", port=_port)