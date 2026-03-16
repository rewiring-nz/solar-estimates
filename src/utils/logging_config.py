"""Logging configuration for the solar estimates pipeline.

This module provides structured logging with elapsed time since script start.
"""

import logging
import sys
import time

_start_time = time.time()


def _format_elapsed(total_seconds: int) -> str:
    """Format elapsed seconds as a human-readable string.

    Only non-zero larger units are shown; seconds are always shown.

    Examples:
        0  -> "0s"
        45 -> "45s"
        135 -> "2m 15s"
        5025 -> "1h 23m 45s"
        188130 -> "2d 4h 15m 30s"
    """
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


class ElapsedTimeFormatter(logging.Formatter):
    """Formatter that prefixes each log record with elapsed time since script start."""

    def format(self, record: logging.LogRecord) -> str:
        elapsed = int(record.created - _start_time)
        record.elapsed_str = _format_elapsed(elapsed)
        return super().format(record)


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Configure logging with elapsed time formatting.

    Args:
        log_level: Logging level (default: INFO).

    Returns:
        The configured root pipeline logger.
    """
    logger = logging.getLogger("solar_pipeline")
    logger.setLevel(log_level)
    logger.handlers.clear()

    formatter = ElapsedTimeFormatter("%(elapsed_str)s : %(levelname)s - %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance for a module.

    Args:
        name: Logger name, typically ``__name__``.

    Returns:
        A child logger under the ``solar_pipeline`` hierarchy.
    """
    return logging.getLogger("solar_pipeline" + ("." + name if name else ""))
