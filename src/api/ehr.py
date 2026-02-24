"""
EHR data API — read-only endpoints for the CREDO UI.

All data is served from the demo SQLite database.
Run scripts/seed_db.py first to generate the database.

Owner agent: code-architect
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import yaml
from pathlib import Path

from src.data.db import (
    create_visit as db_create_visit,
    get_gp_worklist,
    get_patient_background,
    get_patient_documents,
    get_patient_medications,
    get_patient_profile,
    get_patient_vitals,
    get_patient_visits,
    search_patients,
)

router = APIRouter(prefix="/ehr", tags=["EHR"])

# Demo clinician ID — loaded from configs/database.yaml (fallback: "CLN001")
def _load_demo_clinician() -> str:
    cfg_path = Path(__file__).parent.parent.parent / "configs" / "database.yaml"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return raw["ehr"]["demo_clinician_id"]
    except Exception:
        return "CLN001"

_DEMO_CLINICIAN = _load_demo_clinician()


def _db_missing() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Demo database not found. Run: python scripts/seed_db.py",
    )


@router.get("/worklist")
def worklist() -> List[dict]:
    """GP patient worklist — all patients seen by the demo clinician."""
    try:
        return get_gp_worklist(_DEMO_CLINICIAN)
    except FileNotFoundError:
        raise _db_missing()


# NOTE: /patients/search must be declared BEFORE /patients/{patient_id}/...
# so FastAPI does not treat "search" as a patient_id.
@router.get("/patients/search")
def patient_search(name: str = Query(..., min_length=1)) -> List[dict]:
    """Search patients by partial name (case-insensitive)."""
    try:
        return search_patients(name)
    except FileNotFoundError:
        raise _db_missing()


@router.get("/patients/{patient_id}/profile")
def patient_profile(patient_id: str) -> dict:
    """Patient header card: profile fields + allergies + conditions."""
    try:
        data = get_patient_profile(patient_id)
    except FileNotFoundError:
        raise _db_missing()
    if data is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id!r} not found")
    return data


@router.get("/patients/{patient_id}/visits")
def patient_visits(patient_id: str) -> List[dict]:
    """Visit history with nested diagnoses and prescriptions, newest first."""
    try:
        return get_patient_visits(patient_id)
    except FileNotFoundError:
        raise _db_missing()


@router.get("/patients/{patient_id}/medications")
def patient_medications(patient_id: str) -> List[dict]:
    """Full prescription history, newest first."""
    try:
        return get_patient_medications(patient_id)
    except FileNotFoundError:
        raise _db_missing()


@router.get("/patients/{patient_id}/documents")
def patient_documents(patient_id: str) -> List[dict]:
    """Unified list of documents, lab results, and imaging studies."""
    try:
        return get_patient_documents(patient_id)
    except FileNotFoundError:
        raise _db_missing()


@router.get("/patients/{patient_id}/vitals")
def patient_vitals(patient_id: str) -> dict:
    """Weight/BP/heart-rate/SpO2 history for the vitals tab."""
    try:
        return get_patient_vitals(patient_id)
    except FileNotFoundError:
        raise _db_missing()


@router.get("/patients/{patient_id}/background")
def patient_background(patient_id: str) -> dict:
    """Lifestyle and family history for the Patient Background tab."""
    try:
        data = get_patient_background(patient_id)
    except FileNotFoundError:
        raise _db_missing()
    if data is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id!r} not found")
    return data


# ── Visit write models ─────────────────────────────────────────────────────────

class DiagnosisIn(BaseModel):
    code: str = ""
    display: str
    code_system: str = "ICD-10"
    status: str = "provisional"


class PrescriptionIn(BaseModel):
    medicine_name: str
    inn: str = ""
    dose: str = ""
    frequency: str = "as_needed"
    route: str = "oral"
    therapy_type: str = "acute"


class VitalsIn(BaseModel):
    weight_kg: Optional[float] = None
    systolic_mmhg: Optional[int] = None
    diastolic_mmhg: Optional[int] = None
    heart_rate_bpm: Optional[int] = None
    spo2_pct: Optional[float] = None
    measured_at: Optional[str] = None


class OrderIn(BaseModel):
    category: str = "lab"            # lab | imaging | other
    test_display: str
    test_code: str = ""
    test_code_system: str = "LOINC"  # LOINC for labs, CPT for imaging
    status: str = "requested"


class VisitCreateRequest(BaseModel):
    patient_reported_reason: str
    clinician_notes: str = ""
    visit_type: str = "outpatient"
    diagnoses: List[DiagnosisIn] = []
    prescriptions: List[PrescriptionIn] = []
    vitals: Optional[VitalsIn] = None
    orders: List[OrderIn] = []


@router.post("/patients/{patient_id}/visits")
def visit_create(patient_id: str, body: VisitCreateRequest) -> dict:
    """
    Create a new visit with diagnoses, prescriptions, and optional vitals.

    Returns the new visit_id on success.
    """
    try:
        visit_id = db_create_visit(
            patient_id=patient_id,
            patient_reported_reason=body.patient_reported_reason,
            clinician_notes=body.clinician_notes,
            diagnoses=[d.model_dump() for d in body.diagnoses],
            prescriptions=[p.model_dump() for p in body.prescriptions],
            vitals=body.vitals.model_dump() if body.vitals else None,
            orders=[o.model_dump() for o in body.orders],
            visit_type=body.visit_type,
        )
    except FileNotFoundError:
        raise _db_missing()
    return {"visit_id": visit_id, "status": "created"}
