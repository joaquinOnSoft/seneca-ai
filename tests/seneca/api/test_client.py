"""
tests/seneca/api/test_client.py – Unit tests for :class:`SenecaApiClient`.

Every external HTTP call is replaced by :mod:`unittest.mock` objects so that
no network access is needed.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Ensure ``src/`` is importable when running tests from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from seneca.api.client import (
    HealthResponse,
    LanguageInfo,
    SenecaApiClient,
    SenecaApiError,
    SenecaAuthenticationError,
    SenecaBadRequestError,
    SenecaServerError,
    SenecaServiceUnavailableError,
    TranscriptionResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session():
    """Return a mocked :class:`requests.Session`."""
    with patch("seneca.api.client.requests.Session") as mock_cls:
        session_instance = MagicMock()
        mock_cls.return_value = session_instance
        yield session_instance


@pytest.fixture()
def client(mock_session):
    """Return a :class:`SenecaApiClient` whose session is mocked."""
    return SenecaApiClient(
        base_url="http://localhost:1414/",
        api_key="test-key",
        timeout=10.0,
        max_retries=2,
    )


@pytest.fixture()
def client_with_correlation(mock_session):
    """Client with a custom ``correlation_id``."""
    return SenecaApiClient(
        base_url="http://localhost:1414",
        api_key="test-key",
        correlation_id="corr-123",
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitialization:
    """Verify constructor / ``__post_init__`` behaviour."""

    def test_trailing_slash_is_stripped(self, client):
        assert client.base_url == "http://localhost:1414"

    def test_base_url_without_trailing_slash(self, mock_session):
        c = SenecaApiClient(base_url="http://host:8080", api_key="k")
        assert c.base_url == "http://host:8080"

    def test_default_timeout(self, mock_session):
        c = SenecaApiClient(base_url="http://host", api_key="k")
        assert c.timeout == 30.0

    def test_default_max_retries(self, mock_session):
        c = SenecaApiClient(base_url="http://host", api_key="k")
        assert c.max_retries == 3

    def test_session_is_created(self, client, mock_session):
        # ``_build_session`` was called during ``__post_init__``
        assert client._session is mock_session


# ---------------------------------------------------------------------------
# Context-manager protocol
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_enter_returns_self(self, client):
        assert client.__enter__() is client

    def test_exit_closes_session(self, client, mock_session):
        client.__exit__(None, None, None)
        mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_headers_include_api_key(self, client):
        headers = client._headers()
        assert headers["X-SENECA-AI-API-KEY"] == "test-key"

    def test_headers_exclude_api_key_when_requested(self, client):
        headers = client._headers(include_api_key=False)
        assert "X-SENECA-AI-API-KEY" not in headers

    def test_headers_without_api_key_set(self, mock_session):
        c = SenecaApiClient(base_url="http://host", api_key="")
        headers = c._headers()
        assert "X-SENECA-AI-API-KEY" not in headers

    def test_correlation_id_included(self, client_with_correlation):
        headers = client_with_correlation._headers()
        assert headers["X-Correlation-ID"] == "corr-123"

    def test_no_correlation_id_by_default(self, client):
        headers = client._headers()
        assert "X-Correlation-ID" not in headers


# ---------------------------------------------------------------------------
# _raise_for_status
# ---------------------------------------------------------------------------


class TestRaiseForStatus:
    """Verify the static error-mapping helper."""

    @staticmethod
    def _make_response(status_code, json_body=None, text="", reason="Error"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.ok = 200 <= status_code < 400
        resp.reason = reason
        resp.text = text
        if json_body is not None:
            resp.json.return_value = json_body
        else:
            resp.json.side_effect = ValueError("No JSON")
        return resp

    def test_ok_response_does_nothing(self):
        resp = self._make_response(200)
        SenecaApiClient._raise_for_status(resp)  # should not raise

    def test_400_raises_bad_request(self):
        resp = self._make_response(400, {"error": "missing file"})
        with pytest.raises(SenecaBadRequestError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert exc_info.value.status_code == 400
        assert "missing file" in str(exc_info.value)

    def test_401_raises_authentication_error(self):
        resp = self._make_response(401, {"error": "invalid key"})
        with pytest.raises(SenecaAuthenticationError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert exc_info.value.status_code == 401

    def test_503_raises_service_unavailable(self):
        resp = self._make_response(503, {"error": "model not loaded"})
        with pytest.raises(SenecaServiceUnavailableError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert exc_info.value.status_code == 503

    def test_500_raises_server_error(self):
        resp = self._make_response(500, {"error": "internal"})
        with pytest.raises(SenecaServerError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert exc_info.value.status_code == 500

    def test_502_raises_server_error(self):
        resp = self._make_response(502, {"error": "bad gateway"})
        with pytest.raises(SenecaServerError):
            SenecaApiClient._raise_for_status(resp)

    def test_404_raises_generic_api_error(self):
        resp = self._make_response(404, {"error": "not found"})
        with pytest.raises(SenecaApiError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert type(exc_info.value) is SenecaApiError  # not a subclass

    def test_non_json_error_body(self):
        resp = self._make_response(500, json_body=None, text="oops")
        with pytest.raises(SenecaServerError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert "oops" in str(exc_info.value)

    def test_empty_text_falls_back_to_reason(self):
        resp = self._make_response(500, json_body=None, text="", reason="Internal")
        with pytest.raises(SenecaServerError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert "Internal" in str(exc_info.value)

    def test_response_body_stored_on_exception(self):
        body = {"error": "detail", "extra": 42}
        resp = self._make_response(400, body)
        with pytest.raises(SenecaBadRequestError) as exc_info:
            SenecaApiClient._raise_for_status(resp)
        assert exc_info.value.response_body == body


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_returns_health_response(self, client, mock_session):
        resp = MagicMock()
        resp.json.return_value = {"status": "ok", "model_status": "loaded"}
        resp.ok = True
        mock_session.get.return_value = resp

        result = client.health_check()

        assert isinstance(result, HealthResponse)
        assert result.status == "ok"
        assert result.model_status == "loaded"

    def test_calls_correct_url(self, client, mock_session):
        resp = MagicMock()
        resp.json.return_value = {"status": "ok", "model_status": "loaded"}
        resp.ok = True
        mock_session.get.return_value = resp

        client.health_check()

        args, kwargs = mock_session.get.call_args
        assert args[0] == "http://localhost:1414/senecaai/v1/health"

    def test_does_not_send_api_key(self, client, mock_session):
        resp = MagicMock()
        resp.json.return_value = {"status": "ok", "model_status": "loaded"}
        resp.ok = True
        mock_session.get.return_value = resp

        client.health_check()

        _, kwargs = mock_session.get.call_args
        assert "X-SENECA-AI-API-KEY" not in kwargs["headers"]

    def test_defaults_to_unknown_on_missing_keys(self, client, mock_session):
        resp = MagicMock()
        resp.json.return_value = {}
        resp.ok = True
        mock_session.get.return_value = resp

        result = client.health_check()

        assert result.status == "unknown"
        assert result.model_status == "unknown"

    def test_degraded_503_still_returns_body(self, client, mock_session):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 503
        resp.json.return_value = {"status": "degraded", "model_status": "not loaded"}
        mock_session.get.return_value = resp

        result = client.health_check()

        assert result.status == "degraded"
        assert result.model_status == "not loaded"

    def test_non_json_response_raises(self, client, mock_session):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 500
        resp.json.side_effect = ValueError("no json")
        resp.text = "error"
        resp.reason = "Internal"
        mock_session.get.return_value = resp

        with pytest.raises(SenecaServerError):
            client.health_check()


# ---------------------------------------------------------------------------
# get_supported_languages
# ---------------------------------------------------------------------------


class TestGetSupportedLanguages:
    def test_returns_language_list(self, client, mock_session):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = [
            {"code": "en", "name": "english"},
            {"code": "es", "name": "spanish"},
        ]
        mock_session.get.return_value = resp

        result = client.get_supported_languages()

        assert len(result) == 2
        assert all(isinstance(item, LanguageInfo) for item in result)
        assert result[0].code == "en"
        assert result[1].name == "spanish"

    def test_calls_correct_url(self, client, mock_session):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = []
        mock_session.get.return_value = resp

        client.get_supported_languages()

        args, _ = mock_session.get.call_args
        assert args[0] == "http://localhost:1414/senecaai/v1/stt/languages"

    def test_sends_api_key(self, client, mock_session):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = []
        mock_session.get.return_value = resp

        client.get_supported_languages()

        _, kwargs = mock_session.get.call_args
        assert kwargs["headers"]["X-SENECA-AI-API-KEY"] == "test-key"

    def test_empty_list(self, client, mock_session):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = []
        mock_session.get.return_value = resp

        result = client.get_supported_languages()

        assert result == []

    def test_authentication_error(self, client, mock_session):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 401
        resp.json.return_value = {"error": "invalid key"}
        resp.reason = "Unauthorized"
        mock_session.get.return_value = resp

        with pytest.raises(SenecaAuthenticationError):
            client.get_supported_languages()


# ---------------------------------------------------------------------------
# speech_to_text
# ---------------------------------------------------------------------------


class TestSpeechToText:
    """Tests for the ``speech_to_text`` method."""

    def test_transcription_from_path(self, client, mock_session, tmp_path):
        # Create a temporary audio file.
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF fake audio data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": "hello world"}
        mock_session.post.return_value = resp

        result = client.speech_to_text(str(audio_file), lang="en")

        assert isinstance(result, TranscriptionResult)
        assert result.text == "hello world"

    def test_transcription_from_path_object(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "recording.mp3"
        audio_file.write_bytes(b"fake mp3")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": "hola"}
        mock_session.post.return_value = resp

        result = client.speech_to_text(audio_file, lang="es")

        assert result.text == "hola"

    def test_calls_correct_url(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "a.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(audio_file)

        args, _ = mock_session.post.call_args
        assert args[0] == "http://localhost:1414/senecaai/v1/stt"

    def test_sends_api_key(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "a.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(audio_file)

        _, kwargs = mock_session.post.call_args
        assert kwargs["headers"]["X-SENECA-AI-API-KEY"] == "test-key"

    def test_sends_lang_parameter(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "a.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(audio_file, lang="fr")

        _, kwargs = mock_session.post.call_args
        assert kwargs["data"]["lang"] == "fr"

    def test_default_lang_is_english(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "a.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(audio_file)

        _, kwargs = mock_session.post.call_args
        assert kwargs["data"]["lang"] == "en"

    def test_sends_filename_from_path(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "my_recording.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(audio_file)

        _, kwargs = mock_session.post.call_args
        file_tuple = kwargs["files"]["file"]
        assert file_tuple[0] == "my_recording.wav"

    def test_explicit_filename_overrides_path(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "original.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(audio_file, filename="override.wav")

        _, kwargs = mock_session.post.call_args
        file_tuple = kwargs["files"]["file"]
        assert file_tuple[0] == "override.wav"

    def test_file_not_found_raises(self, client):
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            client.speech_to_text("/nonexistent/path/audio.wav")

    def test_transcription_from_file_object(self, client, mock_session):
        file_obj = io.BytesIO(b"audio bytes")
        file_obj.name = "/tmp/test.wav"

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": "from file object"}
        mock_session.post.return_value = resp

        result = client.speech_to_text(file_obj)

        assert result.text == "from file object"

    def test_file_object_uses_basename(self, client, mock_session):
        file_obj = io.BytesIO(b"audio bytes")
        file_obj.name = "/some/deep/path/recording.wav"

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(file_obj)

        _, kwargs = mock_session.post.call_args
        file_tuple = kwargs["files"]["file"]
        assert file_tuple[0] == "recording.wav"

    def test_file_object_explicit_filename(self, client, mock_session):
        file_obj = io.BytesIO(b"audio bytes")
        # No ``name`` attribute by default on plain BytesIO

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(file_obj, filename="custom.wav")

        _, kwargs = mock_session.post.call_args
        file_tuple = kwargs["files"]["file"]
        assert file_tuple[0] == "custom.wav"

    def test_file_object_without_name_raises_value_error(self, client):
        file_obj = io.BytesIO(b"audio bytes")
        # BytesIO has no ``name`` attribute
        with pytest.raises(ValueError, match="Cannot determine filename"):
            client.speech_to_text(file_obj)

    def test_bad_request_error(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "bad.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = False
        resp.status_code = 400
        resp.json.return_value = {"error": "unsupported format"}
        resp.reason = "Bad Request"
        mock_session.post.return_value = resp

        with pytest.raises(SenecaBadRequestError):
            client.speech_to_text(audio_file)

    def test_service_unavailable_error(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "a.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = False
        resp.status_code = 503
        resp.json.return_value = {"error": "model not loaded"}
        resp.reason = "Service Unavailable"
        mock_session.post.return_value = resp

        with pytest.raises(SenecaServiceUnavailableError):
            client.speech_to_text(audio_file)

    def test_server_error(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "a.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = False
        resp.status_code = 500
        resp.json.return_value = {"error": "internal"}
        resp.reason = "Internal Server Error"
        mock_session.post.return_value = resp

        with pytest.raises(SenecaServerError):
            client.speech_to_text(audio_file)

    def test_uses_timeout(self, client, mock_session, tmp_path):
        audio_file = tmp_path / "a.wav"
        audio_file.write_bytes(b"data")

        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"text": ""}
        mock_session.post.return_value = resp

        client.speech_to_text(audio_file)

        _, kwargs = mock_session.post.call_args
        assert kwargs["timeout"] == 10.0


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Verify the custom exception classes form the expected hierarchy."""

    def test_all_inherit_from_seneca_api_error(self):
        assert issubclass(SenecaAuthenticationError, SenecaApiError)
        assert issubclass(SenecaBadRequestError, SenecaApiError)
        assert issubclass(SenecaServiceUnavailableError, SenecaApiError)
        assert issubclass(SenecaServerError, SenecaApiError)

    def test_seneca_api_error_is_exception(self):
        assert issubclass(SenecaApiError, Exception)

    def test_exception_attributes(self):
        err = SenecaApiError("msg", status_code=418, response_body={"k": "v"})
        assert str(err) == "msg"
        assert err.status_code == 418
        assert err.response_body == {"k": "v"}

    def test_default_optional_attributes(self):
        err = SenecaApiError("msg")
        assert err.status_code is None
        assert err.response_body is None


# ---------------------------------------------------------------------------
# Data-class models
# ---------------------------------------------------------------------------


class TestDataModels:
    def test_health_response_is_frozen(self):
        hr = HealthResponse(status="ok", model_status="loaded")
        with pytest.raises(AttributeError):
            hr.status = "bad"  # type: ignore[misc]

    def test_language_info_equality(self):
        a = LanguageInfo(code="en", name="english")
        b = LanguageInfo(code="en", name="english")
        assert a == b

    def test_transcription_result_is_frozen(self):
        tr = TranscriptionResult(text="hello")
        with pytest.raises(AttributeError):
            tr.text = "bye"  # type: ignore[misc]
