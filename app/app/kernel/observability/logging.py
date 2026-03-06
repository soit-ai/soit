""" logging

Structured logging setup.
"""

import json
import logging
import sys
from typing import Any, Dict, Iterable, Tuple

from app.kernel.observability.context import get_log_context
from app.settings.settings import settings


_CONTEXT_FIELDS: Tuple[str, ...] = (
    "request_id",
    "trace_id",
    "tenant_id",
    "workspace_id",
    "user_id",
    "run_id",
    "step_id",
)

_RESERVED_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


def _merge_context(record: logging.LogRecord) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for field in _CONTEXT_FIELDS:
        if hasattr(record, field):
            value = getattr(record, field)
            if value is not None:
                data[field] = value
    context_fields = get_log_context()
    for key, value in context_fields.items():
        if value is not None and key not in data:
            data[key] = value
    for key, value in record.__dict__.items():
        if key in _RESERVED_FIELDS or key in data:
            continue
        data[key] = value
    return data


def _format_kv(items: Iterable[Tuple[str, Any]]) -> str:
    data = [(key, value) for key, value in items if value is not None]
    priority = ("http_method", "path", "status_code")
    ordered: list[tuple[str, Any]] = []
    for key in priority:
        for item_key, item_value in data:
            if item_key == key:
                ordered.append((item_key, item_value))
                break
    for item in data:
        if item[0] not in priority:
            ordered.append(item)
    rendered: list[str] = []
    for key, value in ordered:
        if key == "http_method":
            rendered.append(f"{key}={str(value):<4}")
        else:
            rendered.append(f"{key}={value}")
    return " ".join(rendered)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record.

        Returns:
            JSON string.
        """
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        log_data.update(_merge_context(record))

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable formatter with optional ANSI colors."""

    _LEVEL_COLORS = {
        "DEBUG": "\x1b[38;5;246m",
        "INFO": "\x1b[32m",
        "WARNING": "\x1b[33m",
        "ERROR": "\x1b[31m",
        "CRITICAL": "\x1b[35m",
    }
    _RESET = "\x1b[0m"

    def __init__(self, *, use_color: bool, datefmt: str | None = None) -> None:
        super().__init__(datefmt=datefmt)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        timestamp = f"{self.formatTime(record, self.datefmt)}.{int(record.msecs):03d}"
        level = record.levelname
        if self._use_color and level in self._LEVEL_COLORS:
            level = f"{self._LEVEL_COLORS[level]}{level}{self._RESET}"
        message = record.getMessage()
        context = _merge_context(record)
        extra = _format_kv(context.items())
        base = f"{timestamp} | {level} | {record.name} | {message}"
        if extra:
            base = f"{base} | {extra}"
        if record.exc_info:
            return f"{base}\n{self.formatException(record.exc_info)}"
        return base


class RichMessageFormatter(logging.Formatter):
    """Formatter for RichHandler message column."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        context = _merge_context(record)
        extra = _format_kv(context.items())
        if extra:
            message = f"{message} | {extra}"
        return message


def _build_formatter() -> logging.Formatter:
    datefmt = "%Y-%m-%d %H:%M:%S"
    if settings.log_format.lower() == "json":
        return JSONFormatter(datefmt=datefmt)
    use_color = bool(settings.log_color and (sys.stdout.isatty() or settings.log_color_force))
    return TextFormatter(use_color=use_color, datefmt=datefmt)


def _build_handler() -> logging.Handler:
    fmt = settings.log_format.lower()
    if fmt == "rich":
        try:
            from rich.logging import RichHandler  # type: ignore
            from rich.console import Console  # type: ignore
        except Exception:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(_build_formatter())
            return handler
        force_color = bool(settings.log_color and (sys.stdout.isatty() or settings.log_color_force))
        console = Console(
            force_terminal=force_color,
            color_system="auto",
            stderr=False,
        )
        handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_level=True,
            show_path=False,
            log_time_format="%Y-%m-%d %H:%M:%S",
            console=console,
        )
        handler.setFormatter(RichMessageFormatter())
        return handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_build_formatter())
    return handler


def _configure_uvicorn_logging() -> None:
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True


def setup_logging() -> None:
    """Setup structured logging."""
    handler = _build_handler()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)
    root_logger.addHandler(handler)
    _configure_uvicorn_logging()


# Setup on import
setup_logging()
