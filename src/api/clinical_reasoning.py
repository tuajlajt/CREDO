"""
Clinical Reasoning API router.

Exposes the multi-agent clinical reasoning pipeline via HTTP.
The browser calls this from NewVisitLog.uploadAudioForAI() to get
full multi-agent form pre-population with chain-of-thought.

POST /clinical/visit/{patient_id}
  multipart: file (audio blob, optional), transcript (form str, optional)
  → ClinicalVisitResult JSON

Owner agent: code-architect
"""
from __future__ import annotations

import logging
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clinical", tags=["Clinical Reasoning"])


@router.post("/visit/{patient_id}")
async def clinical_visit(
    patient_id: str,
    file: Optional[UploadFile] = File(default=None),
    transcript: Optional[str] = Form(default=None),
) -> JSONResponse:
    """
    Run the multi-agent clinical reasoning pipeline for a visit.

    Accepts either:
    - An audio file (WebM/WAV) → MedASR transcription → multi-agent pipeline
    - A plain text transcript → multi-agent pipeline directly

    Returns ClinicalVisitResult JSON with pre-populated form fields and CoT log.

    Raises:
        400: Neither audio nor transcript provided.
        503: Model weights not found (MedGemma or MedASR not downloaded).
    """
    if file is None and not transcript:
        raise HTTPException(
            status_code=400,
            detail="Provide either an audio file (field: file) or a transcript (field: transcript).",
        )

    from src.pipelines.clinical_reasoning import run_clinical_reasoning

    audio_path: Optional[Path] = None
    tmp_path: Optional[Path] = None

    try:
        if file is not None:
            # Write upload to a temp file so MedASR can read it by path
            suffix = Path(file.filename or "audio.webm").suffix or ".webm"
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)

            audio_path = tmp_path
            logger.info(
                "Clinical visit: patient=%s, audio=%s (%d bytes)",
                patient_id,
                audio_path.name,
                len(content),
            )
        else:
            logger.info(
                "Clinical visit: patient=%s, transcript=%d chars",
                patient_id,
                len(transcript or ""),
            )

        result = run_clinical_reasoning(
            patient_id=patient_id,
            audio_path=audio_path,
            transcript=transcript,
        )
        return JSONResponse(content=asdict(result))

    except FileNotFoundError as exc:
        logger.error("Model weights or database not found: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Service unavailable: {exc}. "
                "Ensure model weights are downloaded and the database is seeded."
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception(
            "Clinical reasoning pipeline failed for patient %s", patient_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Clinical reasoning pipeline error: {exc}",
        )
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
