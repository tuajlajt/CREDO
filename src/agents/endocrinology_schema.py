"""
Pydantic schemas for the Endocrinologist agent output.

Covers diabetes management, thyroid disorders, and metabolic conditions.
Cross-references multi-organ complications (fundus, cardiac, skin, renal).
All schemas carry requires_review=True — hardcoded, never configurable.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class DiabetesAssessment(BaseModel):
    diabetes_type: Optional[str] = Field(
        default=None,
        description="Type 1 | Type 2 | MODY | gestational | secondary | unknown. Null if no diabetes."
    )
    hba1c_current: Optional[str] = Field(
        default=None,
        description="Current HbA1c value with units and date if available"
    )
    hba1c_trend: Optional[str] = Field(
        default=None,
        description=(
            "HbA1c trajectory based on serial values: "
            "improving | stable | worsening | newly_diagnosed | not_available"
        )
    )
    glycemic_control: Optional[str] = Field(
        default=None,
        description=(
            "Glycemic control classification: "
            "well_controlled (HbA1c <7.0%) | "
            "suboptimal (7.0–8.0%) | "
            "poor (8.1–9.0%) | "
            "very_poor (>9.0%) | "
            "not_assessable"
        )
    )
    diabetes_duration_estimate: Optional[str] = Field(
        default=None,
        description="Estimated duration of diabetes from history if available"
    )
    complications_present: List[str] = Field(
        description=(
            "Active or suspected diabetic complications: "
            "retinopathy, nephropathy, neuropathy, cardiomyopathy, "
            "peripheral vascular disease, diabetic foot. "
            "Empty list if none identified."
        )
    )
    retinopathy_risk: Optional[str] = Field(
        default=None,
        description=(
            "Diabetic retinopathy risk from fundus findings or HbA1c/duration: "
            "no_dr | mild_npdr | moderate_npdr | severe_npdr | pdr | "
            "unable_to_assess. Null if no diabetes."
        )
    )
    current_treatment: Optional[str] = Field(
        default=None,
        description="Current diabetes medications identified: insulin, metformin, GLP-1, SGLT2i, etc."
    )
    treatment_adequacy: Optional[str] = Field(
        default=None,
        description="Assessment of whether current treatment regimen is adequate for glycemic target"
    )


class ThyroidAssessment(BaseModel):
    tsh: Optional[str] = Field(default=None, description="TSH value with units and reference range")
    t3: Optional[str] = Field(default=None, description="T3 (free T3) value if available")
    t4: Optional[str] = Field(default=None, description="T4 (free T4) value if available")
    thyroid_antibodies: Optional[str] = Field(
        default=None,
        description="TPO antibodies, anti-thyroglobulin if measured"
    )
    thyroid_function: str = Field(
        description=(
            "Overall thyroid function: "
            "euthyroid | subclinical_hypothyroid (raised TSH, normal T4) | "
            "overt_hypothyroid (raised TSH, low T4) | "
            "subclinical_hyperthyroid (suppressed TSH, normal T3/T4) | "
            "overt_hyperthyroid (suppressed TSH, raised T3/T4) | "
            "unable_to_assess (no thyroid labs)"
        )
    )
    hashimotos_assessment: Optional[str] = Field(
        default=None,
        description=(
            "Hashimoto's thyroiditis assessment: "
            "positive (elevated TPO antibodies + hypothyroid pattern) | "
            "suspected (hypothyroid without antibody testing) | "
            "negative | not_applicable. "
            "Null if thyroid data insufficient."
        )
    )
    treatment_adequacy: Optional[str] = Field(
        default=None,
        description="If on levothyroxine — is TSH in target range? Dose adequate?"
    )


class EndocrinologyAssessment(BaseModel):
    """
    Structured endocrinology assessment from the Endocrinologist agent.
    The specialist who touches every other specialty — cross-references all organs.
    Diabetes complications affect eyes, heart, kidneys, skin, and nerves.
    """
    chain_of_thought: str = Field(
        description=(
            "Explicit endocrinological reasoning: "
            "1) Glucose/HbA1c trajectory — is diabetes controlled, worsening, or newly diagnosed, "
            "2) Thyroid function pattern — interpret TSH/T3/T4 together, not in isolation, "
            "3) Cross-organ complication mapping for diabetes: "
            "   - Retina: DR staging from fundus or HbA1c/duration risk estimate, "
            "   - Kidney: GFR trajectory, microalbuminuria (nephropathy), "
            "   - Heart: cardiomyopathy risk, HbA1c effect on cardiovascular outcomes, "
            "   - Skin: diabetic dermopathy, acanthosis nigricans, delayed wound healing, "
            "   - Nerves: peripheral neuropathy symptoms, autonomic neuropathy, "
            "4) Metabolic syndrome assessment (waist circumference, BP, lipids, glucose, TG), "
            "5) Hashimoto's monitoring — antibody trend, symptom burden, dose optimization, "
            "6) How endocrine findings modify recommendations from other specialists "
            "   (e.g., HbA1c 10% → high cardiomyopathy risk → escalate cardiac concern; "
            "    uncontrolled diabetes + skin lesion → delayed healing risk), "
            "7) Treatment adequacy and optimization opportunity. "
            "The endocrinologist synthesizes metabolic disease across all organ systems."
        )
    )
    diabetes_assessment: Optional[DiabetesAssessment] = Field(
        default=None,
        description="Comprehensive diabetes assessment. Null if no diabetes identified."
    )
    thyroid_assessment: ThyroidAssessment = Field(
        description="Thyroid function assessment — always required even if normal"
    )
    metabolic_syndrome: Optional[str] = Field(
        default=None,
        description=(
            "Metabolic syndrome assessment: "
            "present (3+ of: central obesity, high TG, low HDL, hypertension, high fasting glucose) | "
            "possible (insufficient data) | absent | not_assessed"
        )
    )
    adrenal_concerns: Optional[str] = Field(
        default=None,
        description=(
            "Any adrenal concerns identified: Cushing's features, Addison's, incidentaloma. "
            "Null if no concerns."
        )
    )
    cross_specialty_flags: List[str] = Field(
        description=(
            "Critical endocrine-driven cross-specialty findings: "
            "'HbA1c 10.5% → high cardiomyopathy risk — escalate to cardiology', "
            "'Severe hypothyroidism → hyperlipidaemia and cardiac risk', "
            "'Uncontrolled T2DM → fundus DR screening overdue', "
            "'HbA1c 12% → impaired wound healing — skin lesion treatment modified'. "
            "These flags flow to the board synthesis agent."
        )
    )
    primary_diagnosis: str = Field(
        description="Primary endocrine diagnosis with confidence"
    )
    differentials: List[str] = Field(
        description="Endocrine differential diagnoses in order of likelihood"
    )
    urgency: str = Field(
        description=(
            "Management urgency: "
            "emergency (DKA, HHS, myxoedema coma, thyroid storm — immediate) | "
            "urgent (severely uncontrolled diabetes >14 mmol/L, overt hypothyroidism, "
            "new severe hypoglycaemia) | "
            "semi-urgent (HbA1c >9%, newly diagnosed T2DM, Hashimoto's review needed) | "
            "routine (stable T2DM, euthyroid on treatment, metabolic monitoring)"
        )
    )
    icd_codes: List[str] = Field(description="ICD-10 codes for identified endocrine conditions")
    recommendations: List[str] = Field(
        description=(
            "Specific endocrine management recommendations: "
            "HbA1c target adjustment, insulin optimization, GLP-1/SGLT2i consideration, "
            "TSH monitoring frequency, levothyroxine dose adjustment, "
            "fundus screening referral, renal function monitoring, "
            "endocrinology referral, diabetes education."
        )
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. Requires endocrinologist or diabetologist review."
    )
