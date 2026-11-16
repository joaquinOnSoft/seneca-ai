"""
tests/unit/test_config.py – Secrets loaded from files (Docker secrets).
"""

import pytest

from seneca.utils.config import AppConfig


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("JWT_SECRET_KEY", "JWT_SECRET_KEY_FILE", "SENECA_AI_API_KEY", "SENECA_AI_API_KEY_FILE",
                 "MONGODB_USERNAME", "MONGODB_PASSWORD", "MONGO_ROOT_USERNAME_FILE", "MONGO_ROOT_PASSWORD_FILE"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _secret(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(value + "\n")
    return str(path)


def test_jwt_secret_is_required(clean_env):
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        AppConfig()


def test_jwt_secret_from_file(clean_env, tmp_path):
    clean_env.setenv("JWT_SECRET_KEY_FILE", _secret(tmp_path, "jwt", "from-file"))
    assert AppConfig().jwt_secret_key == "from-file"


def test_secret_file_takes_precedence_over_variable(clean_env, tmp_path):
    clean_env.setenv("JWT_SECRET_KEY", "from-env")
    clean_env.setenv("JWT_SECRET_KEY_FILE", _secret(tmp_path, "jwt", "from-file"))
    assert AppConfig().jwt_secret_key == "from-file"


def test_missing_secret_file_falls_back_to_variable(clean_env, tmp_path):
    clean_env.setenv("JWT_SECRET_KEY", "from-env")
    clean_env.setenv("JWT_SECRET_KEY_FILE", str(tmp_path / "does-not-exist"))
    assert AppConfig().jwt_secret_key == "from-env"


def test_api_key_and_mongo_credentials_from_files(clean_env, tmp_path):
    clean_env.setenv("JWT_SECRET_KEY", "x")
    clean_env.setenv("SENECA_AI_API_KEY_FILE", _secret(tmp_path, "key", "api-key"))
    clean_env.setenv("MONGO_ROOT_USERNAME_FILE", _secret(tmp_path, "user", "root"))
    clean_env.setenv("MONGO_ROOT_PASSWORD_FILE", _secret(tmp_path, "pass", "s3cr3t"))
    cfg = AppConfig()
    assert cfg.seneca_ai_api_key == "api-key"
    assert (cfg.mongodb_username, cfg.mongodb_password) == ("root", "s3cr3t")


def test_mongo_credentials_default_to_empty(clean_env):
    clean_env.setenv("JWT_SECRET_KEY", "x")
    cfg = AppConfig()
    assert (cfg.mongodb_username, cfg.mongodb_password) == ("", "")
