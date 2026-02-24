"""
Pydantic schemas for the Pulmonologist agent output.

Covers respiratory assessment including CXR lung findings, spirometry, and atopic march.
All schemas carry requires_review=True — hardcoded, never configurable.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class PFTInterpretation(BaseModel):
    fev1_fvc_ratio: Optional[str] = Field(
        default=None,
        description="FEV1/FVC ratio — below 0.70 indicates obstruction"
    )
    fev1_percent_predicted: Optional[str] = Field(
        default=None,
        description="FEV1 as percentage of predicted — used to grade obstruction severity"
    )
    obstruction_pattern: Optional[str] = Field(
        default=None,
        description="none | mild | moderate | severe | very_severe"
    )
    reversibility: Optional[str] = Field(
        default=None,
        description=(
            "Response to bronchodilator: significant (>12% and >200mL FEV1 increase) | "
            "partial | none. Null if reversibility not tested."
        )
    )
    dlco: Optional[str] = Field(
        default=None,
        description="Diffusion capacity (DLCO) — reduced in emphysema, ILD, pulmonary hypertension"
    )
    interpretation: str = Field(
        description="Overall PFT interpretation: normal | obstructive | restrictive | mixed"
    )


class PleuralAssessment(BaseModel):
    side: str = Field(description="right | left | bilateral")
    finding: str = Field(
        description=(
            "pleural_effusion | pleural_thickening | pneumothorax | "
            "haemothorax | empyema | pleural_plaques"
        )
    )
    size: str = Field(description="small | moderate | large | tension (for pneumothorax)")
    change_from_prior: Optional[str] = Field(
        default=None,
        description="Comparison with prior: increased | stable | decreased | resolved | new"
    )
    clinical_significance: str = Field(description="urgent | significant | monitor | incidental")


class PulmonologyAssessment(BaseModel):
    """
    Structured pulmonology assessment from the Pulmonologist agent.
    Integrates CXR lung findings, PFT data, symptom history, and atopic context.
    """
    chain_of_thought: str = Field(
        description=(
            "Explicit pulmonological reasoning: "
            "1) Respiratory symptom characterization (dyspnea — onset, duration, exertional vs rest, "
            "orthopnea; cough — productive vs dry, duration, triggers, nocturnal; "
            "wheeze — episodic vs persistent; haemoptysis), "
            "2) Smoking history and pack-year calculation if available, "
            "3) Occupational and environmental exposure history, "
            "4) Atopy assessment — eczema, allergic rhinitis, family atopy history, "
            "5) Systematic review of lung fields: upper zones (TB, sarcoid), "
            "mid zones (infection, malignancy), lower zones (effusion, collapse, consolidation), "
            "6) PFT pattern interpretation and correlation with symptoms, "
            "7) COPD GOLD staging if applicable, "
            "8) Asthma severity/control assessment if applicable, "
            "9) Interstitial lung disease pattern recognition if relevant, "
            "10) Atopic march assessment — eczema-asthma-rhinitis triad. "
            "Pulmonary diagnoses missed early cause significant long-term morbidity."
        )
    )
    respiratory_symptoms_summary: str = Field(
        description=(
            "Summary of respiratory symptoms: dyspnea (MRC grade if determinable), "
            "cough character, sputum production, wheeze, haemoptysis. "
            "Use '[not documented]' if absent."
        )
    )
    smoking_history: Optional[str] = Field(
        default=None,
        description=(
            "Smoking status and pack-year history if available: "
            "never | ex-smoker (pack-years, quit date) | current (pack-years). "
            "Null if not documented."
        )
    )
    pft_interpretation: Optional[PFTInterpretation] = Field(
        default=None,
        description="Pulmonary function test interpretation. Null if PFT data not available."
    )
    lung_findings_on_imaging: List[str] = Field(
        description=(
            "Pulmonary-specific imaging findings from CXR/CT: "
            "consolidation, ground-glass opacity, effusion, emphysema, "
            "nodules, masses, hyperinflation, reticular pattern. "
            "Include location and size where possible."
        )
    )
    pleural_findings: List[PleuralAssessment] = Field(
        description="Pleural findings if present. Empty list if pleura is clear."
    )
    copd_assessment: Optional[str] = Field(
        default=None,
        description=(
            "COPD GOLD stage if applicable: GOLD 1 (mild, FEV1 ≥80%) | "
            "GOLD 2 (moderate, 50–79%) | GOLD 3 (severe, 30–49%) | "
            "GOLD 4 (very severe, <30%). Include exacerbation risk group. "
            "Null if COPD not applicable."
        )
    )
    asthma_assessment: Optional[str] = Field(
        default=None,
        description=(
            "Asthma severity and control: "
            "intermittent | mild persistent | moderate persistent | severe persistent. "
            "Control: well-controlled | partially controlled | uncontrolled. "
            "Null if asthma not applicable."
        )
    )
    atopic_march_assessment: Optional[str] = Field(
        default=None,
        description=(
            "Atopic march assessment if eczema or asthma present: "
            "describe the triad status (eczema present, asthma status, rhinitis status) "
            "and progression risk. Recommend combined derm+pulm management if triad active."
        )
    )
    primary_diagnosis: str = Field(
        description="Primary pulmonary diagnosis with confidence"
    )
    differentials: List[str] = Field(
        description="Pulmonary differential diagnoses in order of likelihood"
    )
    urgency: str = Field(
        description=(
            "Management urgency: "
            "emergency (tension pneumothorax, acute severe asthma, massive PE, "
            "respiratory failure — immediate intervention) | "
            "urgent (large effusion, acute exacerbation COPD, haemoptysis) | "
            "semi-urgent (new nodule needing CT characterization, "
            "uncontrolled asthma needing specialist review within 2 weeks) | "
            "routine (stable COPD, mild asthma, monitoring)"
        )
    )
    icd_codes: List[str] = Field(description="ICD-10 codes for identified pulmonary conditions")
    recommendations: List[str] = Field(
        description=(
            "Specific pulmonary management recommendations: "
            "HRCT for ILD, pleural aspiration, bronchoscopy, "
            "spirometry, pulmonary rehabilitation, inhaler review, "
            "oxygen therapy, pulmonology referral urgency."
        )
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. Requires pulmonologist or clinician review."
    )
