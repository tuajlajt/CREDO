"""
Radiology API endpoints.

POST /radiology/analyze — analyze a medical image (CXR, CT, MRI)
GET  /radiology/report/{report_id} — retrieve a stored report

All responses include requires_review=True and a clinical disclaimer.
Emergency findings are flagged in the response for immediate escalation.

Owner agent: ui-designer-agent, radiologist-agent
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

router = APIRouter()


@router.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    modality: str = Form("CXR"),
) -> dict:
    """
    Analyze a medical image and return a structured radiology report.

    Args:
        file: DICOM file (de-identified by caller)
        modality: "CXR" | "CT" | "MRI"

    Returns:
        RadiologyReport dict with requires_review=True, critical_findings list,
        and standard clinical disclaimer.
    """
    # TODO: implement
    # 1. Save uploaded file
    # 2. Validate it's de-identified DICOM
    # 3. Run radiology_pipeline.run_radiology_pipeline()
    # 4. Return report + log to audit
    raise NotImplementedError
