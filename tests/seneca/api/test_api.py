import io
import json
from unittest.mock import patch, MagicMock

import pytest

# Import your Flask application (ensure 'api' is the Flask object)
# We assume the import structure is correct from the project root
from src.seneca.api.api import api as flask_app

# Mock of the languages returned by the /seneca/v1/stt/languages endpoint
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
    "code": "fa",
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
    "code": "hy",
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

# Mock the FasterWhisper model so it's not actually loaded
# and to control the return value of transcribe
# Removed the top-level patch to avoid interference with the fixture.
# with patch('faster_whisper.WhisperModel') as MockWhisperModel:
#     mock_instance = MockWhisperModel.return_value
#     mock_instance.transcribe.return_value = ([MagicMock(text="Mocked transcription")], MagicMock(language="en", language_probability=1.0))

@pytest.fixture
def client():
    """Configures the test client for the Flask application."""
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

@pytest.fixture
def mock_whisper_model_fixture():
    """Fixture to mock the faster-whisper model in tests."""
    # Patch the 'model' object directly in the api module
    with patch('src.seneca.api.api.model') as MockWhisperModel:
        # Configure a default value for transcribe
        MockWhisperModel.transcribe.return_value = ([MagicMock(text="Mocked transcription")], MagicMock(language="en", language_probability=1.0))
        yield MockWhisperModel

@pytest.fixture
def mock_tempfile_fixture():
    """Fixture to mock tempfile.NamedTemporaryFile and os.remove."""
    with patch('tempfile.NamedTemporaryFile') as MockNamedTemporaryFile:
        mock_file_obj = MagicMock()
        mock_file_obj.name = "/tmp/mock_audio_file.mp3" # Simulated file name
        MockNamedTemporaryFile.return_value.__enter__.return_value = mock_file_obj
        with patch('os.remove') as MockOsRemove:
            yield mock_file_obj, MockOsRemove

# --- Tests for /seneca/v1/stt ---

def test_stt_success_mp3(client, mock_whisper_model_fixture, mock_tempfile_fixture):
    """
    Tests successful transcription of an MP3 file with a specified language.
    The /seneca/v1/stt method receives the lang=es parameter and in the body an mp3 file
    (simulated) and returns the following: { "text": " 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10" }
    """
    mock_file_obj, mock_os_remove = mock_tempfile_fixture
    
    # Configure the mock to return the specific text
    mock_whisper_model_fixture.transcribe.return_value = (
        [MagicMock(text=" 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10")],
        MagicMock(language="es", language_probability=1.0)
    )

    # Simulate the MP3 file content
    dummy_mp3_content = b"fake mp3 audio data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), '1-10-sp.mp3'),
        'lang': 'es'
    }
    response = client.post('/seneca/v1/stt', data=data, content_type='multipart/form-data')

    assert response.status_code == 200
    assert json.loads(response.data) == {"text": " 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10"}
    mock_whisper_model_fixture.transcribe.assert_called_once_with(mock_file_obj.name, language='es')
    mock_os_remove.assert_called_once_with(mock_file_obj.name)

def test_stt_no_file_provided(client):
    """Tests the case where no file is provided."""
    response = client.post('/seneca/v1/stt', data={}, content_type='multipart/form-data')
    assert response.status_code == 400
    assert json.loads(response.data) == {"error": "No audio file provided"}

def test_stt_empty_file(client):
    """Tests the case where an empty file is provided."""
    dummy_empty_content = b""
    data = {
        'file': (io.BytesIO(dummy_empty_content), 'empty.mp3')
    }
    response = client.post('/seneca/v1/stt', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert json.loads(response.data) == {"error": "Empty audio file"}

def test_stt_invalid_file_type(client):
    """Tests the case of an disallowed file type."""
    dummy_txt_content = b"this is a text file"
    data = {
        'file': (io.BytesIO(dummy_txt_content), 'test.txt')
    }
    response = client.post('/seneca/v1/stt', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert json.loads(response.data) == {"error": "Invalid file type. Only .wav and .mp3 are supported."}

def test_stt_model_not_loaded(client):
    """Tests the case where the Faster-Whisper model has not been loaded."""
    with patch('src.seneca.api.api.model', None): # Mocks the global model to None
        dummy_mp3_content = b"fake mp3 audio data"
        data = {
            'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
        }
        response = client.post('/seneca/v1/stt', data=data, content_type='multipart/form-data')
        assert response.status_code == 503
        assert json.loads(response.data) == {"error": "Speech-to-Text service is unavailable."}

def test_stt_transcription_error(client, mock_whisper_model_fixture, mock_tempfile_fixture):
    """Tests the case where faster-whisper transcription fails."""
    # The actual error message from faster-whisper when given invalid audio data
    expected_error_message = "[Errno 1094995529] Invalid data found when processing input: '/tmp/mock_audio_file.mp3'"
    mock_whisper_model_fixture.transcribe.side_effect = Exception(expected_error_message)
    mock_file_obj, mock_os_remove = mock_tempfile_fixture
    dummy_mp3_content = b"fake mp3 audio data"
    data = {
        'file': (io.BytesIO(dummy_mp3_content), 'test_audio.mp3')
    }
    response = client.post('/seneca/v1/stt', data=data, content_type='multipart/form-data')
    assert response.status_code == 500
    assert json.loads(response.data) == {"error": expected_error_message}
    mock_os_remove.assert_called_once_with(mock_file_obj.name)


# --- Tests for /seneca/v1/stt/languages ---

def test_get_supported_languages(client):
    """
    Tests the endpoint for getting supported languages.
    The /seneca/v1/stt/languages method returns the MOCKED_LANGUAGES list.
    """
    # Mock whisper.tokenizer.LANGUAGES only for this test
    with patch('whisper.tokenizer.LANGUAGES', {lang['code']: lang['name'] for lang in MOCKED_LANGUAGES}):
        response = client.get('/seneca/v1/stt/languages')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert data == MOCKED_LANGUAGES