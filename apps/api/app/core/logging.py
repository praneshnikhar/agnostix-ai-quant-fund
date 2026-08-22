"""Structured JSON logging via structlog.

Security rule: never log API keys, tokens, passwords, or credentials.
A redaction processor strips any key matching sensitive patterns.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_SENSITIVE_KEY_PATTERNS = (
    "api_key",
    "secret",
    "password",
    "token",
    "credential",
    "authorization",
)


def _redact_sensitive(
    _logger: Any, _name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Redact values whose keys look sensitive (defense in depth)."""
    for key in list(event_dict.keys()):
        if any(pattern in str(key).lower() for pattern in _SENSITIVE_KEY_PATTERNS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog + stdlib logging for the whole process."""
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_sensitive,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
