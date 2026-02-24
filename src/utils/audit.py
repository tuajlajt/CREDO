"""
HIPAA audit logging utilities.

Every data access and inference event must be logged here.
Audit log is append-only and must not be deleted or truncated.

Required audit events:
  - data_access: any time patient data (even de-identified) is accessed
  - inference:   any time a clinical AI model runs on patient data
  - emergency:   any time an emergency finding is generated
  - error:       any time a safety gate fails or data is rejected

Owner agent: code-architect, medical-data-engineer
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

_audit_logger = logging.getLogger("audit")


def _log(event: dict) -> None:
    """Write a JSON audit event to the audit log."""
    event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    _audit_logger.info(json.dumps(event))


def log_data_access(
    data_type: str,
    record_id: str,
    purpose: str,
    agent: str,
) -> None:
    """
    Log a data access event.

    Args:
        data_type: "dicom" | "fhir" | "audio" | "text"
        record_id: De-identified record ID only — never real MRN or patient name
        purpose:   Why this data is being accessed
        agent:     Which agent/module is accessing the data
    """
    _log({
        "event": "data_access",
        "data_type": data_type,
        "record_id": record_id,
        "purpose": purpose,
        "agent": agent,
    })


def log_inference(
    request_id: str,
    agents_invoked: list[str],
    model_versions: dict,
    data_types: list[str],
    confidence_scores: dict,
    emergency_flag: bool = False,
) -> None:
    """Log a clinical AI inference event."""
    _log({
        "event": "inference",
        "request_id": request_id,
        "agents_invoked": agents_invoked,
        "model_versions": model_versions,
        "data_types": data_types,
        "confidence_scores": confidence_scores,
        "emergency_flag": emergency_flag,
        "requires_review": True,
    })


def log_emergency(
    request_id: str,
    finding: str,
    agent: str,
) -> None:
    """Log an emergency clinical finding escalation."""
    _log({
        "event": "emergency_finding",
        "request_id": request_id,
        "finding": finding,
        "agent": agent,
    })


def log_safety_gate_failure(
    gate: str,
    reason: str,
    request_id: Optional[str] = None,
) -> None:
    """Log a safety gate failure (PHI detected, de-identification incomplete, etc.)."""
    _log({
        "event": "safety_gate_failure",
        "gate": gate,
        "reason": reason,
        "request_id": request_id,
    })
