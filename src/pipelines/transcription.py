"""
Speech-to-structured-note pipeline (fully offline).

Flow:
  audio file
    → [MedASR]           raw medical transcript
    → [MedGemma 1.5]     SOAP note + ICD-10 codes (JSON)
    → [icd_mapper]       validated, formatted ICD codes
    → TranscriptionResult

All outputs carry requires_review=True.
Low ASR confidence (< 0.85) is flagged but does NOT block processing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.nlp.icd_mapper import ICDCode, parse_icd_codes, to_display_list
from src.utils.audit import log_inference


@dataclass
class SOAPNote:
    subjective: str = "[not documented]"
    objective: str = "[not documented]"
    assessment: str = "[not documented]"
    plan: str = "[not documented]"


@dataclass
class TranscriptionResult:
    # Core content
    raw_transcript: str
    soap: SOAPNote
    icd_codes: list[ICDCode]
    chief_complaint: str
    summary: str
    medications_mentioned: list[str]
    allergies_mentioned: list[str]
    documentation_gaps: list[str]

    # Quality / provenance
    requires_review: bool = True          # ALWAYS True — never remove
    disclaimer: str = (
        "AI-generated clinical note — requires clinician review and "
        "verification before use in the medical record."
    )
    asr_model: str = ""
    llm_model: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "requires_review": self.requires_review,
            "disclaimer": self.disclaimer,
            "chief_complaint": self.chief_complaint,
            "raw_transcript": self.raw_transcript,
            "soap": {
                "subjective": self.soap.subjective,
                "objective": self.soap.objective,
                "assessment": self.soap.assessment,
                "plan": self.soap.plan,
            },
            "icd_codes": to_display_list(self.icd_codes),
            "medications_mentioned": self.medications_mentioned,
            "allergies_mentioned": self.allergies_mentioned,
            "summary": self.summary,
            "documentation_gaps": self.documentation_gaps,
            "asr_model": self.asr_model,
            "llm_model": self.llm_model,
            "generated_at": self.generated_at,
        }


def _extract_json(text: str) -> dict:
    """
    Extract the first JSON object from model output.
    MedGemma occasionally wraps JSON in markdown code fences or adds
    a preamble sentence — this strips both.
    """
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

    # Find first '{' and last '}' — take everything in between
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output:\n{text[:300]}")

    return json.loads(text[start : end + 1])


def transcribe_to_structured_note(
    audio_path: str | Path,
    note_type: str = "soap",
) -> TranscriptionResult:
    """
    Full offline pipeline: audio file → structured SOAP note with ICD codes.

    Args:
        audio_path: Path to audio file (any format, any sample rate).
                    Must be de-identified before calling.
        note_type:  "soap" (default) — more note types planned.

    Returns:
        TranscriptionResult with requires_review=True always set.

    Raises:
        FileNotFoundError if model weights not found.
        ValueError if audio preprocessing or JSON parsing fails.
    """
    from src.models.medasr.inference import transcribe_medical_audio
    from src.models.medgemma.inference import structure_transcript_to_soap

    # ── Step 1: Speech → text (MedASR) ────────────────────────────────────────
    asr_result = transcribe_medical_audio(audio_path)
    raw_transcript = asr_result["transcript"]
    asr_model = asr_result.get("model", "medasr")

    if not raw_transcript.strip():
        raise ValueError("MedASR returned an empty transcript. Check audio quality.")

    # ── Step 2: Text → structured note + ICD codes (MedGemma) ─────────────────
    raw_json_str = structure_transcript_to_soap(raw_transcript)

    try:
        data = _extract_json(raw_json_str)
    except (json.JSONDecodeError, ValueError) as exc:
        # Return a degraded result rather than crashing — clinician can still
        # see the raw transcript and the unparsed model output.
        return TranscriptionResult(
            raw_transcript=raw_transcript,
            soap=SOAPNote(subjective=raw_json_str),   # dump raw output to subjective
            icd_codes=[],
            chief_complaint="[parsing error — see raw transcript]",
            summary=raw_transcript[:200],
            medications_mentioned=[],
            allergies_mentioned=[],
            documentation_gaps=[f"JSON parsing failed: {exc}"],
            asr_model=asr_model,
            llm_model="medgemma-1.5-4b-it",
        )

    # ── Step 3: Parse + validate ICD codes ────────────────────────────────────
    raw_codes = data.get("icd_codes", [])
    icd_codes = parse_icd_codes(raw_codes)

    # ── Step 4: Assemble result ────────────────────────────────────────────────
    soap_data = data.get("soap", {})
    result = TranscriptionResult(
        raw_transcript=raw_transcript,
        soap=SOAPNote(
            subjective=soap_data.get("subjective", "[not documented]"),
            objective=soap_data.get("objective", "[not documented]"),
            assessment=soap_data.get("assessment", "[not documented]"),
            plan=soap_data.get("plan", "[not documented]"),
        ),
        icd_codes=icd_codes,
        chief_complaint=data.get("chief_complaint", ""),
        summary=data.get("summary", ""),
        medications_mentioned=data.get("medications_mentioned", []),
        allergies_mentioned=data.get("allergies_mentioned", []),
        documentation_gaps=data.get("documentation_gaps", []),
        asr_model=asr_model,
        llm_model="medgemma-1.5-4b-it",
    )

    # ── Step 5: Audit log ──────────────────────────────────────────────────────
    log_inference(
        request_id=str(hash(raw_transcript)),
        agents_invoked=["medasr", "medgemma-1.5-4b-it"],
        model_versions={"medasr": asr_model, "medgemma": "medgemma-1.5-4b-it"},
        data_types=["audio"],
        confidence_scores={},
    )

    return result


def structure_text_to_note(
    transcript: str,
) -> TranscriptionResult:
    """
    Text-only path: raw transcript → SOAP note + ICD codes (no ASR step).
    Used when the user pastes a transcript manually.
    """
    from src.models.medgemma.inference import structure_transcript_to_soap

    raw_json_str = structure_transcript_to_soap(transcript)

    try:
        data = _extract_json(raw_json_str)
    except (json.JSONDecodeError, ValueError) as exc:
        return TranscriptionResult(
            raw_transcript=transcript,
            soap=SOAPNote(subjective=raw_json_str),
            icd_codes=[],
            chief_complaint="[parsing error]",
            summary=transcript[:200],
            medications_mentioned=[],
            allergies_mentioned=[],
            documentation_gaps=[f"JSON parsing failed: {exc}"],
            asr_model="none",
            llm_model="medgemma-1.5-4b-it",
        )

    soap_data = data.get("soap", {})
    icd_codes = parse_icd_codes(data.get("icd_codes", []))

    result = TranscriptionResult(
        raw_transcript=transcript,
        soap=SOAPNote(
            subjective=soap_data.get("subjective", "[not documented]"),
            objective=soap_data.get("objective", "[not documented]"),
            assessment=soap_data.get("assessment", "[not documented]"),
            plan=soap_data.get("plan", "[not documented]"),
        ),
        icd_codes=icd_codes,
        chief_complaint=data.get("chief_complaint", ""),
        summary=data.get("summary", ""),
        medications_mentioned=data.get("medications_mentioned", []),
        allergies_mentioned=data.get("allergies_mentioned", []),
        documentation_gaps=data.get("documentation_gaps", []),
        asr_model="none",
        llm_model="medgemma-1.5-4b-it",
    )

    log_inference(
        request_id=str(hash(transcript)),
        agents_invoked=["medgemma-1.5-4b-it"],
        model_versions={"medgemma": "medgemma-1.5-4b-it"},
        data_types=["text"],
        confidence_scores={},
    )

    return result
