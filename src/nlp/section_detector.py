"""
Clinical note section detection.

Detects SOAP, radiology, and discharge summary sections from clinical text transcripts.
Used by medical-transcriber-agent pipeline.

Owner agent: medical-transcriber-agent
"""
from __future__ import annotations

import re

SOAP_PATTERNS = {
    "subjective": [
        r"(?i)(patient\s+(reports|states|complains|presents\s+with)|chief\s+complaint|history\s+of\s+present\s+illness|HPI)",
        r"(?i)(subjective[:\s])",
    ],
    "objective": [
        r"(?i)(vital\s+signs|blood\s+pressure|temperature|heart\s+rate|physical\s+exam|on\s+examination)",
        r"(?i)(objective[:\s]|lab\s+results|imaging)",
    ],
    "assessment": [
        r"(?i)(assessment[:\s]|impression[:\s]|diagnosis[:\s]|differential)",
    ],
    "plan": [
        r"(?i)(plan[:\s]|will\s+(prescribe|order|follow\s+up|refer)|medications|follow-up)",
    ],
}

RADIOLOGY_PATTERNS = {
    "technique":  [r"(?i)(technique[:\s]|protocol[:\s]|performed\s+with|using)"],
    "findings":   [r"(?i)(findings[:\s]|the\s+(lungs|heart|liver|kidney)|demonstrates|reveals)"],
    "impression": [r"(?i)(impression[:\s]|conclusion[:\s]|in\s+summary)"],
}

DISCHARGE_PATTERNS = {
    "admission_diagnosis": [r"(?i)(admission\s+diagnosis|reason\s+for\s+(admission|hospital))"],
    "hospital_course":     [r"(?i)(hospital\s+course|course\s+of\s+admission)"],
    "discharge_diagnosis": [r"(?i)(discharge\s+diagnosis|final\s+diagnosis)"],
    "discharge_plan":      [r"(?i)(discharge\s+(plan|instructions|medications)|follow-up)"],
}


def structure_as_soap(transcript: str) -> dict:
    """
    Detect and extract SOAP note sections from a clinical transcript.
    Returns dict with keys: subjective, objective, assessment, plan.
    """
    return _detect_section_boundaries(transcript, SOAP_PATTERNS)


def structure_as_radiology_report(transcript: str) -> dict:
    """
    Detect and extract radiology report sections from a transcript.
    Returns dict with keys: technique, findings, impression.
    """
    return _detect_section_boundaries(transcript, RADIOLOGY_PATTERNS)


def structure_as_discharge_summary(transcript: str) -> dict:
    """
    Detect and extract discharge summary sections from a transcript.
    Returns dict with keys: admission_diagnosis, hospital_course,
    discharge_diagnosis, discharge_plan.
    """
    return _detect_section_boundaries(transcript, DISCHARGE_PATTERNS)


def _detect_section_boundaries(
    text: str,
    patterns: dict[str, list[str]],
) -> dict[str, str]:
    """
    Internal: find section boundaries using keyword patterns.
    Returns dict mapping section names to extracted text.
    """
    section_starts: list[tuple[int, str]] = []

    for section_name, section_patterns in patterns.items():
        for pattern in section_patterns:
            for match in re.finditer(pattern, text):
                section_starts.append((match.start(), section_name))

    if not section_starts:
        # No sections found — return full text as first section
        first_key = next(iter(patterns))
        return {k: "" for k in patterns} | {first_key: text}

    section_starts.sort(key=lambda x: x[0])

    result = {k: "" for k in patterns}
    for i, (start_pos, section_name) in enumerate(section_starts):
        end_pos = section_starts[i + 1][0] if i + 1 < len(section_starts) else len(text)
        result[section_name] = text[start_pos:end_pos].strip()

    return result
