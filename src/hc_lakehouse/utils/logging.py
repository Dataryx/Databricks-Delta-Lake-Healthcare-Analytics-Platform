"""Structured logging for pipeline tasks.

Uses stdlib ``logging`` only (never bare ``print``). JSON format is default for
machine-parseable ops logs; text format is available for local debugging.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)
        # Allow structured keys passed via LoggerAdapter / extra=
        skip = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
            "extra_fields",
        }
        for key, value in record.__dict__.items():
            if key not in skip and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class StructuredAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that merges structured fields into the record."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        extra = dict(self.extra or {})
        user_extra = kwargs.pop("extra", {}) or {}
        extra.update(user_extra)
        kwargs["extra"] = extra
        return msg, kwargs


_CONFIGURED = False


def setup_logging(
    level: str | None = None,
    fmt: str | None = None,
    *,
    force: bool = False,
) -> None:
    """Configure root logging once for the process.

    Parameters
    ----------
    level:
        Log level name (DEBUG, INFO, ...). Defaults to ``HC_LOG_LEVEL`` or INFO.
    fmt:
        ``json`` or ``text``. Defaults to ``HC_LOG_FORMAT`` or json.
    force:
        Reconfigure even if already set (used in tests).
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    level_name = (level or os.environ.get("HC_LOG_LEVEL", "INFO")).upper()
    format_name = (fmt or os.environ.get("HC_LOG_FORMAT", "json")).lower()

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level_name, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    if format_name == "text":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str, **default_fields: Any) -> StructuredAdapter:
    """Return a structured logger for ``name``."""
    if not _CONFIGURED:
        setup_logging()
    return StructuredAdapter(logging.getLogger(name), default_fields)
