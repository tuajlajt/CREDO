"""
Pydantic schemas for the General Practitioner agent output.

All schemas carry requires_review=True — hardcoded, never configurable.
Use these with src/models/medgemma/structured_output.py.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class SOAPFields(BaseModel):
    subjective: str = Field(
        description=(
            "Patient's chief complaint, symptoms, history of present illness, "
            "past medical history, medications, allergies, social and family history "
            "as stated in the transcript. Use '[not documented]' if absent."
        )
    )
    objective: str = Field(
        description=(
            "Vital signs, physical examination findings, current lab values, "
            "imaging results as stated. Use '[not documented]' if absent."
        )
    )
    assessment: str = Field(
        description=(
            "Clinician's diagnosis, clinical impression, or differential diagnoses "
            "as stated or strongly implied. Use '[not documented]' if absent."
        )
    )
    plan: str = Field(
        description=(
            "Treatment plan, prescriptions, referrals, follow-up instructions, "
            "monitoring orders as stated. Use '[not documented]' if absent."
        )
    )


class ICDCode(BaseModel):
    code: str = Field(description="ICD-10 code in format X00.0")
    description: str = Field(description="Short plain-language description of the diagnosis")
    confidence: str = Field(description="Confidence level: high | medium | low")
    basis: str = Field(description="One sentence explaining why this code applies")


class UrgencyAssessment(BaseModel):
    level: str = Field(description="Urgency level: emergency | urgent | routine")
    rationale: str = Field(
        description=(
            "One to two sentences explaining why this urgency level was assigned. "
            "emergency = life-threatening, needs immediate care; "
            "urgent = needs same-day or next-day care; "
            "routine = can be managed at next scheduled visit."
        )
    )


class DifferentialDiagnosis(BaseModel):
    diagnosis: str = Field(description="Name of the diagnosis being considered")
    reasoning: str = Field(
        description=(
            "Clinical reasoning supporting this diagnosis — symptoms, signs, "
            "or history elements that point to it."
        )
    )
    probability: str = Field(description="Likelihood: most likely | possible | less likely")


class SpecialistReferral(BaseModel):
    specialty: str = Field(description="Medical specialty to consult (e.g., Cardiology)")
    reason: str = Field(description="Clinical reason for referral in one sentence")
    urgency: str = Field(description="Urgency of referral: urgent | semi-urgent | elective")


class BoardRoutingDecision(BaseModel):
    consult_radiologist: bool = Field(
        description="True if imaging is present or imaging findings need specialist interpretation"
    )
    consult_cardiologist: bool = Field(
        description=(
            "True if cardiac symptoms (chest pain, palpitations, dyspnea), "
            "elevated troponin/BNP, or cardiomegaly on CXR"
        )
    )
    consult_dermatologist: bool = Field(
        description="True if skin images present or skin condition described in transcript"
    )
    consult_pulmonologist: bool = Field(
        description=(
            "True if lung findings on CXR, respiratory symptoms, asthma, COPD, "
            "or effusion/emphysema suspected"
        )
    )
    consult_endocrinologist: bool = Field(
        description=(
            "True if HbA1c > 6.5%, diabetes management concerns, thyroid abnormalities "
            "(TSH/T3/T4), or metabolic disorders"
        )
    )
    consult_pharmacology: bool = Field(
        description=(
            "True always when patient is on 2+ medications — DDI check and "
            "symptom-medication correlation should run on every visit with polypharmacy"
        )
    )
    routing_rationale: str = Field(
        description=(
            "Chain-of-thought explanation: for each true flag, state the specific "
            "evidence (lab value, symptom, image finding) that triggered that routing. "
            "Be explicit about what data drove each decision."
        )
    )
    context_packets: Optional[str] = Field(
        default=None,
        description=(
            "Brief summary of key context to forward to each consulted specialist: "
            "what the attending found, what question needs answering, patient history "
            "most relevant to that specialty."
        )
    )


class GPAssessment(BaseModel):
    """
    Full GP/attending assessment output.
    Produced by GPAgent, used as input to BoardRoutingDecision and Stage 05 synthesis.
    requires_review is hardcoded True — never change this.
    """
    chief_complaint: str = Field(description="Primary reason for the visit in one sentence")
    chain_of_thought: str = Field(
        description=(
            "Explicit step-by-step clinical reasoning: "
            "1) What the presenting complaint tells you, "
            "2) Relevant history and risk factors identified, "
            "3) How the objective findings modify your assessment, "
            "4) Why you reached the differential diagnoses below, "
            "5) What drives the urgency classification. "
            "This is the audit trail for clinical reasoning — be thorough."
        )
    )
    soap: SOAPFields
    urgency: UrgencyAssessment
    differentials: List[DifferentialDiagnosis] = Field(
        description="Top 3–5 differential diagnoses, ordered from most to least likely"
    )
    recommended_workup: List[str] = Field(
        description=(
            "Specific investigations to order: lab tests (with rationale), "
            "imaging studies, ECG, specialist referrals. Be specific — "
            "'CBC with differential' not just 'blood tests'."
        )
    )
    icd_codes: List[ICDCode] = Field(
        description="ICD-10 codes for conditions clearly stated or strongly implied in the encounter"
    )
    medications_mentioned: List[str] = Field(
        description="All medications named in the transcript (brand or generic, exactly as stated)"
    )
    allergies_mentioned: List[str] = Field(
        description="All allergies and adverse reactions mentioned"
    )
    specialist_referrals: List[SpecialistReferral] = Field(
        description="Formal referral recommendations for conditions beyond GP scope"
    )
    board_routing: BoardRoutingDecision = Field(
        description=(
            "Which specialist AI agents to convene for this case. "
            "The attending makes this routing decision based on all available evidence."
        )
    )
    documentation_gaps: List[str] = Field(
        description=(
            "Information that would be clinically useful but was not documented — "
            "e.g., 'smoking history not mentioned', 'no vital signs recorded'. "
            "Use this to prompt the clinician to complete the record."
        )
    )
    summary: str = Field(
        description=(
            "One paragraph clinical summary: who the patient is, why they came in, "
            "what was found, and what will be done — suitable for handover."
        )
    )
    requires_review: bool = Field(
        default=True,
        description=(
            "ALWAYS True. This output requires clinician review before any clinical action."
        )
    )
