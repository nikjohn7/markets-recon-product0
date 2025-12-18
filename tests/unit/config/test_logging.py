import json
import logging
import traceback
from io import StringIO

from src.config import Settings
from src.config.logging import MAX_MESSAGE_LENGTH, configure_logging


def build_settings(**overrides: object) -> Settings:
    defaults = {
        "DATABASE_URL": "sqlite:///./data/test.db",
        "BLOB_STORAGE_PATH": "./data/pdfs",
        "ANTHROPIC_API_KEY": "ant-secret",
        "OPENAI_API_KEY": "open-secret",
        "LOG_LEVEL": "INFO",
        "LOG_JSON_FORMAT": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_console_logging_includes_metadata_and_redacts_secrets() -> None:
    stream = StringIO()
    settings = build_settings()

    configure_logging(settings=settings, stream=stream)
    logger = logging.getLogger("config.test.console")
    logger.warning("Using key %s", "ant-secret")

    log_line = stream.getvalue().strip().splitlines()[-1]
    assert "config.test.console" in log_line
    assert "WARNING" in log_line
    assert "[REDACTED]" in log_line
    assert "ant-secret" not in log_line


def test_json_logging_outputs_structured_line() -> None:
    stream = StringIO()
    settings = build_settings(LOG_JSON_FORMAT=True)

    configure_logging(settings=settings, stream=stream)
    logger = logging.getLogger("config.test.json")
    logger.info("hello world")

    log_line = stream.getvalue().strip()
    payload = json.loads(log_line)
    assert payload["level"] == "INFO"
    assert payload["module"] == "config.test.json"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_oversized_payloads_are_truncated() -> None:
    stream = StringIO()
    settings = build_settings()
    configure_logging(settings=settings, stream=stream)

    logger = logging.getLogger("config.test.truncate")
    logger.error("x" * (MAX_MESSAGE_LENGTH + 25))

    log_line = stream.getvalue().strip().splitlines()[-1]
    assert "TRUNCATED payload length" in log_line
    assert "x" * 10 not in log_line


def test_json_logging_includes_exception_tracebacks() -> None:
    stream = StringIO()
    settings = build_settings(LOG_JSON_FORMAT=True)

    configure_logging(settings=settings, stream=stream)
    logger = logging.getLogger("config.test.exception")
    
    # Log an exception with traceback
    try:
        raise ValueError("Test exception for traceback verification")
    except Exception:
        logger.exception("An error occurred with traceback")

    log_line = stream.getvalue().strip()
    payload = json.loads(log_line)
    
    # Verify basic log structure
    assert payload["level"] == "ERROR"
    assert payload["module"] == "config.test.exception"
    assert payload["message"] == "An error occurred with traceback"
    assert "timestamp" in payload
    
    # Verify exception information is included
    assert "exception" in payload
    exception_info = payload["exception"]
    assert exception_info["type"] == "ValueError"
    assert exception_info["message"] == "Test exception for traceback verification"
    assert "traceback" in exception_info
    assert isinstance(exception_info["traceback"], list)
    assert len(exception_info["traceback"]) > 0
    assert "ValueError: Test exception for traceback verification" in "".join(exception_info["traceback"])
