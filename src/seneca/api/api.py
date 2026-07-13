import json
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from http import HTTPStatus  # Import HTTPStatus for standard status codes

import jwt
import whisper
from bson.objectid import ObjectId
from faster_whisper import WhisperModel
from flasgger import Swagger
from flask import Flask, request, jsonify, g, has_app_context, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from passlib.hash import bcrypt
from pymongo.errors import PyMongoError
from pythonjsonlogger.json import JsonFormatter

from seneca.api.database import MongoDatabase
from seneca.utils.config import config
from seneca.utils.passlib_bcrypt_fix import _passlib_bcrypt_module  # noqa: F401

H265 = "HS256"


# --- Custom Exception Classes ---
class ApiException(Exception):
    """Base class for API exceptions."""
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

class BadRequestError(ApiException):
    status_code = HTTPStatus.BAD_REQUEST

class UnauthorizedError(ApiException):
    status_code = HTTPStatus.UNAUTHORIZED

class ForbiddenError(ApiException):
    status_code = HTTPStatus.FORBIDDEN

class NotFoundError(ApiException):
    status_code = HTTPStatus.NOT_FOUND

class ServiceUnavailableError(ApiException):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE

class InternalServerError(ApiException):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR


# --- Structured Logging Configuration ---
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if has_app_context():
            record.correlation_id = g.get('correlation_id', 'no-correlation-id')
        else:
            record.correlation_id = 'no-app-context'
        record.service = 'seneca-api'
        return True


# Initialize Flask app here to ensure api.logger is available for configuration
api = Flask(__name__)

# Remove default Flask handlers to avoid duplicate logs and format conflicts
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
api.logger.addFilter(RequestIdFilter())
api.logger.setLevel(logging.INFO)

logging.getLogger().addFilter(RequestIdFilter())
logging.getLogger().setLevel(logging.INFO)

# --- MongoDB Configuration ---
db_client = MongoDatabase(config.mongodb_uri)

# Defer MongoDB connection to a function to be called within app context or mocked
def init_mongodb():
    if getattr(db_client, '_is_mock', False):
        return
    if not db_client.is_connected():
        db_client.connect()

@api.before_request
def setup_mongodb():
    init_mongodb()

# --- Custom JSON Encoder for MongoDB ObjectId and datetime ---
class MongoJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                return obj.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
            return obj.isoformat().replace('+00:00', 'Z')
        return json.JSONEncoder.default(self, obj)

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

def validate_message_structure(messages):
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
            datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            return False, "Message timestamp must be in ISO 8601 format."
    return True, None


# --- JWT and Refresh Token Utilities ---
def generate_jwt(user_id, user_name, expires_in_seconds=config.jwt_access_token_expires_in):
    payload = {
        "user_id": user_id,
        "user_name": user_name,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, config.jwt_secret_key, algorithm=H265)

def decode_jwt(token):
    try:
        return jwt.decode(token, config.jwt_secret_key, algorithms=[H265])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")

def generate_refresh_token():
    return str(uuid.uuid4())

def hash_refresh_token(token):
    return bcrypt.hash(token)

def verify_refresh_token(token, hashed_token):
    return bcrypt.verify(token, hashed_token)


# --- Swagger Configuration ---
swagger_config = {
    "swagger": "2.0",
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
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
            "description": "API Key required for authentication (for specific integrations)"
        },
        "BearerAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Access Token (Bearer <token>)"
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
        },
        "AuthLoginSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "User's username"},
                "password": {"type": "string", "description": "User's password"}
            },
            "required": ["username", "password"]
        },
        "AuthTokensSchema": {
            "type": "object",
            "properties": {
                "access_token": {"type": "string", "description": "JWT Access Token"},
                "refresh_token": {"type": "string", "description": "Refresh Token (use for /auth/refresh)"},
                "token_type": {"type": "string", "enum": ["Bearer"], "default": "Bearer"},
                "expires_in": {"type": "integer", "description": "Access Token expiration time in seconds"}
            },
            "required": ["access_token", "token_type", "expires_in"]
        },
        "RefreshTokenResponseSchema": {
            "type": "object",
            "properties": {
                "access_token": {"type": "string", "description": "New JWT Access Token"},
                "token_type": {"type": "string", "enum": ["Bearer"], "default": "Bearer"},
                "expires_in": {"type": "integer", "description": "Access Token expiration time in seconds"}
            },
            "required": ["access_token", "token_type", "expires_in"]
        }
    }
}

Swagger(api, config=swagger_config)


# --- Rate Limiting Configuration ---
def custom_key_func():
    if request.path in ['/apidocs', '/apispec_1.json'] or request.path.startswith('/flasgger_static'):
        return request.path
    return get_remote_address()


limiter = Limiter(
    key_func=custom_key_func,
    default_limits=["5 per second"]
)
limiter.init_app(api)


# --- Error Handlers ---
@api.errorhandler(ApiException)
def handle_api_exception(error):
    api.logger.error(f"API Exception: {error.message}", exc_info=True, extra={'event': 'api_exception', 'status_code': error.status_code})
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@api.errorhandler(PyMongoError)
def handle_mongo_error(error):
    api.logger.error(f"MongoDB Error: {error}", exc_info=True, extra={'event': 'mongodb_error'})
    response = jsonify({"error": "Database error occurred."})
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    return response

@api.errorhandler(Exception)
def handle_general_exception(error):
    api.logger.error(f"Unhandled Exception: {error}", exc_info=True, extra={'event': 'unhandled_exception'})
    response = jsonify({"error": "An unexpected internal server error occurred."})
    response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    return response


# --- API Key Validation (for specific integrations, secondary to JWT) ---
def validate_api_key():
    api_key = request.headers.get('X-SENECA-AI-API-KEY')
    if not api_key:
        return None

    if not config.seneca_ai_api_key:
        api.logger.error("SENECA_AI_API_KEY is not configured in the application.", exc_info=True,
                         extra={'event': 'auth_error'})
        raise InternalServerError("Server configuration error: API Key not set")

    if api_key != config.seneca_ai_api_key:
        api.logger.warning("Invalid API Key provided.", extra={'event': 'auth_failed', 'reason': 'invalid_key'})
        raise UnauthorizedError("Unauthorized: Invalid API Key")
    
    g.user_id = "api_key_user"
    g.user_name = "api_key_user"
    return None


# --- Request Hooks for Correlation ID and Authentication ---
@api.before_request
def before_request_func():
    if request.path in ['/apidocs', '/apispec_1.json', '/senecaai/v1/health'] or request.path.startswith('/flasgger_static'):
        return None

    correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
    g.correlation_id = correlation_id
    api.logger.info(f"Request started: {request.method} {request.path}",
                    extra={'event': 'request_start', 'method': request.method, 'path': request.path})

    if request.path in ['/senecaai/v1/auth/login', '/senecaai/v1/auth/refresh', '/senecaai/v1/auth/logout']:
        return None

    # --- Authentication Logic ---
    auth_header = request.headers.get('Authorization')
    
    try:
        validate_api_key() # This will raise if API key is invalid or misconfigured
    except ApiException as e:
        raise e # Re-raise to be caught by error handler
    
    if g.get('user_id'): # If API Key was valid and set user_id
        return None

    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            decoded_token = decode_jwt(token) # This will raise UnauthorizedError on failure
        except UnauthorizedError as e:
            api.logger.warning(f"JWT authentication failed: {e.message}", extra={'event': 'auth_failed', 'reason': e.message})
            raise e
        
        g.user_id = decoded_token['user_id']
        g.user_name = decoded_token['user_name']
        api.logger.debug(f"User {g.user_name} authenticated via JWT.")
        return None
    
    api.logger.warning("Authentication required: No valid API Key or JWT provided.", extra={'event': 'auth_failed', 'reason': 'no_auth_provided'})
    raise UnauthorizedError("Authentication required")


@api.after_request
def after_request_func(response):
    correlation_id_to_log = g.get('correlation_id', 'no-correlation-id')
    response.headers['X-Correlation-ID'] = correlation_id_to_log
    api.logger.info(f"Request finished with status {response.status_code}",
                    extra={'event': 'request_end', 'status_code': response.status_code})
    return response


@api.route('/senecaai/v1/stt', methods=['POST'])
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
        description: "The audio file to transcribe (WAV or MP3 format)."
      - name: lang
        in: formData
        type: string
        required: false
        default: en
        description: "The language of the audio. e.g., 'en', 'es', 'fr'."
    security:
      - BearerAuth: []
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
        description: "Unauthorized: API Key or JWT missing or invalid."
      503:
        description: "Service unavailable, Faster-Whisper model not loaded."
      500:
        description: "Internal server error during transcription."
    """
    api.logger.info("STT request received.")

    if config.stt_backend == 'faster-whisper' and model is None:
        api.logger.error("Faster-Whisper model is not loaded. Cannot process request.")
        raise ServiceUnavailableError("Speech-to-Text service is unavailable.")

    if 'file' not in request.files:
        api.logger.error("No audio file provided in the request.")
        raise BadRequestError("No audio file provided")

    audio_file = request.files['file']
    if audio_file.filename == '':
        api.logger.error("No selected file in the request.")
        raise BadRequestError("No selected file")

    audio_file.seek(0, os.SEEK_END)
    file_size = audio_file.tell()
    audio_file.seek(0)
    if file_size == 0:
        api.logger.error("Received an empty audio file.")
        raise BadRequestError("Empty audio file")

    api.logger.info(f"Input file name: {audio_file.filename}")

    allowed_extensions = ['wav', 'mp3']
    filename_parts = audio_file.filename.rsplit('.', 1)
    if len(filename_parts) < 2 or filename_parts[1].lower() not in allowed_extensions:
        api.logger.error(f"Invalid file type received: {audio_file.filename}. Only .wav and .mp3 are supported.")
        raise BadRequestError("Invalid file type. Only .wav and .mp3 are supported.")

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
            raise InternalServerError("Unsupported STT backend configured.")

        truncated_text = (full_text[:100] + '...') if len(full_text) > 100 else full_text
        api.logger.info(f"Transcription successful. Text: '{truncated_text}'")

        return jsonify({"text": full_text}), HTTPStatus.OK

    except Exception as e:
        api.logger.error(f"An error occurred during faster-whisper transcription for file: {audio_file.filename}.",
                         exc_info=True)
        raise InternalServerError("An internal server error occurred during transcription.")
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
      - BearerAuth: []
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
        description: "Unauthorized: API Key or JWT missing or invalid."
    """
    api.logger.info("Request received for supported STT languages.")
    supported_languages = [{"code": code, "name": name} for code, name in whisper.tokenizer.LANGUAGES.items()]
    return jsonify(supported_languages), HTTPStatus.OK


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
        return jsonify({"status": "ok", "model_status": "google_online"}), HTTPStatus.OK
    elif config.stt_backend == 'faster-whisper' and model is not None:
        return jsonify({"status": "ok", "model_status": "loaded"}), HTTPStatus.OK
    else:
        api.logger.warning("Health check: Faster-Whisper model is not loaded or backend is unsupported.")
        return jsonify({"status": "degraded", "model_status": "not loaded"}), HTTPStatus.SERVICE_UNAVAILABLE


# --- Authentication Endpoints ---
@api.route('/senecaai/v1/auth/login', methods=['POST'])
def login():
    """
    User Login
    Authenticates a user and returns access and refresh tokens.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/AuthLoginSchema'
    responses:
      200:
        description: "Authentication successful."
        schema:
          $ref: '#/definitions/AuthTokensSchema'
      400:
        description: "Bad Request: Missing username or password."
      401:
        description: "Unauthorized: Invalid username or password."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info("Login request received.")
    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        raise ServiceUnavailableError("Database service unavailable.")

    data = request.get_json()
    if not data:
        api.logger.warning("Login attempt with no data.")
        raise BadRequestError("Missing username or password.")

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        api.logger.warning("Login attempt with missing username or password.")
        raise BadRequestError("Missing username or password.")

    user = db_client.get_user_by_username(username)

    if user and bcrypt.verify(password, user['password_hash']):
        access_token = generate_jwt(str(user['_id']), user['user_name'])
        refresh_token = generate_refresh_token()
        hashed_refresh_token = hash_refresh_token(refresh_token)
        
        # Calculate refresh token expiration (e.g., 7 days from now)
        refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        db_client.add_refresh_token_to_user(str(user['_id']), hashed_refresh_token, refresh_token_expires_at)

        api.logger.info(f"User {username} logged in successfully.")
        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": config.jwt_access_token_expires_in
        }), HTTPStatus.OK
    else:
        api.logger.warning(f"Failed login attempt for user: {username}")
        raise UnauthorizedError("Invalid username or password.")


@api.route('/senecaai/v1/auth/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh Access Token
    Refreshes an expired access token using a valid refresh token.
    ---
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: "Refresh Token (Bearer <refresh_token>)"
    responses:
      200:
        description: "Token refreshed successfully."
        schema:
          $ref: '#/definitions/RefreshTokenResponseSchema'
      400:
        description: "Bad Request: Refresh token not provided."
      401:
        description: "Unauthorized: Invalid or expired refresh token."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info("Refresh token request received.")
    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        raise ServiceUnavailableError("Database service unavailable.")

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        api.logger.warning("Refresh token request missing Authorization header or malformed.")
        raise BadRequestError("Refresh token not provided.")

    refresh_token = auth_header.split(' ')[1]
    
    user = db_client.find_user_by_refresh_token(refresh_token)

    if user:
        new_access_token = generate_jwt(str(user['_id']), user['user_name'])
        api.logger.info(f"Access token refreshed for user: {user['user_name']}.")
        return jsonify({
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": config.jwt_access_token_expires_in
        }), HTTPStatus.OK
    else:
        api.logger.warning("Invalid or expired refresh token provided.")
        raise UnauthorizedError("Invalid or expired refresh token.")


@api.route('/senecaai/v1/auth/logout', methods=['POST'])
def logout():
    """
    User Logout
    Revokes the provided refresh token, effectively logging the user out.
    ---
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: "Refresh Token (Bearer <refresh_token>)"
    responses:
      200:
        description: "Logout successful."
      400:
        description: "Bad Request: Refresh token not provided."
      401:
        description: "Unauthorized: Invalid refresh token."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info("Logout request received.")
    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        raise ServiceUnavailableError("Database service unavailable.")

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        api.logger.warning("Logout attempt with missing Authorization header or malformed.")
        raise BadRequestError("Refresh token not provided.")

    refresh_token = auth_header.split(' ')[1]
    
    user = db_client.find_user_by_refresh_token(refresh_token)
    if not user:
        api.logger.warning("Logout failed: Invalid refresh token provided.")
        raise UnauthorizedError("Invalid refresh token.")

    if db_client.revoke_refresh_token(str(user['_id']), refresh_token):
        api.logger.info("Logout successful: Refresh token revoked.")
        return jsonify({"message": "Logout successful."}), HTTPStatus.OK
    else:
        api.logger.warning("Logout failed: Invalid refresh token provided.")
        raise UnauthorizedError("Invalid refresh token.")


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
      - BearerAuth: []
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
        description: "Unauthorized: API Key or JWT missing or invalid."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info(f"Request to get conversations for user: {g.user_id}")
    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        raise ServiceUnavailableError("Database service unavailable.")

    try:
        conv_per_page = int(request.args.get('convPerPage', 20))
        num_page = int(request.args.get('numPage', 1))
    except ValueError:
        api.logger.error("Invalid pagination parameters provided.", exc_info=True)
        raise BadRequestError("Invalid pagination parameters. 'convPerPage' and 'numPage' must be integers.")

    if conv_per_page <= 0 or num_page <= 0:
        raise BadRequestError("Pagination parameters 'convPerPage' and 'numPage' must be positive integers.")

    skip = (num_page - 1) * conv_per_page
    limit = conv_per_page

    conversations = db_client.get_conversations(g.user_id, skip=skip, limit=limit)

    api.logger.info(f"Found {len(conversations)} conversations for user {g.user_id} on page {num_page}.")
    return Response(json.dumps(_prepare_response_data(conversations), cls=MongoJsonEncoder),
                    mimetype='application/json'), HTTPStatus.OK


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
      - name: Authorization
        in: header
        type: string
        required: true
        description: "JWT Access Token (Bearer <token>)"
    responses:
      200:
        description: "The requested conversation."
        schema:
          $ref: '#/definitions/ConversationSchema'
      400:
        description: "Bad Request: Invalid conversation ID format."
      401:
        description: "Unauthorized: API Key or JWT missing or invalid."
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
        raise ServiceUnavailableError("Database service unavailable.")

    if not ObjectId.is_valid(_id):
        api.logger.warning(f"Invalid ObjectId format for _id: {_id}")
        raise BadRequestError("Invalid conversation ID format.")

    conversation = db_client.get_conversation_by_id(_id, user_id=g.user_id)

    if not conversation:
        if db_client.check_conversation_exists(_id):
            api.logger.warning(f"User {g.user_id} attempted to access conversation {_id} owned by another user.")
            raise ForbiddenError("User does not have access to this conversation.")
        api.logger.info(f"Conversation with _id: {_id} not found for user: {g.user_id}")
        raise NotFoundError("Conversation not found.")

    api.logger.info(f"Conversation {_id} retrieved successfully for user {g.user_id}.")
    return Response(json.dumps(_prepare_response_data(conversation), cls=MongoJsonEncoder),
                    mimetype='application/json'), HTTPStatus.OK


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
      - BearerAuth: []
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
        description: "Unauthorized: API Key or JWT missing or invalid."
      500:
        description: "Internal Server Error: An unexpected error occurred."
    """
    api.logger.info(f"Request to create new conversation for user: {g.user_id}")

    if not db_client.is_connected():
        api.logger.error("MongoDB is not connected.")
        raise ServiceUnavailableError("Database service unavailable.")

    data = request.get_json()
    if not data:
        raise BadRequestError("No input data provided.")

    title = data.get('title')
    messages = data.get('messages')

    if not title or not isinstance(title, str):
        raise BadRequestError("Title is required and must be a string.")

    is_valid_messages, error_msg = validate_message_structure(messages)
    if not is_valid_messages:
        raise BadRequestError(error_msg)

    new_conversation = db_client.create_conversation(g.user_id, title, messages)

    location_header = f"{request.url}/{new_conversation['_id']}"
    api.logger.info(f"Conversation created successfully with _id: {new_conversation['_id']} for user {g.user_id}.")
    return Response(json.dumps(_prepare_response_data(new_conversation), cls=MongoJsonEncoder),
                    mimetype='application/json'), HTTPStatus.CREATED, {'Location': location_header}


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
      - BearerAuth: []
      - APIKeyHeader: []
    responses:
      200:
        description: "The updated conversation."
        schema:
          $ref: '#/definitions/ConversationSchema'
      400:
        description: "Bad Request: Invalid update data provided or invalid conversation ID format."
      401:
        description: "Unauthorized: API Key or JWT missing or invalid."
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
        raise ServiceUnavailableError("Database service unavailable.")

    if not ObjectId.is_valid(_id):
        api.logger.warning(f"Invalid ObjectId format for _id: {_id}")
        raise BadRequestError("Invalid conversation ID format.")

    data = request.get_json()
    if not data:
        raise BadRequestError("No update data provided.")

    update_fields = {}
    if 'title' in data:
        if not isinstance(data['title'], str):
            raise BadRequestError("Title must be a string.")
        update_fields['title'] = data['title']

    if 'messages' in data:
        is_valid_messages, error_msg = validate_message_structure(data['messages'])
        if not is_valid_messages:
            raise BadRequestError(error_msg)
        update_fields['messages'] = data['messages']

    if not update_fields:
        raise BadRequestError("No valid fields to update provided (e.g., 'title', 'messages').")

    updated = db_client.update_conversation(_id, g.user_id, update_fields)

    if not updated:
        if db_client.check_conversation_exists(_id):
            api.logger.warning(f"User {g.user_id} attempted to update conversation {_id} owned by another user.")
            raise ForbiddenError("User does not have access to modify this conversation.")

        api.logger.info(f"Conversation with _id: {_id} not found for user: {g.user_id}")
        raise NotFoundError("Conversation not found.")

    updated_conversation = db_client.get_conversation_by_id(_id)
    api.logger.info(f"Conversation {_id} updated successfully for user {g.user_id}.")
    return Response(json.dumps(_prepare_response_data(updated_conversation), cls=MongoJsonEncoder),
                    mimetype='application/json'), HTTPStatus.OK


if __name__ == '__main__':
    from urllib.parse import urlparse
    from waitress import serve

    _parsed = urlparse(config.seneca_api_base_url)
    _host = _parsed.hostname or "0.0.0.0"
    _port = _parsed.port or 1414
    serve(api, host="0.0.0.0", port=_port)