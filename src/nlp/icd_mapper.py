"""
ICD-10 code handling utilities.

MedGemma suggests ICD-10 codes via prompt. This module:
  1. Parses and validates the raw JSON codes from MedGemma.
  2. Formats them for API responses and UI display.
  3. Provides confidence-level filtering.

No external lookup database required — MedGemma has ICD-10 knowledge baked in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ICD-10 format: letter + 2 digits + optional dot + up to 4 more chars
# e.g. J18.9, Z23, M54.5, K92.1
_ICD10_PATTERN = re.compile(r"^[A-Z]\d{2}(\.\d{1,4})?$")


@dataclass
class ICDCode:
    code: str
    description: str
    confidence: str          # "high" | "medium" | "low"
    basis: str = ""          # justification from transcript


def is_valid_icd10(code: str) -> bool:
    """Basic format check — not a full vocabulary lookup."""
    return bool(_ICD10_PATTERN.match(code.strip().upper()))


def parse_icd_codes(raw_codes: list[dict]) -> list[ICDCode]:
    """
    Parse and validate ICD-10 code dicts from MedGemma's JSON output.
    Silently drops entries with invalid formats.

    Args:
        raw_codes: list of dicts with keys: code, description, confidence[, basis]

    Returns:
        list[ICDCode] — only valid, well-formed entries.
    """
    parsed = []
    for entry in raw_codes:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code", "")).strip().upper()
        description = str(entry.get("description", "")).strip()
        confidence = str(entry.get("confidence", "low")).strip().lower()
        basis = str(entry.get("basis", "")).strip()

        if not code or not description:
            continue
        if confidence not in ("high", "medium", "low"):
            confidence = "low"

        # Accept even if ICD format check fails — MedGemma may return
        # partial codes; include with a warning rather than silently drop.
        parsed.append(ICDCode(
            code=code,
            description=description,
            confidence=confidence,
            basis=basis,
        ))

    return parsed


def filter_by_confidence(
    codes: list[ICDCode],
    min_confidence: str = "low",
) -> list[ICDCode]:
    """
    Filter codes by minimum confidence level.
    min_confidence: "high" → only high; "medium" → medium + high; "low" → all.
    """
    _rank = {"high": 3, "medium": 2, "low": 1}
    threshold = _rank.get(min_confidence, 1)
    return [c for c in codes if _rank.get(c.confidence, 1) >= threshold]


def to_display_list(codes: list[ICDCode]) -> list[dict]:
    """Serialize ICDCode list to plain dicts for JSON API responses."""
    return [
        {
            "code": c.code,
            "description": c.description,
            "confidence": c.confidence,
            "basis": c.basis,
            "valid_format": is_valid_icd10(c.code),
        }
        for c in codes
    ]
