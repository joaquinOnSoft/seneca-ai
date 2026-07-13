import io
import json
from time import sleep
from unittest.mock import patch, MagicMock
import datetime as dt
from http import HTTPStatus # Import HTTPStatus for standard status codes

import pytest
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError
from seneca.utils.passlib_bcrypt_fix import _passlib_bcrypt_module  # noqa: F401
from passlib.hash import bcrypt

from seneca.api.api import api as flask_app
from seneca.api.api import _prepare_response_data, MongoJsonEncoder, generate_jwt, generate_refresh_token, \
    hash_refresh_token, verify_refresh_token
from seneca.api.database import MongoDatabase


# Mock config for JWT
class MockConfig:
    def __init__(self):
        self.mongodb_uri = "mongodb://mock_host:27017/mock_db"
        self.jwt_access_token_expires_in = 900  # 15 minutes
        self.jwt_refresh_token_expires_in_days = 7
        self.jwt_secret_key = "super-secret-test-key"
        self.seneca_ai_api_key = "test-seneca-ai-api-key"
        self.whisper_model_size = "small"
        self.whisper_device = "cpu"
        self.whisper_compute_type = "int8"
        self.stt_backend = "faster-whisper"


# Patch config globally for tests
with patch('seneca.api.api.config', new=MockConfig()):
    from seneca.api.api import config


API_METHOD_HEALTH = '/senecaai/v1/health'
API_METHOD_STT_LANGUAGES = '/senecaai/v1/stt/languages'
API_METHOD_STT = '/senecaai/v1/stt'

API_METHOD_CONVERSATIONS = '/senecaai/v1/conversations'
API_METHOD_CONVERSATION_BY_ID = '/senecaai/v1/conversations/'
API_METHOD_AUTH_LOGIN = '/senecaai/v1/auth/login'
API_METHOD_AUTH_REFRESH = '/senecaai/v1/auth/refresh'
API_METHOD_AUTH_LOGOUT = '/senecaai/v1/auth/logout'

TEST_API_KEY = "test-seneca-ai-api-key"
TEST_USER_ID = str(ObjectId())
TEST_USER_NAME = "testuser"
TEST_PASSWORD = "testpassword"
TEST_PASSWORD_HASH = bcrypt.hash(TEST_PASSWORD[:72])
TEST_USER_FULL_NAME = "Test User"

TEST_CONVERSATION_ID_1 = str(ObjectId())
TEST_CONVERSATION_ID_2 = str(ObjectId())
TEST_CONVERSATION_ID_OTHER_USER = str(ObjectId())
TEST_CONVERSATION_ID_NEW = str(ObjectId())

TEST_DATETIME_1 = dt.datetime(2023, 10, 27, 15, 59, 50, tzinfo=dt.timezone.utc)
TEST_DATETIME_2 = dt.datetime(2023, 10, 26, 10, 30, 0, tzinfo=dt.timezone.utc)
TEST_DATETIME_NEW_MSG = dt.datetime(2023, 10, 28, 10, 0, 0, tzinfo=dt.timezone.utc)
TEST_DATETIME_UPDATED_MSG = dt.datetime(2023, 10, 29, 10, 0, 0, tzinfo=dt.timezone.utc)

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

def conversation_to_json_compatible(conv):
    return _prepare_response_data(conv)

MOCKED_LANGUAGES = [
    {"code": "en", "name": "english"},
    {"code": "zh", "name": "chinese"},
    {"code": "de", "name": "german"},
    {"code": "es", "name": "spanish"},
    {"code": "ru", "name": "russian"},
    {"code": "ko", "name": "korean"},
    {"code": "fr", "name": "french"},
    {"code": "ja", "name": "japanese"},
    {"code": "pt", "name": "portuguese"},
    {"code": "tr", "name": "turkish"},
    {"code": "pl", "name": "polish"},
    {"code": "ca", "name": "catalan"},
    {"code": "nl", "name": "dutch"},
    {"code": "ar", "name": "arabic"},
    {"code": "sv", "name": "swedish"},
    {"code": "it", "name": "italian"},
    {"code": "id", "name": "indonesian"},
    {"code": "hi", "name": "hindi"},
    {"code": "fi", "name": "finnish"},
    {"code": "vi", "name": "vietnamese"},
    {"code": "he", "name": "hebrew"},
    {"code": "uk", "name": "ukrainian"},
    {"code": "el", "name": "greek"},
    {"code": "ms", "name": "malay"},
    {"code": "cs", "name": "czech"},
    {"code": "ro", "name": "romanian"},
    {"code": "da", "name": "danish"},
    {"code": "hu", "name": "hungarian"},
    {"code": "ta", "name": "tamil"},
    {"code": "no", "name": "norwegian"},
    {"code": "th", "name": "thai"},
    {"code": "ur", "name": "urdu"},
    {"code": "hr", "name": "croatian"},
    {"code": "bg", "name": "bulgarian"},
    {"code": "lt", "name": "lithuanian"},
    {"code": "la", "name": "latin"},
    {"code": "mi", "name": "maori"},
    {"code": "ml", "name": "malayalam"},
    {"code": "cy", "name": "welsh"},
    {"code": "sk", "name": "slovak"},
    {"code": "te", "name": "telugu"},
    {"code": "fa", "name": "persian"},
    {"code": "lv", "name": "latvian"},
    {"code": "bn", "name": "bengali"},
    {"code": "sr", "name": "serbian"},
    {"code": "az", "name": "azerbaijani"},
    {"code": "sl", "name": "slovenian"},
    {"code": "kn", "name": "kannada"},
    {"code": "et", "name": "estonian"},
    {"code": "mk", "name": "macedonian"},
    {"code": "br", "name": "breton"},
    {"code": "eu", "name": "basque"},
    {"code": "is", "name": "icelandic"},
    {"code": "hy", "name": "armenian"},
    {"code": "ne", "name": "nepali"},
    {"code": "mn", "name": "mongolian"},
    {"code": "bs", "name": "bosnian"},
    {"code": "kk", "name": "kazakh"},
    {"code": "sq", "name": "albanian"},
    {"code": "sw", "name": "swahili"},
    {"code": "gl", "name": "galician"},
    {"code": "mr", "name": "marathi"},
    {"code": "pa", "name": "punjabi"},
    {"code": "si", "name": "sinhala"},
    {"code": "km", "name": "khmer"},
    {"code": "sn", "name": "shona"},
    {"code": "yo", "name": "yoruba"},
    {"code": "so", "name": "somali"},
    {"code": "af", "name": "afrikaans"},
    {"code": "oc", "name": "occitan"},
    {"code": "ka", "name": "georgian"},
    {"code": "be", "name": "belarusian"},
    {"code": "tg", "name": "tajik"},
    {"code": "sd", "name": "sindhi"},
    {"code": "gu", "name": "gujarati"},
    {"code": "am", "name": "amharic"},
    {"code": "yi", "name": "yiddish"},
    {"code": "lo", "name": "lao"},
    {"code": "uz", "name": "uzbek"},
    {"code": "fo", "name": "faroese"},
    {"code": "ht", "name": "haitian creole"},
    {"code": "ps", "name": "pashto"},
    {"code": "tk", "name": "turkmen"},
    {"code": "nn", "name": "nynorsk"},
    {"code": "mt", "name": "maltese"},
    {"code": "sa", "name": "sanskrit"},
    {"code": "lb", "name": "luxembourgish"},
    {"code": "my", "name": "myanmar"},
    {"code": "bo", "name": "tibetan"},
    {"code": "tl", "name": "tagalog"},
    {"code": "mg", "name": "malagasy"},
    {"code": "as", "name": "assamese"},
    {"code": "tt", "name": "tatar"},
    {"code": "haw", "name": "hawaiian"},
    {"code": "ln", "name": "lingala"},
    {"code": "ha", "name": "hausa"},
    {"code": "ba", "name": "bashkir"},
    {"code": "jw", "name": "javanese"},
    {"code": "su", "name": "sundanese"},
    {"code": "yue", "name": "cantonese"}
]


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True

    mock_config = MagicMock()
    mock_config.seneca_ai_api_key = TEST_API_KEY
    mock_config.whisper_model_size = "small"
    mock_config.whisper_device = "cpu"
    mock_config.whisper_compute_type = "int8"
    mock_config.hf_token = None
    mock_config.stt_backend = "faster-whisper"
    mock_config.mongodb_uri = "mongodb://mock_host:27017/mock_db"
    mock_config.jwt_access_token_expires_in = 900
    mock_config.jwt_refresh_token_expires_in_days = 7
    mock_config.jwt_secret_key = "super-secret-test-key"

    with patch('seneca.api.api.config', new=mock_config):
        flask_app.config["LIMITER_ENABLED"] = False
        flask_app.config["RATELIMIT_ENABLED"] = False

        from seneca.api.api import limiter
        limiter.enabled = False

        with flask_app.test_client() as client:
            yield client


@pytest.fixture
def mock_whisper_model_fixture():
    with patch('seneca.api.api.model') as MockWhisperModel:
        MockWhisperModel.transcribe.return_value = ([MagicMock(text="Mocked transcription")],
                                                    MagicMock(language="en", language_probability=1.0))
        yield MockWhisperModel


@pytest.fixture
def mock_temp_file_fixture():
    with patch('tempfile.NamedTemporaryFile') as MockNamedTemporaryFile:
        mock_file_obj = MagicMock()
        mock_file_obj.name = "/tmp/mock_audio_file.mp3"
        MockNamedTemporaryFile.return_value.__enter__.return_value = mock_file_obj
        with patch('os.remove') as MockOsRemove:
            yield mock_file_obj, MockOsRemove


@pytest.fixture(autouse=True)
def delay_to_avoid_too_many_request_per_second():
    sleep(0.01)


@pytest.fixture
def mock_db_client():
    _users_store = {
        ObjectId(TEST_USER_ID): {
            "_id": ObjectId(TEST_USER_ID),
            "user_id": TEST_USER_ID,
            "user_name": TEST_USER_NAME,
            "user_full_name": TEST_USER_FULL_NAME,
            "password_hash": TEST_PASSWORD_HASH,
            "refresh_tokens": []
        }
    }
    _conversations_store = {
        ObjectId(SAMPLE_CONVERSATION_1["_id"]): SAMPLE_CONVERSATION_1.copy(),
        ObjectId(SAMPLE_CONVERSATION_2["_id"]): SAMPLE_CONVERSATION_2.copy(),
        ObjectId(SAMPLE_CONVERSATION_OTHER_USER["_id"]): SAMPLE_CONVERSATION_OTHER_USER.copy(),
    }

    mock_db_instance = MagicMock()
    mock_db_instance.is_connected.return_value = True
    mock_db_instance._is_mock = True

    mock_db_instance.users_collection = MagicMock()
    mock_db_instance.conversations_collection = MagicMock()

    mock_db_instance.get_conversations.side_effect = lambda user_id, skip=0, limit=20: \
        [doc.copy() for doc in _conversations_store.values() if doc.get("user_id") == user_id][skip: skip + limit]

    mock_db_instance.get_conversation_by_id.side_effect = lambda conv_id_str, user_id=None: \
        _conversations_store.get(ObjectId(conv_id_str)).copy() if ObjectId(conv_id_str) in _conversations_store and \
                                                                  (user_id is None or _conversations_store.get(
                                                                      ObjectId(conv_id_str)).get(
                                                                      "user_id") == user_id) else None

    mock_db_instance.check_conversation_exists.side_effect = lambda conv_id_str: \
        ObjectId(conv_id_str) in _conversations_store

    mock_db_instance.create_conversation.side_effect = lambda user_id, title, messages: \
        _create_mock_conversation(user_id, title, messages, _conversations_store)

    mock_db_instance.update_conversation.side_effect = lambda conv_id_str, user_id, update_fields: \
        _update_mock_conversation(conv_id_str, user_id, update_fields, _conversations_store)

    mock_db_instance.get_user_by_username.side_effect = lambda username: \
        next((user_doc.copy() for user_doc in _users_store.values() if user_doc["user_name"] == username), None)

    mock_db_instance.get_user_by_id.side_effect = lambda user_id: \
        _users_store.get(ObjectId(user_id))

    mock_db_instance.find_user_by_refresh_token.side_effect = lambda refresh_token_to_find: \
        _find_user_by_refresh_token_mock(refresh_token_to_find, _users_store)

    mock_db_instance.add_refresh_token_to_user.side_effect = lambda user_id, hashed_token, expires_at: \
        _add_refresh_token_to_user_mock(user_id, hashed_token, expires_at, _users_store)

    mock_db_instance.revoke_refresh_token.side_effect = lambda user_id, refresh_token_to_revoke: \
        _revoke_refresh_token_mock(user_id, refresh_token_to_revoke, _users_store)

    def _create_mock_conversation(user_id, title, messages, store):
        new_id = ObjectId()
        doc = {
            "_id": new_id,
            "user_id": user_id,
            "title": title,
            "created_at": TEST_DATETIME_NEW_MSG,
            "messages": messages
        }
        store[new_id] = doc
        return doc

    def _update_mock_conversation(conv_id_str, user_id, update_fields, store):
        conv_obj_id = ObjectId(conv_id_str)
        if conv_obj_id in store and store[conv_obj_id].get("user_id") == user_id:
            for key, value in update_fields.items():
                store[conv_obj_id][key] = value
            return True
        return False

    def _find_user_by_refresh_token_mock(refresh_token_to_find, store):
        for user_doc in store.values():
            for rt_entry in user_doc.get("refresh_tokens", []):
                if bcrypt.verify(refresh_token_to_find, rt_entry["token_hash"]) and \
                        rt_entry["expires_at"] > dt.datetime.now(dt.timezone.utc) and \
                        not rt_entry["revoked"]:
                    return user_doc
        return None

    def _add_refresh_token_to_user_mock(user_id, hashed_token, expires_at, store):
        user_obj_id = ObjectId(user_id)
        if user_obj_id in store:
            user_doc = store[user_obj_id]
            user_doc.setdefault("refresh_tokens", []).append({
                "token_hash": hashed_token,
                "issued_at": dt.datetime.now(dt.timezone.utc),
                "expires_at": expires_at, # Use the passed expires_at
                "revoked": False
            })
            return True
        return False

    def _revoke_refresh_token_mock(user_id, refresh_token_to_revoke, store):
        user_obj_id = ObjectId(user_id)
        if user_obj_id in store:
            user_doc = store[user_obj_id]
            for rt_entry in user_doc.get("refresh_tokens", []):
                if bcrypt.verify(refresh_token_to_revoke, rt_entry["token_hash"]):
                    rt_entry["revoked"] = True
                    return True
        return False

    mock_db_instance._users_store_accessor = _users_store
    mock_db_instance._conversations_store_accessor = _conversations_store

    with patch('seneca.api.api.db_client', new=mock_db_instance):
        yield mock_db_instance


# --- Tests for /senecaai/v1/stt ---

def test_stt_success_mp3(client, mock_whisper_model_fixture, mock_temp_file_fixture, mock_db_client):
    mock_file_obj, mock_os_remove = mock_temp_file_fixture

    mock_whisper_model_fixture.transcribe.return_value = (
        [MagicMock(text=" 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10")],
        MagicMock(language="es", language_probability=1.0)
    )

    dummy_mp3_content = b"fake mp3 audio data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), '1-10-sp.mp3'),
        'lang': 'es'
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    response = client.post(API_METHOD_STT, data=data, content_type='multipart/form-data', headers=headers)

    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.data) == {"text": " 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10"}
    mock_whisper_model_fixture.transcribe.assert_called_once_with(mock_file_obj.name, language='es')
    mock_os_remove.assert_called_once_with(mock_file_obj.name)


def test_stt_success_google_backend(client, mock_temp_file_fixture, mock_db_client):
    mock_file_obj, mock_os_remove = mock_temp_file_fixture

    with patch('seneca.api.api.config.stt_backend', 'google'):
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

            assert response.status_code == HTTPStatus.OK
            assert json.loads(response.data) == {"text": "Google transcription result"}
            mock_recognize.assert_called_once()
            mock_os_remove.assert_called_once_with(mock_file_obj.name)


def test_stt_no_file_provided(client, mock_db_client):
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    response = client.post(API_METHOD_STT, data={}, content_type='multipart/form-data', headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert json.loads(response.data) == {"error": "No audio file provided"}


def test_stt_empty_file(client, mock_db_client):
    dummy_empty_content = b""
    data = {
        'file': (io.BytesIO(dummy_empty_content), 'empty.mp3')
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    response = client.post(API_METHOD_STT, data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert json.loads(response.data) == {"error": "Empty audio file"}


def test_stt_invalid_file_type(client, mock_db_client):
    dummy_txt_content = b"this is a text file"
    data = {
        'file': (io.BytesIO(dummy_txt_content), 'test.txt')
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert json.loads(response.data) == {"error": "Invalid file type. Only .wav and .mp3 are supported."}


def test_stt_model_not_loaded(client, mock_db_client):
    with patch('seneca.api.api.model', None):
        dummy_mp3_content = b"fake mp3 audio data"
        data = {
            'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
        }
        headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
        response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data', headers=headers)
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert json.loads(response.data) == {"error": "Speech-to-Text service is unavailable."}


def test_stt_transcription_error(client, mock_whisper_model_fixture, mock_temp_file_fixture, mock_db_client):
    expected_error_message = "An internal server error occurred during transcription."
    mock_whisper_model_fixture.transcribe.side_effect = Exception("Whisper internal error")
    mock_file_obj, mock_os_remove = mock_temp_file_fixture
    dummy_mp3_content = b"fake mp3 audio data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
    }
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    response = client.post(API_METHOD_STT, data=data, content_type='multipart/form-data',
                           headers=headers)

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert json.loads(response.data) == {"error": expected_error_message}


def test_stt_missing_api_key(client, mock_db_client):
    dummy_mp3_content = b"fake mp3 audio data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
    }
    response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data')
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Authentication required"}


def test_stt_invalid_api_key(client, mock_db_client):
    dummy_mp3_content = b"fake mp3 audio data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
    }
    headers = {'X-SENECA-AI-API-KEY': "invalid-key"}
    response = client.post('/senecaai/v1/stt', data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Unauthorized: Invalid API Key"}


# --- Tests for /senecaai/v1/stt/languages ---

def test_get_supported_languages(client, mock_db_client):
    with patch('whisper.tokenizer.LANGUAGES', {lang['code']: lang['name'] for lang in MOCKED_LANGUAGES}):
        headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
        response = client.get(API_METHOD_STT_LANGUAGES, headers=headers)
        assert response.status_code == HTTPStatus.OK
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert data == MOCKED_LANGUAGES


def test_get_supported_languages_missing_api_key(client, mock_db_client):
    response = client.get(API_METHOD_STT_LANGUAGES)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Authentication required"}


def test_get_supported_languages_invalid_api_key(client, mock_db_client):
    headers = {'X-SENECA-AI-API-KEY': "invalid-key"}
    response = client.get(API_METHOD_STT_LANGUAGES, headers=headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Unauthorized: Invalid API Key"}


# --- Tests for /senecaai/v1/health ---

def test_health_check_model_loaded(client, mock_whisper_model_fixture, mock_db_client):
    response = client.get(API_METHOD_HEALTH)
    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.data) == {"status": "ok", "model_status": "loaded"}


def test_health_check_google_backend(client, mock_db_client):
    with patch('seneca.api.api.config.stt_backend', 'google'):
        response = client.get(API_METHOD_HEALTH)
        assert response.status_code == HTTPStatus.OK
        assert json.loads(response.data) == {"status": "ok", "model_status": "google_online"}


def test_health_check_model_not_loaded(client, mock_db_client):
    with patch('seneca.api.api.model', None):
        response = client.get(API_METHOD_HEALTH) # Health check itself should return 503 if model not loaded
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert json.loads(response.data) == {"status": "degraded", "model_status": "not loaded"}


# --- New test for Rate Limiting ---
def test_rate_limiting(client, mock_whisper_model_fixture, mock_temp_file_fixture, mock_db_client):
    mock_file_obj, mock_os_remove = mock_temp_file_fixture
    mock_whisper_model_fixture.transcribe.return_value = (
        [MagicMock(text="Mocked transcription")],
        MagicMock(language="en", language_probability=1.0)
    )

    endpoint = API_METHOD_STT
    headers = {'X-SENECA-AI-API-KEY': TEST_API_KEY}
    dummy_mp3_content = b"fake mp3 audio data"

    for i in range(5):
        data = {
            'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3'),
            'lang': 'en'
        }
        response = client.post(endpoint, data=data, content_type='multipart/form-data', headers=headers)
        assert response.status_code == HTTPStatus.OK, f"Request {i + 1} failed unexpectedly with status {response.status_code}"

    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3'),
        'lang': 'en'
    }
    response = client.post(endpoint, data=data, content_type='multipart/form-data', headers=headers)
    assert response.status_code == HTTPStatus.OK, f"Expected 200, but got {response.status_code}"


# --- Tests for Authentication Endpoints ---

@pytest.fixture
def auth_tokens(client, mock_db_client):
    user_id = ObjectId(TEST_USER_ID)
    mock_db_client._users_store_accessor[user_id] = {
        "_id": user_id,
        "user_id": TEST_USER_ID,
        "user_name": TEST_USER_NAME,
        "user_full_name": TEST_USER_FULL_NAME,
        "password_hash": TEST_PASSWORD_HASH,
        "refresh_tokens": []
    }

    login_data = {
        "username": TEST_USER_NAME,
        "password": TEST_PASSWORD
    }
    response = client.post(API_METHOD_AUTH_LOGIN, json=login_data)
    assert response.status_code == HTTPStatus.OK
    return json.loads(response.data)


def test_auth_login_success(client, mock_db_client):
    user_id = ObjectId(TEST_USER_ID)
    mock_db_client._users_store_accessor[user_id] = {
        "_id": user_id,
        "user_id": TEST_USER_ID,
        "user_name": TEST_USER_NAME,
        "user_full_name": TEST_USER_FULL_NAME,
        "password_hash": TEST_PASSWORD_HASH,
        "refresh_tokens": []
    }

    login_data = {
        "username": TEST_USER_NAME,
        "password": TEST_PASSWORD
    }
    response = client.post(API_METHOD_AUTH_LOGIN, json=login_data)
    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == config.jwt_access_token_expires_in

    user_in_db = mock_db_client.get_user_by_id(user_id)
    assert user_in_db is not None
    assert len(user_in_db["refresh_tokens"]) == 1
    assert bcrypt.verify(data["refresh_token"], user_in_db["refresh_tokens"][0]["token_hash"])
    assert not user_in_db["refresh_tokens"][0]["revoked"]
    assert user_in_db["refresh_tokens"][0]["expires_at"] > dt.datetime.now(dt.timezone.utc)


def test_auth_login_invalid_credentials(client, mock_db_client):
    user_id = ObjectId(TEST_USER_ID)
    mock_db_client._users_store_accessor[user_id] = {
        "_id": user_id,
        "user_id": TEST_USER_ID,
        "user_name": TEST_USER_NAME,
        "user_full_name": TEST_USER_FULL_NAME,
        "password_hash": TEST_PASSWORD_HASH,
        "refresh_tokens": []
    }
    login_data = {
        "username": TEST_USER_NAME,
        "password": "wrongpassword"
    }
    response = client.post(API_METHOD_AUTH_LOGIN, json=login_data)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Invalid username or password."}


def test_auth_login_missing_fields(client, mock_db_client):
    response = client.post(API_METHOD_AUTH_LOGIN, json={"username": TEST_USER_NAME})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert json.loads(response.data) == {"error": "Missing username or password."}


def test_auth_refresh_success(client, auth_tokens, mock_db_client):
    refresh_token = auth_tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {refresh_token}"}
    response = client.post(API_METHOD_AUTH_REFRESH, headers=headers)
    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == config.jwt_access_token_expires_in


def test_auth_refresh_invalid_token(client, mock_db_client):
    headers = {"Authorization": f"Bearer invalid_refresh_token"}
    response = client.post(API_METHOD_AUTH_REFRESH, headers=headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Invalid or expired refresh token."}


def test_auth_refresh_expired_token(client, auth_tokens, mock_db_client):
    user_id = ObjectId(TEST_USER_ID)
    user_in_store = mock_db_client.get_user_by_id(user_id)
    for rt_entry in user_in_store["refresh_tokens"]:
        rt_entry["expires_at"] = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)

    refresh_token = auth_tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {refresh_token}"}
    response = client.post(API_METHOD_AUTH_REFRESH, headers=headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Invalid or expired refresh token."}


def test_auth_logout_success(client, auth_tokens, mock_db_client):
    refresh_token = auth_tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {refresh_token}"}
    response = client.post(API_METHOD_AUTH_LOGOUT, headers=headers)
    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.data) == {"message": "Logout successful."}

    user_id = ObjectId(TEST_USER_ID)
    user_in_db = mock_db_client._users_store_accessor[user_id]
    assert user_in_db["refresh_tokens"][0]["revoked"] is True


def test_auth_logout_invalid_token(client, mock_db_client):
    headers = {"Authorization": f"Bearer invalid_refresh_token"}
    response = client.post(API_METHOD_AUTH_LOGOUT, headers=headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert json.loads(response.data) == {"error": "Invalid refresh token."}


# --- Tests for Conversation Management Endpoints ---

def test_get_conversations_success(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}

    response = client.get(API_METHOD_CONVERSATIONS, headers=headers)

    assert response.status_code == HTTPStatus.OK
    expected_conversations = [
        conversation_to_json_compatible(SAMPLE_CONVERSATION_1),
        conversation_to_json_compatible(SAMPLE_CONVERSATION_2)
    ]
    assert json.loads(response.data) == expected_conversations
    mock_db_client.get_conversations.assert_called_once_with(TEST_USER_ID, skip=0, limit=20)


def test_get_conversations_pagination(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}

    response = client.get(f"{API_METHOD_CONVERSATIONS}?convPerPage=1&numPage=2", headers=headers)

    assert response.status_code == HTTPStatus.OK

    expected_conversations = [conversation_to_json_compatible(SAMPLE_CONVERSATION_2)]
    assert json.loads(response.data) == expected_conversations
    mock_db_client.get_conversations.assert_called_once_with(TEST_USER_ID, skip=1, limit=1)


def test_get_conversations_invalid_pagination(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}
    response = client.get(f"{API_METHOD_CONVERSATIONS}?convPerPage=-1&numPage=abc", headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid pagination parameters. 'convPerPage' and 'numPage' must be integers." in json.loads(response.data)["error"]


def test_get_conversations_db_error(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}
    mock_db_client.get_conversations.side_effect = PyMongoError("DB connection lost")
    response = client.get(API_METHOD_CONVERSATIONS, headers=headers)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Database error occurred." in json.loads(response.data)["error"]


def test_get_conversation_by_id_success(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}

    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", headers=headers)

    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.data) == conversation_to_json_compatible(SAMPLE_CONVERSATION_1)
    mock_db_client.get_conversation_by_id.assert_called_once_with(TEST_CONVERSATION_ID_1, user_id=TEST_USER_ID)


def test_get_conversation_by_id_not_found(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}

    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{str(ObjectId())}", headers=headers)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Conversation not found" in json.loads(response.data)["error"]


def test_get_conversation_by_id_invalid_id_format(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}
    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}invalid_id_format", headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid conversation ID format." in json.loads(response.data)["error"]


def test_get_conversation_by_id_forbidden(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}

    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_OTHER_USER}", headers=headers)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "User does not have access to this conversation." in json.loads(response.data)["error"]


def test_get_conversation_by_id_db_error(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}"}
    mock_db_client.get_conversation_by_id.side_effect = PyMongoError("DB connection lost")
    response = client.get(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", headers=headers)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Database error occurred." in json.loads(response.data)["error"]


def test_create_conversation_success(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}
    new_conversation_data = {
        "title": "Nueva Conversación de Prueba",
        "messages": [
            {"role": "user", "content": "¿Qué tal el tiempo hoy?",
             "timestamp": TEST_DATETIME_NEW_MSG.isoformat().replace('+00:00', 'Z')}
        ]
    }

    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps(new_conversation_data), headers=headers)

    assert response.status_code == HTTPStatus.CREATED
    response_data = json.loads(response.data)
    assert "_id" in response_data
    assert response_data["user_id"] == TEST_USER_ID
    assert response_data["title"] == new_conversation_data["title"]
    assert response_data["messages"] == new_conversation_data["messages"]
    assert "Location" in response.headers
    assert response.headers["Location"] == f"http://localhost{API_METHOD_CONVERSATIONS}/{response_data['_id']}"

    mock_db_client.create_conversation.assert_called_once_with(TEST_USER_ID, new_conversation_data["title"],
                                                               new_conversation_data["messages"])


def test_create_conversation_invalid_data(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}

    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({"messages": []}), headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Title is required and must be a string." in json.loads(response.data)["error"]

    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({"title": "Test", "messages": "not a list"}),
                           headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Messages must be a list." in json.loads(response.data)["error"]

    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps(
        {"title": "Test", "messages": [{"role": "user", "timestamp": "2023-10-28T10:00:00+00:00"}]}), headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Each message must have 'role', 'content', and 'timestamp'." in json.loads(response.data)["error"]

    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({
        "title": "Test",
        "messages": [{"role": "user", "content": "hi", "timestamp": "invalid-date"}]
    }), headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Message timestamp must be in ISO 8601 format." in json.loads(response.data)["error"]

    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps({
        "title": "Test",
        "messages": [{"role": "invalid", "content": "hi", "timestamp": "2023-10-28T10:00:00Z"}]
    }), headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Message role must be 'user' or 'assistant'." in json.loads(response.data)["error"]


def test_create_conversation_db_error(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}
    new_conversation_data = {
        "title": "Nueva Conversación de Prueba",
        "messages": [
            {"role": "user", "content": "¿Qué tal el tiempo hoy?",
             "timestamp": TEST_DATETIME_NEW_MSG.isoformat().replace('+00:00', 'Z')}
        ]
    }
    mock_db_client.create_conversation.side_effect = PyMongoError("DB write error")
    response = client.post(API_METHOD_CONVERSATIONS, data=json.dumps(new_conversation_data), headers=headers)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Database error occurred." in json.loads(response.data)["error"]


def test_update_conversation_success(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}
    update_data = {
        "title": "Título Actualizado",
        "messages": [
            {"role": "user", "content": "Nuevo mensaje",
             "timestamp": TEST_DATETIME_UPDATED_MSG.isoformat().replace('+00:00', 'Z')}
        ]
    }

    original_conv_id = ObjectId(TEST_CONVERSATION_ID_1)
    mock_db_client._conversations_store_accessor[original_conv_id] = SAMPLE_CONVERSATION_1.copy()

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", data=json.dumps(update_data),
                            headers=headers)

    assert response.status_code == HTTPStatus.OK
    response_data = json.loads(response.data)
    assert "_id" in response_data
    assert response_data["user_id"] == TEST_USER_ID
    assert response_data["title"] == update_data["title"]
    assert response_data["messages"] == update_data["messages"]

    mock_db_client.update_conversation.assert_called_once_with(TEST_CONVERSATION_ID_1, TEST_USER_ID, update_data)

    updated_doc_in_store = mock_db_client.get_conversation_by_id(TEST_CONVERSATION_ID_1, user_id=TEST_USER_ID)
    assert updated_doc_in_store["title"] == update_data["title"]
    assert updated_doc_in_store["messages"] == update_data["messages"]


def test_update_conversation_not_found(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}
    update_data = {"title": "Non Existent"}

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{str(ObjectId())}", json=update_data, headers=headers)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Conversation not found" in json.loads(response.data)["error"]


def test_update_conversation_invalid_id_format(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}
    update_data = {"title": "Invalid ID"}
    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}invalid_id_format", json=update_data, headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid conversation ID format." in json.loads(response.data)["error"]


def test_update_conversation_forbidden(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}
    update_data = {"title": "Forbidden Update"}

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_OTHER_USER}", json=update_data,
                            headers=headers)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "User does not have access to modify this conversation." in json.loads(response.data)["error"]


def test_update_conversation_invalid_data(client, mock_db_client):
    headers = {"Authorization": f"Bearer {generate_jwt(TEST_USER_ID, TEST_USER_NAME)}",
               'Content-Type': 'application/json'}

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", json={"title": 123},
                            headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Title must be a string." in json.loads(response.data)["error"]

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}",
                            json={"messages": "not a list"}, headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Messages must be a list." in json.loads(response.data)["error"]

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}",
                            json={"messages": [{"role": "user", "timestamp": "2023-10-28T10:00:00+00:00"}]},
                            headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Each message must have 'role', 'content', and 'timestamp'." in json.loads(response.data)["error"]

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", json={
        "messages": [{"role": "user", "content": "hi", "timestamp": "invalid-date"}]
    }, headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Message timestamp must be in ISO 8601 format." in json.loads(response.data)["error"]

    response = client.patch(f"{API_METHOD_CONVERSATION_BY_ID}{TEST_CONVERSATION_ID_1}", json={
        "messages": [{"role": "invalid", "content": "hi", "timestamp": "2023-10-28T10:00:00Z"}]
    }, headers=headers)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Message role must be 'user' or 'assistant'." in json.loads(response.data)["error"]