"""
Pydantic schemas for the Cardiologist agent output.

Covers cardiac assessment integrating lab values, imaging findings, and vital sign trends.
All schemas carry requires_review=True — hardcoded, never configurable.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CardiacLabValues(BaseModel):
    troponin: Optional[str] = Field(default=None, description="Troponin I or T value with units and reference range")
    bnp_or_ntprobnp: Optional[str] = Field(default=None, description="BNP or NT-proBNP value with units")
    creatine_kinase: Optional[str] = Field(default=None, description="CK or CK-MB value")
    d_dimer: Optional[str] = Field(default=None, description="D-dimer if measured")
    cholesterol_ldl: Optional[str] = Field(default=None, description="LDL cholesterol")
    cholesterol_hdl: Optional[str] = Field(default=None, description="HDL cholesterol")
    crp: Optional[str] = Field(default=None, description="C-reactive protein")
    interpretation: str = Field(
        description=(
            "Clinical interpretation of all available cardiac lab values together — "
            "not just individual abnormalities but the pattern they form. "
            "e.g., 'Elevated troponin with raised BNP suggests acute myocardial stress "
            "in the context of heart failure decompensation.'"
        )
    )


class HeartFailureAssessment(BaseModel):
    nyha_class: Optional[str] = Field(
        default=None,
        description="NYHA functional class I | II | III | IV if determinable. Null if insufficient data."
    )
    acc_aha_stage: Optional[str] = Field(
        default=None,
        description="ACC/AHA heart failure stage A | B | C | D if determinable."
    )
    ef_estimate: Optional[str] = Field(
        default=None,
        description="Ejection fraction if known from echocardiography or inferred from clinical data"
    )
    hfref_vs_hfpef: Optional[str] = Field(
        default=None,
        description="HFrEF (reduced EF <40%) | HFpEF (preserved EF >=50%) | indeterminate"
    )
    congestion_signs: List[str] = Field(
        description="Signs of congestion identified: peripheral edema, pulmonary crackles, JVD, S3 gallop, etc."
    )
    clinical_evidence: str = Field(
        description="Evidence basis for this heart failure staging — what data supports the classification"
    )


class CardiologyAssessment(BaseModel):
    """
    Structured cardiology assessment from the Cardiologist agent.
    Integrates cardiac labs, CXR cardiac findings, vital sign trends, and patient history.
    """
    chain_of_thought: str = Field(
        description=(
            "Explicit cardiac reasoning: "
            "1) Systematic assessment of cardiac symptoms (chest pain character — onset, "
            "duration, radiation, associated symptoms, exertional vs rest; palpitations; "
            "dyspnea — orthopnea, PND, exertional), "
            "2) Cardiac biomarker interpretation (troponin kinetics, BNP trajectory), "
            "3) ECG findings if available, "
            "4) Imaging findings — cardiac silhouette size, pulmonary vascularity, "
            "pleural effusions as cardiac indicators, "
            "5) Risk factor burden (hypertension, diabetes, smoking, family history, "
            "hyperlipidemia, age/sex), "
            "6) Differential diagnosis construction with probability weighting, "
            "7) Urgency determination — ACS rule-in/rule-out pathway if applicable, "
            "8) How diabetic cardiomyopathy or other systemic disease modifies the picture. "
            "Be thorough — cardiac misses are catastrophic."
        )
    )
    cardiac_symptoms_summary: str = Field(
        description=(
            "Summary of cardiac symptoms from transcript: chest pain, palpitations, "
            "dyspnea, syncope, presyncope, ankle swelling. "
            "Characterize each symptom precisely. Use '[not documented]' if absent."
        )
    )
    cardiac_labs: CardiacLabValues = Field(
        description="Structured interpretation of all available cardiac laboratory values"
    )
    heart_failure_assessment: Optional[HeartFailureAssessment] = Field(
        default=None,
        description="Heart failure staging if relevant. Null if no heart failure suspected."
    )
    acs_risk: str = Field(
        description=(
            "Acute coronary syndrome risk assessment: "
            "high (troponin rise, typical chest pain, ECG changes — activate ACS pathway) | "
            "intermediate (atypical features, risk factors, serial troponins needed) | "
            "low (troponin negative x2, atypical history, no risk factors) | "
            "unable_to_assess (insufficient data)"
        )
    )
    arrhythmia_concerns: List[str] = Field(
        description=(
            "Any arrhythmia concerns: QT prolongation risk (from medications or electrolytes), "
            "palpitations differential, AF/flutter features. Empty list if none."
        )
    )
    cardiomegaly_assessment: Optional[str] = Field(
        default=None,
        description=(
            "Cardiomegaly assessment from CXR: "
            "cardiothoracic ratio estimate, comparison with prior, clinical significance. "
            "Null if no CXR available."
        )
    )
    primary_diagnosis: str = Field(
        description="Most likely cardiac diagnosis with confidence level"
    )
    differentials: List[str] = Field(
        description="Cardiac differential diagnoses in order of likelihood with key supporting features"
    )
    urgency: str = Field(
        description=(
            "Management urgency: "
            "emergency (active ACS, severe HF decompensation, critical arrhythmia — call cardiology now) | "
            "urgent (elevated troponin, new HF presentation, hemodynamically compromised) | "
            "semi-urgent (stable angina, compensated HF, new findings needing outpatient cardiology) | "
            "routine (stable chronic cardiac disease, risk factor management)"
        )
    )
    icd_codes: List[str] = Field(description="ICD-10 codes for identified cardiac conditions")
    recommendations: List[str] = Field(
        description=(
            "Specific cardiac management recommendations: "
            "serial troponins, ECG, echocardiography, stress testing, coronary angiography, "
            "Holter monitoring, cardiology referral urgency, medication adjustments."
        )
    )
    diabetic_cardiomyopathy_risk: Optional[str] = Field(
        default=None,
        description=(
            "If patient has diabetes: assess cardiomyopathy risk based on HbA1c, "
            "duration of diabetes, cardiac findings. "
            "low | moderate | high | requires_echo_assessment. Null if no diabetes."
        )
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. Cardiac assessments require cardiologist or senior clinician review."
    )
