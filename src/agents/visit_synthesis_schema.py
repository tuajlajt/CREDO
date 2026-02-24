"""
Pydantic schema for the VisitSynthesis output from the SynthesisAgent.

This is the final structured record produced after all specialist agents have
contributed their assessments. It drives the form pre-fill in the New Visit UI
and becomes the payload submitted to POST /ehr/patients/{id}/visits.

All outputs carry requires_review = True — hardcoded, never configurable.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from src.agents.gp_schema import SOAPFields


class SynthesisDiagnosis(BaseModel):
    code: str = Field(description="ICD-10 code in format X00.0")
    display: str = Field(description="Short plain-language description of the diagnosis")
    code_system: str = Field(default="ICD-10", description="Coding system (always ICD-10)")
    status: str = Field(
        default="provisional",
        description="Diagnosis status: confirmed | provisional | differential",
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level: high | medium | low",
    )


class SynthesisOrder(BaseModel):
    category: str = Field(description="Order category: lab | imaging | other")
    test_display: str = Field(
        description="Human-readable test name (e.g. 'CBC with differential')"
    )
    test_code: str = Field(
        default="",
        description="Test code (LOINC for labs, CPT for imaging)",
    )
    test_code_system: str = Field(
        default="LOINC",
        description="Code system: LOINC | CPT",
    )
    urgency: str = Field(
        default="routine",
        description="Order urgency: urgent | routine",
    )
    rationale: str = Field(
        default="",
        description="One-sentence clinical rationale for this order",
    )


class CotEntry(BaseModel):
    agent: str = Field(description="Name of the agent that produced this reasoning entry")
    reasoning: str = Field(description="Chain-of-thought reasoning from this agent")


class VisitSynthesis(BaseModel):
    """
    Final synthesised clinical record from the multi-agent board.
    Produced by SynthesisAgent after GP + specialist contributions.
    requires_review is hardcoded True — never change this.
    """

    reason_for_visit: str = Field(
        description="Chief complaint / primary reason for the visit in one sentence"
    )
    soap: SOAPFields
    diagnoses: List[SynthesisDiagnosis] = Field(
        description="Final ICD-10 diagnosis list synthesised from all agent inputs"
    )
    recommended_orders: List[SynthesisOrder] = Field(
        description=(
            "Recommended investigations: lab tests, imaging studies, and other orders. "
            "For each order: category (lab/imaging/other), display name, code, urgency, rationale."
        )
    )
    key_findings: str = Field(
        description=(
            "2-3 sentence clinical summary: what was found across all specialist assessments, "
            "the primary conclusion, and what action is most important."
        )
    )
    agents_invoked: List[str] = Field(
        description="List of agent names that contributed to this synthesis"
    )
    cot_log: List[CotEntry] = Field(
        description="Chain-of-thought log: one entry per agent that ran"
    )
    requires_review: bool = Field(
        default=True,
        description="ALWAYS True. This output requires clinician review before any clinical action.",
    )
    disclaimer: str = Field(
        default="",
        description="Standard AI safety disclaimer",
    )
