"""
FastAPI application entry point.

Mounts all API routers and exposes the ASGI app for uvicorn:
  uvicorn src.api.main:app --host 0.0.0.0 --port 8000

Or via root main.py:
  python main.py

Owner agent: docker-engineer, code-architect
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.clinical_reasoning import router as clinical_router
from src.api.ehr import router as ehr_router
from src.api.health import router as health_router
from src.api.radiology import router as radiology_router
from src.api.transcription import router as transcription_router
from src.api.drugs import router as drugs_router

app = FastAPI(
    title="MedGemma Medical AI API",
    version="0.1.0",
    description="Clinical decision support API using Google HAI-DEF models.",
)

app.include_router(clinical_router)
app.include_router(ehr_router)
app.include_router(health_router)
app.include_router(radiology_router, prefix="/radiology", tags=["Radiology"])
app.include_router(transcription_router)
app.include_router(drugs_router, prefix="/drug-check", tags=["Drug Interaction"])

# ── Serve static UI files ──────────────────────────────────────────────────────
_static_dir = Path(__file__).parent.parent / "ui" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve the transcription UI at root."""
    index = _static_dir / "transcription.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "MedGemma API running. See /docs for endpoints."}
