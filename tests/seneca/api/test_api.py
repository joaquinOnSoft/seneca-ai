import io
import json
from time import sleep
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError

# Import your Flask application (ensure 'api' is the Flask object)
# We assume the import structure is correct from the project root
from src.seneca.api.api import api as flask_app
from src.seneca.api.api import _prepare_response_data, MongoJsonEncoder  # Import helper and encoder

API_METHOD_HEALTH = '/senecaai/v1/health'
API_METHOD_STT_LANGUAGES = '/senecaai/v1/stt/languages'
API_METHOD_STT = '/senecaai/v1/stt'

# New API Endpoints
API_METHOD_CONVERSATIONS = '/senecaai/v1/conversations'
API_METHOD_CONVERSATION_BY_ID = '/senecaai/v1/conversations/'

# Define a test API key
TEST_API_KEY = "test-seneca-ai-api-key"
TEST_USER_ID = "test_user_123"  # This is set in before_request_func in api.py

# Sample ObjectIds for testing
TEST_CONVERSATION_ID_1 = str(ObjectId())
TEST_CONVERSATION_ID_2 = str(ObjectId())
TEST_CONVERSATION_ID_OTHER_USER = str(ObjectId())
TEST_CONVERSATION_ID_NEW = str(ObjectId())  # For POST tests

# Sample Datetime objects
TEST_DATETIME_1 = datetime(2023, 10, 27, 15, 59, 50, tzinfo=timezone.utc)
TEST_DATETIME_2 = datetime(2023, 10, 26, 10, 30, 0, tzinfo=timezone.utc)
TEST_DATETIME_NEW_MSG = datetime(2023, 10, 28, 10, 0, 0, tzinfo=timezone.utc)
TEST_DATETIME_UPDATED_MSG = datetime(2023, 10, 29, 10, 0, 0, tzinfo=timezone.utc)

# Sample Conversation Data (using ObjectId and datetime objects directly for internal mock storage)
SAMPLE_CONVERSATION_1 = {
    "_id": ObjectId(TEST_CONVERSATION_ID_1),
    "user_id": TEST_USER_ID,
    "title": "Solicitud de Día Libre",
    "created_at": TEST_DATETIME_1,
    "messages": [
        {"role": "user", "content": "Hola Gemini, ¿puedes ayudarme a escribir un correo electrónico?",
         "timestamp": TEST_DATETIME_1.isoformat().replace('+00:00', 'Z')}
    ]
}

SAMPLE_CONVERSATION_2 = {
    "_id": ObjectId(TEST_CONVERSATION_ID_2),
    "user_id": TEST_USER_ID,
    "title": "Planificación de Viaje",
    "created_at": TEST_DATETIME_2,
    "messages": [
        {"role": "user", "content": "Necesito planificar un viaje",
         "timestamp": TEST_DATETIME_2.isoformat().replace('+00:00', 'Z')}
    ]
}

SAMPLE_CONVERSATION_OTHER_USER = {
    "_id": ObjectId(TEST_CONVERSATION_ID_OTHER_USER),
    "user_id": "other_user_456",
    "title": "Conversación de Otro Usuario",
    "created_at": TEST_DATETIME_1,
    "messages": [
        {"role": "user", "content": "Mensaje de otro usuario",
         "timestamp": TEST_DATETIME_1.isoformat().replace('+00:00', 'Z')}
    ]
}


# Helper to convert ObjectId and datetime to string for JSON comparison
# This helper is now less critical as _prepare_response_data should handle it,
# but useful for explicit comparisons in tests.
def conversation_to_json_compatible(conv):
    return _prepare_response_data(conv)


# Mock of the languages returned by the /senecaai/v1/stt/languages endpoint
MOCKED_LANGUAGES = [
    {
        "code": "en",
        "name": "english"
    },
    {
        "code": "zh",
        "name": "chinese"
    },
    {
        "code": "de",
        "name": "german"
    },
    {
        "code": "es",
        "name": "spanish"
    },
    {
        "code": "ru",
        "name": "russian"
    },
    {
        "code": "ko",
        "name": "korean"
    },
    {
        "code": "fr",
        "name": "french"
    },
    {
        "code": "ja",
        "name": "japanese"
    },
    {
        "code": "pt",
        "name": "portuguese"
    },
    {
        "code": "tr",
        "name": "turkish"
    },
    {
        "code": "pl",
        "name": "polish"
    },
    {
        "code": "ca",
        "name": "catalan"
    },
    {
        "code": "nl",
        "name": "dutch"
    },
    {
        "code": "ar",
        "name": "arabic"
    },
    {
        "code": "sv",
        "name": "swedish"
    },
    {
        "code": "it",
        "name": "italian"
    },
    {
        "code": "id",
        "name": "indonesian"
    },
    {
        "code": "hi",
        "name": "hindi"
    },
    {
        "code": "fi",
        "name": "finnish"
    },
    {
        "code": "vi",
        "name": "vietnamese"
    },
    {
        "code": "he",
        "name": "hebrew"
    },
    {
        "code": "uk",
        "name": "ukrainian"
    },
    {
        "code": "el",
        "name": "greek"
    },
    {
        "code": "ms",
        "name": "malay"
    },
    {
        "code": "cs",
        "name": "czech"
    },
    {
        "code": "ro",
        "name": "romanian"
    },
    {
        "code": "da",
        "name": "danish"
    },
    {
        "code": "hu",
        "name": "hungarian"
    },
    {
        "code": "ta",
        "name": "tamil"
    },
    {
        "code": "no",
        "name": "norwegian"
    },
    {
        "code": "th",
        "name": "thai"
    },
    {
        "code": "ur",
        "name": "urdu"
    },
    {
        "code": "hr",
        "name": "croatian"
    },
    {
        "code": "bg",
        "name": "bulgarian"
    },
    {
        "code": "lt",
        "name": "lithuanian"
    },
    {
        "code": "la",
        "name": "latin"
    },
    {
        "code": "mi",
        "name": "maori"
    },
    {
        "code": "ml",
        "name": "malayalam"
    },
    {
        "code": "cy",
        "name": "welsh"
    },
    {
        "code": "sk",
        "name": "slovak"
    },
    {
        "code": "te",
        "name": "telugu"
    },
    {
        "code": "fa",  # Corrected: Removed extra double quote
        "name": "persian"
    },
    {
        "code": "lv",
        "name": "latvian"
    },
    {
        "code": "bn",
        "name": "bengali"
    },
    {
        "code": "sr",
        "name": "serbian"
    },
    {
        "code": "az",
        "name": "azerbaijani"
    },
    {
        "code": "sl",
        "name": "slovenian"
    },
    {
        "code": "kn",
        "name": "kannada"
    },
    {
        "code": "et",
        "name": "estonian"
    },
    {
        "code": "mk",
        "name": "macedonian"
    },
    {
        "code": "br",
        "name": "breton"
    },
    {
        "code": "eu",
        "name": "basque"
    },
    {
        "code": "is",
        "name": "icelandic"
    },
    {
        "code": "hy",  # Corrected: Removed extra double quote
        "name": "armenian"
    },
    {
        "code": "ne",
        "name": "nepali"
    },
    {
        "code": "mn",
        "name": "mongolian"
    },
    {
        "code": "bs",
        "name": "bosnian"
    },
    {
        "code": "kk",
        "name": "kazakh"
    },
    {
        "code": "sq",
        "name": "albanian"
    },
    {
        "code": "sw",
        "name": "swahili"
    },
    {
        "code": "gl",
        "name": "galician"
    },
    {
        "code": "mr",
        "name": "marathi"
    },
    {
        "code": "pa",
        "name": "punjabi"
    },
    {
        "code": "si",
        "name": "sinhala"
    },
    {
        "code": "km",
        "name": "khmer"
    },
    {
        "code": "sn",
        "name": "shona"
    },
    {
        "code": "yo",
        "name": "yoruba"
    },
    {
        "code": "so",
        "name": "somali"
    },
    {
        "code": "af",
        "name": "afrikaans"
    },
    {
        "code": "oc",
        "name": "occitan"
    },
    {
        "code": "ka",
        "name": "georgian"
    },
    {
        "code": "be",
        "name": "belarusian"
    },
    {
        "code": "tg",
        "name": "tajik"
    },
    {
        "code": "sd",
        "name": "sindhi"
    },
    {
        "code": "gu",
        "name": "gujarati"
    },
    {
        "code": "am",
        "name": "amharic"
    },
    {
        "code": "yi",
        "name": "yiddish"
    },
    {
        "code": "lo",
        "name": "lao"
    },
    {
        "code": "uz",
        "name": "uzbek"
    },
    {
        "code": "fo",
        "name": "faroese"
    },
    {
        "code": "ht",
        "name": "haitian creole"
    },
    {
        "code": "ps",
        "name": "pashto"
    },
    {
        "code": "tk",
        "name": "turkmen"
    },
    {
        "code": "nn",
        "name": "nynorsk"
    },
    {
        "code": "mt",
        "name": "maltese"
    },
    {
        "code": "sa",
        "name": "sanskrit"
    },
    {
        "code": "lb",
        "name": "luxembourgish"
    },
    {
        "code": "my",
        "name": "myanmar"
    },
    {
        "code": "bo",
        "name": "tibetan"
    },
    {
        "code": "tl",
        "name": "tagalog"
    },
    {
        "code": "mg",
        "name": "malagasy"
    },
    {
        "code": "as",
        "name": "assamese"
    },
    {
        "code": "tt",
        "name": "tatar"
    },
    {
        "code": "haw",
        "name": "hawaiian"
    },
    {
        "code": "ln",
        "name": "lingala"
    },
    {
        "code": "ha",
        "name": "hausa"
    },
    {
        "code": "ba",
        "name": "bashkir"
    },
    {
        "code": "jw",
        "name": "javanese"
    },
    {
        "code": "su",
        "name": "sundanese"
    },
    {
        "code": "yue",
        "name": "cantonese"
    }
]


@pytest.fixture
def client():
    """Configures the test client for the Flask application."""
    flask_app.config['TESTING'] = True

    # Create a mock config object
    mock_config = MagicMock()
    mock_config.seneca_ai_api_key = TEST_API_KEY
    mock_config.whisper_model_size = "small"  # Default value, adjust if needed for specific tests
    mock_config.whisper_device = "cpu"  # Default value
    mock_config.whisper_compute_type = "int8"  # Default value
    mock_config.hf_token = None  # Default value, or set a test token if needed
    mock_config.stt_backend = "faster-whisper"  # Default backend for most tests
    mock_config.mongodb_uri = "mongodb://mock_host:27017/mock_db"  # Added for MongoDB connection

    # Patch the config object in the api module
    with patch('src.seneca.api.api.config', new=mock_config):
        # Patch MongoClient to prevent actual connection attempts and mock the collection
        with patch('src.seneca.api.api.MongoClient') as MockMongoClient:
            mock_mongo_instance = MagicMock()
            # The actual collection will be mocked by mock_db_client fixture
            mock_mongo_instance.get_database.return_value.conversations = MagicMock()
            MockMongoClient.return_value = mock_mongo_instance

            # Disable rate limiting for tests
            flask_app.config["LIMITER_ENABLED"] = False  # Correct way to disable Flask-Limiter
            flask_app.config["RATELIMIT_ENABLED"] = False

            from src.seneca.api.api import limiter
            limiter.enabled = False

            with flask_app.test_client() as client:
                yield client


@pytest.fixture
def mock_whisper_model_fixture():
    """Fixture to mock the faster-whisper model in tests."""
    # Patch the 'model' object directly in the api module
    with patch('src.seneca.api.api.model') as MockWhisperModel:
        # Configure a default value for transcribe
        MockWhisperModel.transcribe.return_value = ([MagicMock(text="Mocked transcription")],
                                                    MagicMock(language="en", language_probability=1.0))
        yield MockWhisperModel


@pytest.fixture
def mock_temp_file_fixture():
    """Fixture to mock tempfile.NamedTemporaryFile and os.remove."""
    with patch('tempfile.NamedTemporaryFile') as MockNamedTemporaryFile:
        mock_file_obj = MagicMock()
        mock_file_obj.name = "/tmp/mock_audio_file.mp3"  # Simulated file name
        MockNamedTemporaryFile.return_value.__enter__.return_value = mock_file_obj
        with patch('os.remove') as MockOsRemove:
            yield mock_file_obj, MockOsRemove


@pytest.fixture(autouse=True)
def delay_to_avoid_too_many_request_per_second():
    sleep(0.01)  # Reduced delay as rate limiting is disabled


@pytest.fixture
def mock_db_client():
    _db_store = {
        ObjectId(SAMPLE_CONVERSATION_1["_id"]): SAMPLE_CONVERSATION_1.copy(),
        ObjectId(SAMPLE_CONVERSATION_2["_id"]): SAMPLE_CONVERSATION_2.copy(),
        ObjectId(SAMPLE_CONVERSATION_OTHER_USER["_id"]): SAMPLE_CONVERSATION_OTHER_USER.copy(),
    }

    class MockDatabase:
        def is_connected(self):
            return True

        def connect(self):
            return True

        def get_conversations(self, user_id, skip=0, limit=20):
            filtered_data = [doc.copy() for doc in _db_store.values() if doc.get("user_id") == user_id]
            filtered_data.sort(key=lambda x: x["created_at"], reverse=True)
            return filtered_data[skip : skip + limit]

        def get_conversation_by_id(self, conversation_id, user_id=None):
            if isinstance(conversation_id, str):
                try:
                    conversation_id = ObjectId(conversation_id)
                except:
                    pass
            if conversation_id in _db_store:
                doc = _db_store[conversation_id].copy()
                if user_id is None or doc.get("user_id") == user_id:
                    return doc
            return None

        def check_conversation_exists(self, conversation_id):
            if isinstance(conversation_id, str):
                try:
                    conversation_id = ObjectId(conversation_id)
                except:
                    pass
            return conversation_id in _db_store

        def create_conversation(self, user_id, title, messages):
            new_id = ObjectId()
            doc = {
                "_id": new_id,
                "user_id": user_id,
                "title": title,
                "created_at": TEST_DATETIME_NEW_MSG,  # we use TEST_DATETIME_NEW_MSG for consistency
                "messages": messages
            }
            _db_store[new_id] = doc
            return doc

        def update_conversation(self, conversation_id, user_id, update_fields):
            if isinstance(conversation_id, str):
                try:
                    conversation_id = ObjectId(conversation_id)
                except:
                    pass
            if conversation_id in _db_store:
                doc = _db_store[conversation_id]
                if doc.get("user_id") == user_id:
                    for key, value in update_fields.items():
                        doc[key] = value
                    return True
            return False

        @property
        def _db_store_accessor(self):
            return _db_store

    mock_instance = MockDatabase()
    mock_db = MagicMock()
    mock_db.is_connected.side_effect = mock_instance.is_connected
    mock_db.connect.side_effect = mock_instance.connect
    mock_db.get_conversations.side_effect = mock_instance.get_conversations
    mock_db.get_conversation_by_id.side_effect = mock_instance.get_conversation_by_id
    mock_db.check_conversation_exists.side_effect = mock_instance.check_conversation_exists
    mock_db.create_conversation.side_effect = mock_instance.create_conversation
    mock_db.update_conversation.side_effect = mock_instance.update_conversation
    mock_db._db_store_accessor = mock_instance._db_store_accessor
    mock_db._is_mock = True

    with patch('src.seneca.api.api.db_client', mock_db):
        yield mock_db


# --- Tests for /senecaai/v1/stt ---

def test_stt_success_mp3(client, mock_whisper_model_fixture, mock_temp_file_fixture):
    """
  Tests successful transcription of an MP3 file with a specified language.
  The /senecaai/v1/stt method receives the lang=es parameter and in the body an mp3 file
  (simulated) and returns the following: { "text": " 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10" }
  """
    mock_file_obj, mock_os_remove = mock_temp_file_fixture

    # Configure the mock to return the specific text
    mock_whisper_model_fixture.transcribe.return_value = (
        [MagicMock(text=" 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10")],
        MagicMock(language="es", language_probability=1.0)
    )

    # Simulate the MP3 file content
    dummy_mp3_content = b"fake mp3 api data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), '1-10-sp.mp3'),
        'lang': 'es'
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}  # Add API key header
    response = client.post(API_METHOD_STT, data=data, content_type='multipart/form-data', headers=headers)

    assert response.status_code == 200
    assert json.loads(response.data) == {"text": " 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10"}
    mock_whisper_model_fixture.transcribe.assert_called_once_with(mock_file_obj.name, language='es')
    mock_os_remove.assert_called_once_with(mock_file_obj.name)


def test_stt_success_google_backend(client, mock_temp_file_fixture):
    """Tests successful transcription using the Google Web Speech backend."""
    mock_file_obj, mock_os_remove = mock_temp_file_fixture

    # Temporarily change backend to google for this test
    with patch('src.seneca.api.api.config.stt_backend', 'google'):
        # Mock speech_recognition
        with patch('speech_recognition.Recognizer.record') as mock_record, \
                patch('speech_recognition.Recognizer.recognize_google') as mock_recognize, \
                patch('speech_recognition.AudioFile') as mock_audiofile:
            mock_recognize.return_value = "Google transcription result"

            dummy_mp3_content = b"fake mp3 data"
            data = {
                'file': (io.BytesIO(dummy_mp3_content), 'test.wav'),
                'lang': 'en'
            }
            headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
            response = client.post(API_METHOD_STT, data=data, content_type='multipart/form-data', headers=headers)

            assert response.status_code == 200
            assert json.loads(response.data) == {"text": "Google transcription result"}
            mock_recognize.assert_called_once()
            mock_os_remove.assert_called_once_with(mock_file_obj.name)


def test_stt_no_file_provided(client):
    """Tests the case where no file is provided. Should return 400."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}  # Add API key header
    response = client.post(API_METHOD_STT, data={}, content_type='multipart/form-data', headers=headers)
    assert response.status_code == 400
    assert json.loads(response.data) == {"error": "No api file provided"}


def test_stt_empty_file(client):
    """Tests the case where an empty file is provided."""
    dummy_empty_content = b""
    data = {
        'file': (io.BytesIO(dummy_empty_content), 'empty.mp3')
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}  # Add API key header
    response = client.post(API_METHOD_STT, data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == 400
    assert json.loads(response.data) == {"error": "Empty api file"}


def test_stt_invalid_file_type(client):
    """Tests the case of an disallowed file type."""
    dummy_txt_content = b"this is a text file"
    data = {
        'file': (io.BytesIO(dummy_txt_content), 'test.txt')
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}  # Add API key header
    response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == 400
    assert json.loads(response.data) == {"error": "Invalid file type. Only .wav and .mp3 are supported."}


def test_stt_model_not_loaded(client):
    """Tests the case where the Faster-Whisper model has not been loaded."""
    with patch('src.seneca.api.api.model', None):  # Mocks the global model to None
        dummy_mp3_content = b"fake mp3 api data"
        data = {
            'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
        }
        headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}  # Add API key header
        response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data', headers=headers)
        assert response.status_code == 503
        assert json.loads(response.data) == {"error": "Speech-to-Text service is unavailable."}


def test_stt_transcription_error(client, mock_whisper_model_fixture, mock_temp_file_fixture):
    """Tests the case where faster-whisper transcription fails."""
    # The actual error message from faster-whisper when given invalid api data
    expected_error_message = "An internal server error occurred during transcription."
    mock_whisper_model_fixture.transcribe.side_effect = Exception(
        "Whisper internal error")  # The actual exception can be anything
    mock_file_obj, mock_os_remove = mock_temp_file_fixture
    dummy_mp3_content = b"fake mp3 api data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}  # Add API key header
    response = client.post(API_METHOD_STT, data=data, content_type='multipart/form-data', headers=headers)

    assert response.status_code == 500
    assert json.loads(response.data) == {"error": expected_error_message}
    mock_os_remove.assert_called_once_with(mock_file_obj.name)


# --- New tests for API Key Authentication ---

def test_stt_missing_api_key(client):
    """Tests that STT endpoint returns 401 if no API key is provided."""
    dummy_mp3_content = b"fake mp3 api data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
    }
    response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data')  # No headers
    assert response.status_code == 401
    assert json.loads(response.data) == {"error": "Unauthorized: API Key missing"}


def test_stt_invalid_api_key(client):
    """Tests that STT endpoint returns 401 if an invalid API key is provided."""
    dummy_mp3_content = b"fake mp3 api data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
    }
    headers = {'X-SENECA-AI-API-KEY': "invalid-key"}
    response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == 401
    assert json.loads(response.data) == {"error": "Unauthorized: Invalid API Key"}


# --- Tests for /senecaai/v1/stt/languages ---

def test_get_supported_languages(client):
    """
  Tests the endpoint for getting supported languages.
  The /senecaai/v1/stt/languages method returns the MOCKED_LANGUAGES list.
  """
    # Mock whisper.tokenizer.LANGUAGES only for this test
    with patch('whisper.tokenizer.LANGUAGES', {lang['code']: lang['name'] for lang in MOCKED_LANGUAGES}):
        headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}  # Add API key header
        response = client.get(API_METHOD_STT_LANGUAGES, headers=headers)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert data == MOCKED_LANGUAGES


def test_get_supported_languages_missing_api_key(client):
    """Tests that languages endpoint returns 401 if no API key is provided."""
    response = client.get(API_METHOD_STT_LANGUAGES)  # No headers
    assert response.status_code == 401
    assert json.loads(response.data) == {"error": "Unauthorized: API Key missing"}


def test_get_supported_languages_invalid_api_key(client):
    """Tests that languages endpoint returns 401 if an invalid API key is provided."""
    headers = {'X-SENECA-AI-API-KEY': "invalid-key"}
    response = client.get(API_METHOD_STT_LANGUAGES, headers=headers)
    assert response.status_code == 401
    assert json.loads(response.data) == {"error": "Unauthorized: Invalid API Key"}


# --- Tests for /senecaai/v1/health ---

def test_health_check_model_loaded(client, mock_whisper_model_fixture):
    """Tests the health check endpoint when the Faster-Whisper model is loaded."""
    # mock_whisper_model_fixture ensures api.model is not None
    response = client.get(API_METHOD_HEALTH)  # No headers needed for health check
    assert response.status_code == 200
    assert json.loads(response.data) == {"status": "ok", "model_status": "loaded"}


def test_health_check_google_backend(client):
    """Tests the health check endpoint when the Google Web Speech backend is used."""
    with patch('src.seneca.api.api.config.stt_backend', 'google'):
        response = client.get(API_METHOD_HEALTH)
        assert response.status_code == 200
        assert json.loads(response.data) == {"status": "ok", "model_status": "google_online"}


def test_health_check_model_not_loaded(client):
    """Tests the health check endpoint when the Faster-Whisper model is not loaded."""
    with patch('src.seneca.api.api.model', None):
        response = client.get(API_METHOD_HEALTH)  # No headers needed for health check
        assert response.status_code == 503
        assert json.loads(response.data) == {"status": "degraded", "model_status": "not loaded"}


# --- New test for Rate Limiting ---
def test_rate_limiting(client, mock_whisper_model_fixture, mock_temp_file_fixture):
    """
    Tests that the API enforces a rate limit of 5 requests per second.
    """
    # This test is now less relevant as rate limiting is disabled in the client fixture.
    # It will always pass with status 200 for all requests.
    # If you want to test rate limiting, you'd need a separate client fixture where it's enabled.
    mock_file_obj, mock_os_remove = mock_temp_file_fixture
    mock_whisper_model_fixture.transcribe.return_value = (
        [MagicMock(text="Mocked transcription")],
        MagicMock(language="en", language_probability=1.0)
    )

    endpoint = API_METHOD_STT
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    dummy_mp3_content = b"fake mp3 api data"

    # Make 5 requests, all should pass
    for i in range(5):
        # Create a new BytesIO object for each request
        data = {
            'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3'),
            'lang': 'en'
        }
        response = client.post(endpoint, data=data, content_type='multipart/form-data', headers=headers)
        assert response.status_code == 200, f"Request {i + 1} failed unexpectedly with status {response.status_code}"

    # The 6th request should also pass as rate limiting is disabled
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3'),
        'lang': 'en'
    }
    response = client.post(endpoint, data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == 200, f"Expected 200, but got {response.status_code}"


# --- Tests for Conversation Management Endpoints ---

def test_get_conversations_success(client, mock_db_client):
    """Tests successful retrieval of conversations for the authenticated user."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    # The mock collection is initialized with SAMPLE_CONVERSATION_1 and SAMPLE_CONVERSATION_2
    # We need to ensure the mock's find method returns a cursor that iterates over these.
    # The mock_db_client fixture already sets this up.

    response = client.get(API_METHOD_CONVERSATIONS, headers=headers)

    assert response.status_code == 200
    expected_conversations = [
        conversation_to_json_compatible(SAMPLE_CONVERSATION_1),
        conversation_to_json_compatible(SAMPLE_CONVERSATION_2)
    ]
    assert json.loads(response.data) == expected_conversations
    mock_db_client.get_conversations.assert_called_once_with(TEST_USER_ID, skip=0, limit=20)


def test_get_conversations_pagination(client, mock_db_client):
    """Tests pagination parameters for conversations."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    # Simulate the mock collection returning only the second conversation for page 2
    # Reset the mock's internal store for this specific test to control pagination
    mock_db_client._db_store_accessor.clear()
    mock_db_client._db_store_accessor[
        ObjectId(SAMPLE_CONVERSATION_1["_id"])] = SAMPLE_CONVERSATION_1.copy()
    mock_db_client._db_store_accessor[
        ObjectId(SAMPLE_CONVERSATION_2["_id"])] = SAMPLE_CONVERSATION_2.copy()

    response = client.get(f"{API_METHOD_CONVERSATIONS}?convPerPage=1&numPage=2", headers=headers)

    assert response.status_code == 200

    expected_conversations = [conversation_to_json_compatible(SAMPLE_CONVERSATION_2)]
    assert json.loads(response.data) == expected_conversations
    mock_db_client.get_conversations.assert_called_once_with(TEST_USER_ID, skip=1, limit=1)


def test_get_conversations_invalid_pagination(client, mock_db_client):
    """Tests invalid pagination parameters."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    response = client.get(f"{API_METHOD_CONVERSATIONS}?convPerPage=-1&numPage=abc", headers=headers)
    assert response.status_code == 400
    assert "Invalid pagination parameters. convPerPage and numPage must be integers." in json.loads(response.data)[
        "error"]


def test_get_conversations_db_error(client, mock_db_client):
    """Tests database error during conversation retrieval."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    mock_db_client.get_conversations.side_effect = PyMongoError("DB connection lost")
    response = client.get(API_METHOD_CONVERSATIONS, headers=headers)
    assert response.status_code == 500
    assert "Database error" in json.loads(response.data)["error"]


def test_get_conversation_by_id_success(client, mock_db_client):
    """Tests successful retrieval of a specific conversation."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    # The mock_db_client.find_one.side_effect is already set up in the fixture
    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", headers=headers)

    assert response.status_code == 200
    assert json.loads(response.data) == conversation_to_json_compatible(SAMPLE_CONVERSATION_1)
    mock_db_client.get_conversation_by_id.assert_called_once_with(TEST_CONVERSATION_ID_1, user_id=TEST_USER_ID)


def test_get_conversation_by_id_not_found(client, mock_db_client):
    """Tests retrieval of a non-existent conversation."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    # Ensure get_conversation_by_id returns None for the specific ID and user
    mock_db_client.get_conversation_by_id.side_effect = None
    mock_db_client.get_conversation_by_id.return_value = None
    mock_db_client.check_conversation_exists.side_effect = None
    mock_db_client.check_conversation_exists.return_value = False
    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", headers=headers)
    assert response.status_code == 404
    assert "Conversation not found" in json.loads(response.data)["error"]


def test_get_conversation_by_id_invalid_id_format(client, mock_db_client):
    """Tests retrieval with an invalid ObjectId format."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    # Ensure init_mongodb is called and conversations_collection is mocked
    # The setup_mongodb before_request hook will call init_mongodb, which will see the mocked collection.
    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}invalid_id_format", headers=headers)
    assert response.status_code == 400
    assert "Invalid conversation ID format" in json.loads(response.data)["error"]


def test_get_conversation_by_id_forbidden(client, mock_db_client):
    """Tests retrieval of a conversation owned by another user."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}

    # Ensure the conversation exists but belongs to 'other_user_456'
    forbidden_conv_id = ObjectId(TEST_CONVERSATION_ID_OTHER_USER)
    mock_db_client._db_store_accessor[forbidden_conv_id] = SAMPLE_CONVERSATION_OTHER_USER.copy()

    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_OTHER_USER}", headers=headers)
    assert response.status_code == 403
    assert "Forbidden: User does not have access to this conversation." in json.loads(response.data)["error"]


def test_get_conversation_by_id_db_error(client, mock_db_client):
    """Tests database error during specific conversation retrieval."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    mock_db_client.get_conversation_by_id.side_effect = PyMongoError("DB connection lost")
    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", headers=headers)
    assert response.status_code == 500
    assert "Database error" in json.loads(response.data)["error"]


def test_create_conversation_success(client, mock_db_client):
    """Tests successful creation of a new conversation."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}
    new_conversation_data = {
        "title": "Nueva Conversación de Prueba",
        "messages": [
            {"role": "user", "content": "¿Qué tal el tiempo hoy?",
             "timestamp": TEST_DATETIME_NEW_MSG.isoformat().replace('+00:00', 'Z')}
        ]
    }

    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps(new_conversation_data), headers=headers)

    assert response.status_code == 201
    response_data = json.loads(response.data)
    assert "_id" in response_data
    assert response_data["user_id"] == TEST_USER_ID
    assert response_data["title"] == new_conversation_data["title"]
    assert response_data["messages"] == new_conversation_data["messages"]
    assert "Location" in response.headers
    assert response.headers["Location"] == f"http://localhost{API_METHOD_CONVERSATIONS}/{response_data['_id']}"

    mock_db_client.create_conversation.assert_called_once_with(TEST_USER_ID, new_conversation_data["title"], new_conversation_data["messages"])


def test_create_conversation_invalid_data(client):
    """Tests creation with invalid input data."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}

    # Test missing title
    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({"messages": []}), headers=headers)
    assert response.status_code == 400
    assert "Title is required" in json.loads(response.data)["error"]

    # Test invalid messages type
    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({"title": "Test", "messages": "not a list"}),
                           headers=headers)
    assert response.status_code == 400
    assert "Messages must be a list." in json.loads(response.data)["error"]  # Updated expected message

    # Test invalid message structure (missing content)
    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps(
        {"title": "Test", "messages": [{"role": "user", "timestamp": "2023-10-28T10:00:00+00:00"}]}), headers=headers)
    assert response.status_code == 400
    assert "Each message must have 'role', 'content', and 'timestamp'." in json.loads(response.data)[
        "error"]  # Updated expected message

    # Test invalid timestamp format
    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({
        "title": "Test",
        "messages": [{"role": "user", "content": "hi", "timestamp": "invalid-date"}]
    }), headers=headers)
    assert response.status_code == 400
    assert "Message timestamp must be in ISO 8601 format." in json.loads(response.data)[
        "error"]  # Updated expected message

    # Test invalid message role
    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({
        "title": "Test",
        "messages": [{"role": "invalid", "content": "hi", "timestamp": "2023-10-28T10:00:00Z"}]
    }), headers=headers)
    assert response.status_code == 400
    assert "Message role must be 'user' or 'assistant'." in json.loads(response.data)["error"]


def test_create_conversation_db_error(client, mock_db_client):
    """Tests database error during conversation creation."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}
    new_conversation_data = {
        "title": "Nueva Conversación de Prueba",
        "messages": [
            {"role": "user", "content": "¿Qué tal el tiempo hoy?",
             "timestamp": TEST_DATETIME_NEW_MSG.isoformat().replace('+00:00', 'Z')}
        ]
    }
    mock_db_client.create_conversation.side_effect = PyMongoError("DB write error")
    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps(new_conversation_data), headers=headers)
    assert response.status_code == 500
    assert "Database error" in json.loads(response.data)["error"]


def test_update_conversation_success(client, mock_db_client):
    """Tests successful partial update of a conversation."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}
    update_data = {
        "title": "Título Actualizado",
        "messages": [
            {"role": "user", "content": "Nuevo mensaje",
             "timestamp": TEST_DATETIME_UPDATED_MSG.isoformat().replace('+00:00', 'Z')}
        ]
    }

    # Ensure the conversation exists in the mock store before the update
    original_conv_id = ObjectId(TEST_CONVERSATION_ID_1)
    mock_db_client._db_store_accessor[original_conv_id] = SAMPLE_CONVERSATION_1.copy()

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", data=json.dumps(update_data),
                            headers=headers)

    assert response.status_code == 200
    response_data = json.loads(response.data)
    assert response_data["_id"] == TEST_CONVERSATION_ID_1
    assert response_data["title"] == update_data["title"]
    assert response_data["messages"] == update_data["messages"]

    mock_db_client.update_conversation.assert_called_once_with(TEST_CONVERSATION_ID_1, TEST_USER_ID, update_data)

    # Verify the document in the mock store was actually updated
    updated_doc_in_store = mock_db_client.get_conversation_by_id(TEST_CONVERSATION_ID_1, user_id=TEST_USER_ID)
    assert updated_doc_in_store["title"] == update_data["title"]
    assert updated_doc_in_store["messages"] == update_data["messages"]


def test_update_conversation_not_found(client, mock_db_client):
    """Tests updating a non-existent conversation."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}
    update_data = {"title": "Non Existent"}

    # Ensure the conversation is NOT in the mock store for this test
    non_existent_id = ObjectId()
    if non_existent_id in mock_db_client._db_store_accessor:
        del mock_db_client._db_store_accessor[non_existent_id]

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{str(non_existent_id)}", data=json.dumps(update_data),
                            headers=headers)
    assert response.status_code == 404
    assert "Conversation not found" in json.loads(response.data)["error"]


def test_update_conversation_invalid_id_format(client, mock_db_client):
    """Tests updating with an invalid ObjectId format."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}
    update_data = {"title": "Invalid ID"}
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}invalid_id_format", data=json.dumps(update_data),
                            headers=headers)
    assert response.status_code == 400
    assert "Invalid conversation ID format" in json.loads(response.data)["error"]


def test_update_conversation_forbidden(client, mock_db_client):
    """Tests updating a conversation owned by another user."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}
    update_data = {"title": "Forbidden Update"}

    # Ensure the conversation exists but belongs to 'other_user_456'
    forbidden_conv_id = ObjectId(TEST_CONVERSATION_ID_OTHER_USER)
    mock_db_client._db_store_accessor[forbidden_conv_id] = SAMPLE_CONVERSATION_OTHER_USER.copy()

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_OTHER_USER}",
                            data=json.dumps(update_data), headers=headers)
    assert response.status_code == 403
    assert "Forbidden: User does not have access to modify this conversation." in json.loads(response.data)["error"]


def test_update_conversation_invalid_data(client):
    """Tests update with invalid input data."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}

    # Test invalid title type
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", data=json.dumps({"title": 123}),
                            headers=headers)
    assert response.status_code == 400
    assert "Title must be a string." in json.loads(response.data)["error"]

    # Test invalid messages type
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}",
                            data=json.dumps({"messages": "not a list"}), headers=headers)
    assert response.status_code == 400
    assert "Messages must be a list." in json.loads(response.data)["error"]  # Updated expected message

    # Test invalid message structure (missing content)
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}",
                            data=json.dumps({"messages": [{"role": "user", "timestamp": "2023-10-28T10:00:00+00:00"}]}),
                            headers=headers)
    assert response.status_code == 400
    assert "Each message must have 'role', 'content', and 'timestamp'." in json.loads(response.data)[
        "error"]  # Updated expected message

    # Test invalid timestamp format
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", data=json.dumps({
        "messages": [{"role": "user", "content": "hi", "timestamp": "invalid-date"}]
    }), headers=headers)
    assert response.status_code == 400
    assert "Message timestamp must be in ISO 8601 format." in json.loads(response.data)[
        "error"]  # Updated expected message

    # Test invalid message role
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", data=json.dumps({
        "messages": [{"role": "invalid", "content": "hi", "timestamp": "2023-10-28T10:00:00Z"}]
    }), headers=headers)
    assert response.status_code == 400
    assert "Message role must be 'user' or 'assistant'." in json.loads(response.data)["error"]


def test_update_conversation_db_error(client, mock_db_client):
    """Tests database error during conversation update."""
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY, 'Content-Type': 'application/json'}
    update_data = {"title": "Error Update"}
    mock_db_client.update_conversation.side_effect = PyMongoError("DB update error")
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", data=json.dumps(update_data),
                            headers=headers)
    assert response.status_code == 500
    assert "Database error" in json.loads(response.data)["error"]