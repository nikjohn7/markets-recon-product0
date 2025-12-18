from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Settings


def build_env_file(tmp_path: Path, **values: str) -> Path:
    content = "\n".join(f"{key}={val}" for key, val in values.items())
    env_file = tmp_path / "test.env"
    env_file.write_text(content)
    return env_file


def test_settings_load_from_env_file(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        DATABASE_URL="sqlite:///./data/test.db",
        BLOB_STORAGE_PATH="./data/pdfs",
        ANTHROPIC_API_KEY="ant-key",
        OPENAI_API_KEY="open-key",
        LOG_LEVEL="debug",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "sqlite:///./data/test.db"
    assert settings.blob_storage_path == Path("./data/pdfs")
    assert settings.anthropic_api_key.get_secret_value() == "ant-key"
    assert settings.openai_api_key.get_secret_value() == "open-key"
    assert settings.log_level == "DEBUG"


def test_missing_required_field_raises_error(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        DATABASE_URL="sqlite:///./data/test.db",
        BLOB_STORAGE_PATH="./data/pdfs",
        ANTHROPIC_API_KEY="ant-key",
        LOG_LEVEL="INFO",
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)


def test_invalid_log_level_is_rejected(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        DATABASE_URL="sqlite:///./data/test.db",
        BLOB_STORAGE_PATH="./data/pdfs",
        ANTHROPIC_API_KEY="ant-key",
        OPENAI_API_KEY="open-key",
        LOG_LEVEL="verbose",
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)
