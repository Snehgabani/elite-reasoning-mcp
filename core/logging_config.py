"""
Structured logging configuration for the Elite Reasoning system.

Usage:
    from core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Tool called", extra={"tool": "set_goal", "user": "sneh"})
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured log output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "func": record.funcName,
            "msg": record.getMessage(),
        }

        # Include any extra fields
        for key in ('tool', 'user', 'action', 'duration_ms', 'error', 'gap_id'):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """
    Get a structured logger instance.
    
    Log level controlled by ELITE_LOG_LEVEL env var (default: INFO).
    Output goes to stderr (for MCP stdio transport compatibility)
    and optionally to a file via ELITE_LOG_FILE.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    level = os.environ.get("ELITE_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))

    # Stderr handler (structured JSON)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(StructuredFormatter())
    logger.addHandler(stderr_handler)

    # Optional file handler
    log_file = os.environ.get("ELITE_LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger
