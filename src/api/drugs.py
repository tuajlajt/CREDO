"""
Drug interaction check API endpoints.

POST /drug-check/        — check a medication list for drug-drug interactions
POST /drug-check/full    — full pipeline with PubMed RAG + side effects + symptom matching
GET  /drug-check/health  — endpoint availability check

All responses include requires_review=True.
Critical interactions are surfaced at the top of the response.

Owner agent: pharmacology-agent
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)


class DrugCheckRequest(BaseModel):
    drug_names: List[str] = Field(
        description="Drug names as prescribed — trade or generic names accepted",
        min_length=1,
    )
    patient_symptoms: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional list of patient-reported symptoms from the transcript. "
            "Used for symptom-medication correlation analysis."
        ),
    )
    enable_pubmed_rag: bool = Field(
        default=False,
        description=(
            "If True, run PubMed literature search for each drug pair. "
            "Adds latency (~2–5 seconds per pair). Disabled by default."
        ),
    )
    enable_side_effects: bool = Field(
        default=True,
        description="If True, retrieve side effects from openFDA drug labels.",
    )


@router.post("/")
async def check_drug_interactions(request: DrugCheckRequest) -> dict:
    """
    Check a medication list for drug-drug interactions.

    Performs:
    1. Drug name → INN resolution via RxNorm
    2. Batch DDI check via RxNav
    3. Optional PubMed RAG evidence retrieval
    4. Optional openFDA side effects + symptom matching

    Returns a structured report with severity-graded interactions,
    symptom-medication correlations, and clinical recommendations.
    All outputs have requires_review=True.
    """
    from src.pipelines.drug_check_pipeline import run_drug_check_pipeline

    if not request.drug_names:
        raise HTTPException(status_code=400, detail="drug_names must not be empty")

    # Run in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        lambda: run_drug_check_pipeline(
            drug_names=request.drug_names,
            patient_symptoms=request.patient_symptoms,
            enable_pubmed_rag=request.enable_pubmed_rag,
            enable_side_effects=request.enable_side_effects,
        ),
    )
    return result


@router.get("/health")
async def drug_check_health() -> dict:
    """Check that the drug interaction endpoint is available."""
    return {
        "status": "ok",
        "sources": ["NIH RxNav/RxNorm", "openFDA", "PubMed (optional)"],
        "requires_review": True,
    }
