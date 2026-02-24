"""
Logging configuration for the MedGemma application.

Sets up two loggers:
  "app"   — application logs (INFO and above)
  "audit" — HIPAA audit logs (all data access and inference events)

Audit logger writes to logs/audit.log (append-only).
Application logger writes to stdout and logs/app.log.

Owner agent: code-architect
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(
    log_dir: str = "logs",
    app_log_level: str = "INFO",
) -> None:
    """
    Configure application and audit loggers.
    Call once at application startup (main.py or src/api/main.py).
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Application logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(getattr(logging, app_log_level.upper(), logging.INFO))
    app_handler = logging.handlers.RotatingFileHandler(
        log_path / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    app_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    app_logger.addHandler(app_handler)
    app_logger.addHandler(logging.StreamHandler())

    # Audit logger — append-only, no rotation (HIPAA audit trail)
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    audit_handler = logging.FileHandler(log_path / "audit.log", mode="a")
    audit_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    audit_logger.addHandler(audit_handler)
    audit_logger.propagate = False  # Audit events do not go to root logger


def get_logger(name: str = "app") -> logging.Logger:
    """Get a named logger. Use 'audit' for HIPAA audit events."""
    return logging.getLogger(name)
