"""
Pydantic schemas for the Dermatologist agent output.

Covers skin lesion analysis, inflammatory conditions, drug reactions, and melanoma risk.
All schemas carry requires_review=True — hardcoded, never configurable.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class SkinLesionDescription(BaseModel):
    location: str = Field(description="Anatomical location — e.g., 'left forearm', 'face bilateral'")
    morphology: str = Field(
        description=(
            "Primary lesion morphology using dermatological terminology: "
            "macule | papule | plaque | vesicle | bulla | pustule | nodule | "
            "wheal | ulcer | erosion | excoriation | scale | crust | atrophy | scar. "
            "Include secondary morphology if present."
        )
    )
    color: str = Field(description="Lesion color(s) — e.g., 'erythematous', 'hyperpigmented', 'violaceous'")
    size: Optional[str] = Field(default=None, description="Approximate size or extent if estimable")
    borders: str = Field(
        description="Border characteristics: well-defined | ill-defined | irregular | serpiginous"
    )
    distribution: str = Field(
        description=(
            "Distribution pattern: localized | generalized | dermatomal | "
            "flexural | extensor | photodistributed | follicular | linear"
        )
    )
    special_features: Optional[str] = Field(
        default=None,
        description="Notable features: Wickham striae, Koebner phenomenon, satellite lesions, etc."
    )


class MelanomaRiskAssessment(BaseModel):
    abcde_asymmetry: str = Field(description="Asymmetry assessment: symmetric | mildly asymmetric | asymmetric")
    abcde_border: str = Field(description="Border: regular | irregular | notched")
    abcde_color: str = Field(description="Color: uniform | multiple colors | variegated")
    abcde_diameter: Optional[str] = Field(default=None, description="Estimated diameter vs 6mm threshold")
    abcde_evolving: Optional[str] = Field(default=None, description="Reported changes over time if any")
    overall_risk: str = Field(description="low | intermediate | high — refer for biopsy if high")
    referral_recommended: bool = Field(
        description="True if dermoscopy, dermatology referral, or biopsy is recommended"
    )


class AtopicMarchAssessment(BaseModel):
    eczema_present: bool = Field(description="Atopic dermatitis/eczema identified")
    asthma_history: Optional[bool] = Field(
        default=None,
        description="Known asthma history from EHR or transcript. Null if not documented."
    )
    allergic_rhinitis_history: Optional[bool] = Field(
        default=None,
        description="Known allergic rhinitis. Null if not documented."
    )
    atopic_march_risk: str = Field(
        description=(
            "Risk of atopic march progression: "
            "low | moderate | high. "
            "high = eczema + asthma or allergic rhinitis history present."
        )
    )
    recommendation: str = Field(
        description="Clinical recommendation regarding atopic march monitoring and management"
    )


class DermatologyAssessment(BaseModel):
    """
    Structured dermatology assessment from the Dermatologist agent.
    Based on skin image analysis + clinical context.
    """
    chain_of_thought: str = Field(
        description=(
            "Explicit dermatological reasoning: "
            "1) Systematic description of all lesions identified, "
            "2) Differential diagnosis construction with supporting features, "
            "3) Features that support or refute each differential, "
            "4) How patient history (medications, atopy, family history) modifies assessment, "
            "5) Melanoma screening assessment if relevant, "
            "6) Drug reaction consideration — review current medications for skin side effects, "
            "7) Reasoning for urgency and recommendations. "
            "Be exhaustive — this is the audit trail for clinical reasoning."
        )
    )
    lesion_descriptions: List[SkinLesionDescription] = Field(
        description="Systematic description of each distinct lesion or lesion group identified"
    )
    primary_diagnosis: str = Field(
        description=(
            "Most likely diagnosis with confidence — e.g., "
            "'Atopic dermatitis (high confidence)', "
            "'Psoriasis vulgaris (moderate confidence)', "
            "'Contact dermatitis (possible — allergen identification needed)'"
        )
    )
    differentials: List[str] = Field(
        description=(
            "Differential diagnoses in order of likelihood. "
            "For each: name + key distinguishing features for/against. "
            "Include at minimum 3 differentials for any ambiguous presentation."
        )
    )
    melanoma_risk: Optional[MelanomaRiskAssessment] = Field(
        default=None,
        description=(
            "ABCDE melanoma assessment. Required if any pigmented lesion is present. "
            "Null only if no pigmented lesions."
        )
    )
    drug_reaction_assessment: Optional[str] = Field(
        default=None,
        description=(
            "Drug-induced skin reaction assessment: review patient's medication list for "
            "common skin side effects (antibiotics, NSAIDs, anticonvulsants, ACE inhibitors, "
            "biologics). State whether current presentation could be drug-induced and which drug. "
            "Null if no medications on record."
        )
    )
    atopic_march: Optional[AtopicMarchAssessment] = Field(
        default=None,
        description=(
            "Atopic march assessment — required if eczema/atopic dermatitis is in differentials. "
            "Null if no atopic presentation."
        )
    )
    medsiglip_findings: Optional[str] = Field(
        default=None,
        description=(
            "MedSigLIP zero-shot classification results if available — "
            "top predicted conditions with confidence scores. "
            "Note if these align with or diverge from visual assessment."
        )
    )
    urgency: str = Field(
        description=(
            "Management urgency: "
            "emergency (suspected melanoma/SCC requiring same-day referral) | "
            "urgent (infected eczema, cellulitis, blistering disorders) | "
            "semi-urgent (new pigmented lesion requiring dermoscopy within 2 weeks) | "
            "routine (chronic stable condition)"
        )
    )
    icd_codes: List[str] = Field(
        description="ICD-10 codes for identified dermatological conditions"
    )
    recommendations: List[str] = Field(
        description=(
            "Specific management recommendations: "
            "topical/systemic treatment options, biopsy, dermoscopy, "
            "allergen patch testing, dermatology referral, follow-up timeline."
        )
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. Requires dermatologist or clinician review."
    )
