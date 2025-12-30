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
        ANTHROPIC_API_KEY="anthropic-key",
        MEGALLM_API_KEY="megallm-key",
        NEBIUS_API_KEY="nebius-key",
        DEEPINFRA_API_KEY="deepinfra-key",
        OPENAI_API_KEY="open-key",
        LOG_LEVEL="debug",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "sqlite:///./data/test.db"
    assert settings.blob_storage_path == Path("./data/pdfs")
    assert settings.anthropic_api_key.get_secret_value() == "anthropic-key"
    assert settings.megallm_api_key.get_secret_value() == "megallm-key"
    assert settings.nebius_api_key.get_secret_value() == "nebius-key"
    assert settings.deepinfra_api_key.get_secret_value() == "deepinfra-key"
    assert settings.openai_api_key.get_secret_value() == "open-key"
    assert settings.log_level == "DEBUG"


def test_defaults_apply_for_storage_and_logging(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        ANTHROPIC_API_KEY="anthropic-key",
        MEGALLM_API_KEY="megallm-key",
        NEBIUS_API_KEY="nebius-key",
        DEEPINFRA_API_KEY="deepinfra-key",
        OPENAI_API_KEY="open-key",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "sqlite:///./data/marketsrecon.db"
    assert settings.blob_storage_path == Path("./data/pdfs")
    assert settings.log_level == "INFO"


def test_deepinfra_embeddings_provider_allows_missing_openai_key(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        ANTHROPIC_API_KEY="anthropic-key",
        MEGALLM_API_KEY="megallm-key",
        NEBIUS_API_KEY="nebius-key",
        DEEPINFRA_API_KEY="deepinfra-key",
        EMBEDDINGS_PROVIDER="deepinfra",
    )

    settings = Settings(_env_file=env_file)

    assert settings.embeddings_provider == "deepinfra"
    assert settings.openai_api_key is None


def test_openai_embeddings_provider_requires_openai_key(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        ANTHROPIC_API_KEY="anthropic-key",
        MEGALLM_API_KEY="megallm-key",
        NEBIUS_API_KEY="nebius-key",
        DEEPINFRA_API_KEY="deepinfra-key",
        EMBEDDINGS_PROVIDER="openai",
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)


def test_missing_required_field_raises_error(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        DATABASE_URL="sqlite:///./data/test.db",
        BLOB_STORAGE_PATH="./data/pdfs",
        ANTHROPIC_API_KEY="anthropic-key",
        LOG_LEVEL="INFO",
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)


def test_invalid_log_level_is_rejected(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        DATABASE_URL="sqlite:///./data/test.db",
        BLOB_STORAGE_PATH="./data/pdfs",
        ANTHROPIC_API_KEY="anthropic-key",
        MEGALLM_API_KEY="megallm-key",
        NEBIUS_API_KEY="nebius-key",
        DEEPINFRA_API_KEY="deepinfra-key",
        OPENAI_API_KEY="open-key",
        LOG_LEVEL="verbose",
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)


def test_empty_blob_storage_path_is_rejected(tmp_path: Path) -> None:
    env_file = build_env_file(
        tmp_path,
        DATABASE_URL="sqlite:///./data/test.db",
        BLOB_STORAGE_PATH="",
        ANTHROPIC_API_KEY="anthropic-key",
        MEGALLM_API_KEY="megallm-key",
        NEBIUS_API_KEY="nebius-key",
        DEEPINFRA_API_KEY="deepinfra-key",
        OPENAI_API_KEY="open-key",
        LOG_LEVEL="INFO",
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)
