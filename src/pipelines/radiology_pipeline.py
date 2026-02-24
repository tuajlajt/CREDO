"""
Radiology end-to-end pipeline.

Full pipeline: DICOM image (de-identified) → structured radiology report.
Orchestrates: medical-cv-agent (preprocessing) → CXR/CT Foundation (embeddings)
→ MedGemma 4B (report generation) → radiologist-agent (structuring).

Owner agent: radiologist-agent
Config: configs/agents/radiologist_agent.yaml
"""
from __future__ import annotations


def run_radiology_pipeline(
    dicom_path: str,
    modality: str,
) -> dict:
    """
    Full pipeline: DICOM → RadiologyReport.

    Args:
        dicom_path: Path to de-identified DICOM file or series directory
        modality: "CXR" | "CT" | "MRI"

    Returns:
        RadiologyReport as dict with requires_review=True always.
        Includes critical_findings list — check before returning to caller.
    """
    from src.data.dicom_loader import load_dicom_series, validate_dicom_input
    from src.agents.radiologist_agent import RadiologistAgent

    # TODO: load config from configs/agents/radiologist_agent.yaml
    config = {}

    agent = RadiologistAgent(config)
    # TODO: implement — preprocess → embed → report
    raise NotImplementedError
