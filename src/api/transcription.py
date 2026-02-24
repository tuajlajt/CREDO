"""
Medical transcription API endpoints.

POST /transcribe/audio   — upload audio → SOAP note + ICD codes
POST /transcribe/text    — paste transcript → SOAP note + ICD codes
GET  /transcribe/health  — confirm models are loaded and responding
"""
from __future__ import annotations

import tempfile
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/transcribe", tags=["transcription"])

_ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


def _assert_audio_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio format '{ext}'. "
                   f"Accepted: {sorted(_ALLOWED_AUDIO_EXTENSIONS)}",
        )


@router.post("/audio")
async def transcribe_audio(
    file: UploadFile = File(..., description="De-identified clinical audio file"),
    note_type: str = Form("soap", description="soap | free"),
) -> JSONResponse:
    """
    Upload a de-identified clinical audio file.
    Returns a structured SOAP note with ICD-10 code suggestions.

    All outputs carry requires_review=True.
    """
    _assert_audio_extension(file.filename or "audio.wav")

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 100 MB limit.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    # Write to temp file so librosa / MedASR can open it by path
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from src.pipelines.transcription import transcribe_to_structured_note
        result = transcribe_to_structured_note(tmp_path, note_type=note_type)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return JSONResponse(content=result.to_dict())


@router.post("/text")
async def structure_transcript(
    transcript: str = Form(..., description="Raw clinical text (already de-identified)"),
    note_type: str = Form("soap", description="soap | free"),
) -> JSONResponse:
    """
    Paste a raw clinical transcript. Returns a structured SOAP note
    with ICD-10 code suggestions (no ASR step).
    """
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")
    if len(transcript) > 50_000:
        raise HTTPException(status_code=413, detail="Transcript exceeds 50,000 characters.")

    try:
        from src.pipelines.transcription import structure_text_to_note
        result = structure_text_to_note(transcript)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return JSONResponse(content=result.to_dict())


@router.get("/health")
async def transcription_health() -> dict:
    """
    Verify MedASR and MedGemma weights are accessible.
    Does NOT load the full models — just checks paths exist.
    """
    import os
    from pathlib import Path

    base = os.environ.get("MODEL_WEIGHTS_PATH", "./models")
    medasr_ok = Path(base, "google--medasr", "config.json").exists()
    medgemma_ok = Path(base, "google--medgemma-1.5-4b-it", "config.json").exists()

    return {
        "medasr_weights": "ok" if medasr_ok else "missing",
        "medgemma_weights": "ok" if medgemma_ok else "missing",
        "ready": medasr_ok and medgemma_ok,
    }
