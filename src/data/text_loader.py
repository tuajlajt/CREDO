"""
Clinical text loading and basic de-identification.

WARNING: The regex-based de-identification here is NOT sufficient for production
without validation against a clinical NLP de-identification tool.
For production: use philter-ucsf or Microsoft Presidio.

Owner agent: medical-data-engineer
"""
from __future__ import annotations

import re

# Patterns to detect and redact in clinical text (non-exhaustive)
PHI_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",                                             # SSN
    r"\bMRN\s*:?\s*\d+\b",                                                # MRN
    r"\b(0[1-9]|1[012])[-/](0[1-9]|[12][0-9]|3[01])[-/](19|20)\d{2}\b", # MM/DD/YYYY dates
    r"\b(19|20)\d{2}[-/](0[1-9]|1[012])[-/](0[1-9]|[12][0-9]|3[01])\b", # YYYY-MM-DD dates
    r"\b\d{10}\b",                                                         # 10-digit phone
    r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",                                   # Phone with separators
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",              # Email
]


def deidentify_text(text: str) -> str:
    """
    Basic pattern-based de-identification.
    For production: use philter-ucsf or Microsoft Presidio.
    Returns text with PHI patterns replaced by [REDACTED].
    """
    for pattern in PHI_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def load_clinical_note(path: str) -> str:
    """Load a plain text clinical note from file."""
    with open(path, encoding="utf-8") as f:
        return f.read()
