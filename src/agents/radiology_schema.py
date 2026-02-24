"""
Pydantic schemas for the Radiologist agent output.

Covers CXR, CT, MRI, and general radiology interpretations.
All schemas carry requires_review=True — hardcoded, never configurable.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class RadiologyFinding(BaseModel):
    structure: str = Field(
        description=(
            "Anatomical structure being described — e.g., 'right lower lobe', "
            "'cardiac silhouette', 'left costophrenic angle', 'mediastinum'"
        )
    )
    finding: str = Field(
        description=(
            "Description of the finding at this structure. "
            "Use standard radiology terminology: opacity, consolidation, effusion, "
            "atelectasis, cardiomegaly, pneumothorax, nodule, mass, infiltrate, etc. "
            "Include size if measurable."
        )
    )
    is_new: Optional[bool] = Field(
        default=None,
        description=(
            "True if this finding is new compared to prior imaging. "
            "False if unchanged or improved. Null if no prior available."
        )
    )
    change_description: Optional[str] = Field(
        default=None,
        description=(
            "If compared to prior: describe the interval change — "
            "e.g., 'increased in size', 'resolved', 'stable', 'new since prior study'. "
            "Null if no prior available."
        )
    )
    clinical_significance: str = Field(
        description="urgent | significant | incidental | normal variant"
    )


class ProgressionScore(BaseModel):
    overall_drift: str = Field(
        description=(
            "Overall change assessment compared to prior imaging: "
            "improved | stable | worsened | unable_to_assess"
        )
    )
    key_changes: List[str] = Field(
        description=(
            "List of the most clinically significant changes since prior study. "
            "Empty list if no prior or no significant changes."
        )
    )
    time_interval: Optional[str] = Field(
        default=None,
        description="Approximate time since prior study if known — e.g., '3 months', '1 year'"
    )


class RadiologistReport(BaseModel):
    """
    Structured radiology report from the Radiologist agent.
    Produced for CXR, CT, MRI, or any radiological imaging.
    requires_review is hardcoded True.
    """
    modality: str = Field(
        description=(
            "Imaging modality: CXR (chest X-ray) | CT chest | CT abdomen | MRI brain | "
            "CT abdomen/pelvis | CT head | MRI spine | other — specify exactly"
        )
    )
    body_region: str = Field(
        description="Primary anatomical region imaged — e.g., 'chest', 'abdomen', 'brain'"
    )
    indication: str = Field(
        description=(
            "Clinical indication for the study as provided by the referring clinician. "
            "Use '[not documented]' if not stated."
        )
    )
    chain_of_thought: str = Field(
        description=(
            "Explicit radiological reasoning process: "
            "1) Systematic review approach used (e.g., ABCs for CXR), "
            "2) Key normal findings first (to establish baseline), "
            "3) Abnormal findings and their significance, "
            "4) How findings relate to clinical indication, "
            "5) Differential diagnosis for any ambiguous findings, "
            "6) How prior imaging comparison changed the interpretation. "
            "This trace is mandatory for audit purposes."
        )
    )
    technique: str = Field(
        description=(
            "Brief technical description: PA/AP, lateral, contrast, reconstruction, etc. "
            "Use '[not documented]' if not stated."
        )
    )
    findings: List[RadiologyFinding] = Field(
        description=(
            "Systematic per-structure findings. Cover ALL relevant structures for the modality: "
            "For CXR: lungs (each lobe), cardiac silhouette, mediastinum, hila, pleura, "
            "costophrenic angles, bones, soft tissues, tubes/lines if present. "
            "For CT chest: airways, lung parenchyma (each lobe), pleura, mediastinum, "
            "heart/pericardium, great vessels, chest wall, upper abdomen if included. "
            "Document normal structures explicitly — do not skip normal findings."
        )
    )
    impression: str = Field(
        description=(
            "Concise clinical impression — the radiologist's conclusion. "
            "List primary findings in order of clinical importance. "
            "This is what the clinician reads first — be direct and specific."
        )
    )
    progression: Optional[ProgressionScore] = Field(
        default=None,
        description=(
            "Longitudinal comparison with prior imaging. "
            "Null if no prior imaging available for comparison."
        )
    )
    critical_findings: List[str] = Field(
        description=(
            "List of findings requiring immediate clinical notification: "
            "pneumothorax, massive effusion, aortic dissection, pulmonary embolism, "
            "critical cardiomegaly, tension pneumothorax, etc. "
            "Empty list if no critical findings."
        )
    )
    recommendations: List[str] = Field(
        description=(
            "Specific follow-up recommendations: "
            "additional imaging views, CT for characterization, follow-up in N months, "
            "urgent referral, biopsy recommendation, etc."
        )
    )
    comparison_studies: List[str] = Field(
        description=(
            "Prior studies used for comparison — e.g., 'CXR 2024-06-15', 'CT chest 2024-01'. "
            "Empty list if none available."
        )
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. Requires radiologist or clinician review."
    )
