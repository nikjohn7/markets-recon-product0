"""Centralized logging configuration with redaction utilities."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

from .settings import Settings, get_settings

REDACTED = "[REDACTED]"
TRUNCATED_TEMPLATE = "[TRUNCATED payload length={length}]"
MAX_MESSAGE_LENGTH = 500
SENSITIVE_KEYWORDS = {"api_key", "authorization", "prompt", "document_text", "secret"}


def _collect_secrets(settings: Settings) -> Mapping[str, str]:
    return {
        "anthropic_api_key": settings.anthropic_api_key.get_secret_value(),
        "openai_api_key": settings.openai_api_key.get_secret_value(),
        "database_url": settings.database_url,
    }


def _sanitize_string(value: str, secrets: Mapping[str, str]) -> str:
    redacted = value
    for secret in secrets.values():
        if secret and secret in redacted:
            redacted = redacted.replace(secret, REDACTED)

    lowercase = redacted.lower()
    if any(keyword in lowercase for keyword in SENSITIVE_KEYWORDS):
        return REDACTED

    if len(redacted) > MAX_MESSAGE_LENGTH:
        return TRUNCATED_TEMPLATE.format(length=len(redacted))

    return redacted


def sanitize_message(message: Any, secrets: Mapping[str, str]) -> str:
    """Return a sanitized log message with secrets redacted and long payloads truncated."""

    if not isinstance(message, str):
        message = str(message)

    return _sanitize_string(message, secrets)


class ConsoleFormatter(logging.Formatter):
    """Formatter for human-readable console logs with redaction."""

    def __init__(self, secrets: Mapping[str, str]):
        super().__init__(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.secrets = secrets

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - overrides base method
        message = sanitize_message(record.getMessage(), self.secrets)
        timestamp = self.formatTime(record, self.datefmt)
        return f"{timestamp} | {record.levelname} | {record.name} | {message}"


class JsonFormatter(logging.Formatter):
    """Formatter that emits JSON log lines with redaction."""

    def __init__(self, secrets: Mapping[str, str]):
        super().__init__()
        self.secrets = secrets

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - overrides base method
        message = sanitize_message(record.getMessage(), self.secrets)
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": message,
        }
        return json.dumps(log_record, ensure_ascii=False)


def configure_logging(settings: Settings | None = None, stream: Any | None = None) -> None:
    """Configure application logging with sensible defaults and redaction."""

    active_settings = settings or get_settings()
    secrets = _collect_secrets(active_settings)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(active_settings.log_level)

    handler = logging.StreamHandler(stream=stream or sys.stderr)
    if active_settings.log_json_format:
        formatter = JsonFormatter(secrets)
    else:
        formatter = ConsoleFormatter(secrets)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    logging.captureWarnings(True)

