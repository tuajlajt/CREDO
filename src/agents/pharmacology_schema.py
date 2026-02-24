"""
Pydantic schemas for the Pharmacology / DDI agent output.

Covers drug-drug interactions, medication reviews, and symptom-medication correlations.
All schemas carry requires_review=True — hardcoded, never configurable.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class InteractionSummary(BaseModel):
    drug_a: str = Field(description="First drug name (INN/generic preferred)")
    drug_b: str = Field(description="Second drug name (INN/generic preferred)")
    severity: str = Field(
        description=(
            "Severity level: critical | major | moderate | minor. "
            "critical = contraindicated, life-threatening risk. "
            "major = potentially life-threatening or causing permanent damage. "
            "moderate = may cause clinical deterioration requiring monitoring. "
            "minor = minimally significant, usually no change needed."
        )
    )
    mechanism: Optional[str] = Field(
        default=None,
        description=(
            "Pharmacokinetic or pharmacodynamic mechanism: e.g., "
            "'CYP3A4 inhibition', 'additive QT prolongation', 'serotonin syndrome risk', "
            "'increased bleeding risk (additive anticoagulation)'. Null if unknown."
        )
    )
    description: str = Field(
        description=(
            "Clinical description of the interaction and its consequences. "
            "Be specific: what happens, in which patients, how significant is the risk."
        )
    )
    management: str = Field(
        description=(
            "Recommended management: avoid combination | monitor closely | "
            "dose adjustment (specify) | no action required | timing separation. "
            "Be actionable."
        )
    )
    evidence_source: str = Field(
        description="Data source: RxNav | literature | clinical guideline | case reports"
    )


class MedicationReview(BaseModel):
    drug_name: str = Field(description="Drug name as provided (brand or generic)")
    resolved_inn: Optional[str] = Field(
        default=None,
        description="Resolved INN (international non-proprietary name) via RxNorm"
    )
    atc_codes: List[str] = Field(
        description="ATC codes for this drug. Empty list if not found."
    )
    therapy_duration_label: str = Field(
        description="probable_long_term | probable_short_term | unknown"
    )
    duration_confidence: str = Field(description="Confidence: high | medium | low")
    notes: Optional[str] = Field(
        default=None,
        description="Any notable points about this drug in context of this patient's profile"
    )


class SymptomMedicationCorrelation(BaseModel):
    symptom: str = Field(description="Patient symptom from transcript")
    suspected_drug: str = Field(description="Drug potentially causing this symptom")
    side_effect_name: str = Field(description="Matched known side effect name from database")
    similarity_score: float = Field(
        description="Matching confidence 0.0–1.0. Values above 0.82 considered reliable."
    )
    mechanism: Optional[str] = Field(
        default=None,
        description="Pharmacological mechanism explaining how this drug causes this symptom"
    )
    recommendation: str = Field(
        description=(
            "Clinical recommendation: "
            "consider_discontinuation | monitor_closely | adjust_dose | "
            "review_with_clinician | likely_coincidental. "
            "Always recommend clinician review for serious symptoms."
        )
    )
    confidence: str = Field(description="high | medium | low")


class DDIReport(BaseModel):
    """
    Drug-drug interaction report from the DDI Engine.
    Produced by running all active medications through RxNav + RAG.
    """
    medications_checked: List[str] = Field(
        description="All drug names that were checked in this report"
    )
    resolved_inns: List[str] = Field(
        description="INN names resolved from the input drug list via RxNorm"
    )
    interactions: List[InteractionSummary] = Field(
        description=(
            "All interactions found, ordered by severity (critical first). "
            "Empty list if no interactions found."
        )
    )
    critical_count: int = Field(description="Number of critical-severity interactions")
    major_count: int = Field(description="Number of major-severity interactions")
    moderate_count: int = Field(description="Number of moderate-severity interactions")
    overall_risk_level: str = Field(
        description=(
            "Overall risk summary: critical | high | moderate | low | none_found. "
            "Set to critical if any critical interaction exists. "
            "Set to high if any major interaction exists. "
            "Set to moderate if any moderate interaction. "
            "Set to low/none_found otherwise."
        )
    )
    recommendations: List[str] = Field(
        description=(
            "Top-level clinical recommendations for the prescriber — "
            "specific and actionable. Address the most serious interactions first."
        )
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. DDI checks require clinical pharmacist or prescriber review."
    )


class PharmacologyAssessment(BaseModel):
    """
    Complete pharmacology assessment combining DDI checks and side-effect analysis.
    Produced by PharmacologyAgent for the board synthesis stage.
    """
    medications: List[MedicationReview] = Field(
        description="Individual review of each medication in the patient's regimen"
    )
    ddi_findings: DDIReport = Field(
        description="Drug-drug interaction report for the complete medication list"
    )
    symptom_correlations: List[SymptomMedicationCorrelation] = Field(
        description=(
            "Correlations between patient symptoms (from transcript) and "
            "known side effects of current medications. "
            "Empty list if no symptoms were mentioned or no correlations found."
        )
    )
    polypharmacy_risk: str = Field(
        description=(
            "Overall polypharmacy burden assessment: "
            "high (5+ medications) | moderate (3–4) | low (1–2) | none (0). "
            "Include brief note on management complexity."
        )
    )
    risk_flags: List[str] = Field(
        description=(
            "Specific clinical safety flags requiring attention: "
            "'Critical DDI: warfarin + aspirin', "
            "'Dry cough likely from ACE inhibitor', "
            "'QT prolongation risk with current combination', etc."
        )
    )
    recommendations: List[str] = Field(
        description=(
            "Prioritized clinical recommendations: "
            "medication changes, monitoring parameters, timing adjustments, "
            "renal/hepatic function checks, therapeutic drug monitoring."
        )
    )
    chain_of_thought: str = Field(
        description=(
            "Pharmacological reasoning process: "
            "1) Medication list review and INN resolution, "
            "2) DDI analysis — which pairs were checked and what was found, "
            "3) Symptom-medication correlation analysis, "
            "4) Polypharmacy burden assessment, "
            "5) Risk prioritization and recommendation rationale. "
            "This is the audit trace for the pharmacology review."
        )
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. Requires pharmacist or prescriber review."
    )
