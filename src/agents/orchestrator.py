"""
Multi-agent orchestrator.

Reads GPAssessment.board_routing flags and invokes the appropriate
specialist agents sequentially, collecting their outputs.

Layer: agents (consumes gp_schema outputs, invokes specialist agents)
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run_specialists(
    board_routing: dict,
    transcript: str,
    ehr_summary: str,
    drug_names: list[str],
    patient_symptoms: list[str],
    config: dict,
    image=None,
) -> dict[str, dict]:
    """
    Invoke specialist agents as directed by the GP's board routing decision.

    Args:
        board_routing:     BoardRoutingDecision dict from GPAssessment.
        transcript:        Clinical transcript (de-identified).
        ehr_summary:       Formatted EHR context string.
        drug_names:        Active medication INNs (for pharmacology agent).
        patient_symptoms:  Symptom list extracted from transcript / GP assessment.
        config:            Application config dict.
        image:             Optional PIL.Image.Image (de-identified) for image-capable agents.

    Returns:
        Dict mapping agent name → result dict for every invoked specialist.
    """
    results: dict[str, dict] = {}
    context_packets = board_routing.get("context_packets") or ""
    base_context = _build_specialist_context(transcript, ehr_summary, context_packets)

    # ── Pharmacology ──────────────────────────────────────────────────────────
    if board_routing.get("consult_pharmacology") and drug_names:
        logger.info(
            "Orchestrator: invoking PharmacologyAgent for %d drug(s)", len(drug_names)
        )
        try:
            from src.agents.pharmacology_agent import PharmacologyAgent

            result = PharmacologyAgent(config).run(
                drug_names=drug_names,
                patient_symptoms=patient_symptoms or [],
            )
            results["pharmacology"] = result
        except Exception as exc:
            logger.error("PharmacologyAgent failed: %s", exc)
            results["pharmacology"] = {"_error": str(exc), "requires_review": True}

    # ── Radiologist ───────────────────────────────────────────────────────────
    if board_routing.get("consult_radiologist"):
        logger.info("Orchestrator: invoking RadiologistAgent")
        try:
            from src.agents.radiologist_agent import RadiologistAgent

            result = RadiologistAgent(config).run(
                context=base_context,
                image=image,
            )
            results["radiologist"] = result
        except Exception as exc:
            logger.error("RadiologistAgent failed: %s", exc)
            results["radiologist"] = {"_error": str(exc), "requires_review": True}

    # ── Dermatologist ─────────────────────────────────────────────────────────
    if board_routing.get("consult_dermatologist"):
        logger.info("Orchestrator: invoking DermatologistAgent")
        try:
            from src.agents.dermatologist_agent import DermatologistAgent

            result = DermatologistAgent(config).run(
                context=base_context,
                image=image,
            )
            results["dermatologist"] = result
        except Exception as exc:
            logger.error("DermatologistAgent failed: %s", exc)
            results["dermatologist"] = {"_error": str(exc), "requires_review": True}

    # ── Cardiologist ──────────────────────────────────────────────────────────
    if board_routing.get("consult_cardiologist"):
        logger.info("Orchestrator: invoking CardiologistAgent")
        try:
            from src.agents.cardiologist_agent import CardiologistAgent

            result = CardiologistAgent(config).run(
                context=base_context,
                image=image,
            )
            results["cardiologist"] = result
        except Exception as exc:
            logger.error("CardiologistAgent failed: %s", exc)
            results["cardiologist"] = {"_error": str(exc), "requires_review": True}

    # ── Pulmonologist ─────────────────────────────────────────────────────────
    if board_routing.get("consult_pulmonologist"):
        logger.info("Orchestrator: invoking PulmonologistAgent")
        try:
            from src.agents.pulmonologist_agent import PulmonologistAgent

            result = PulmonologistAgent(config).run(
                context=base_context,
                image=image,
            )
            results["pulmonologist"] = result
        except Exception as exc:
            logger.error("PulmonologistAgent failed: %s", exc)
            results["pulmonologist"] = {"_error": str(exc), "requires_review": True}

    # ── Endocrinologist ───────────────────────────────────────────────────────
    if board_routing.get("consult_endocrinologist"):
        logger.info("Orchestrator: invoking EndocrinologistAgent")
        try:
            from src.agents.endocrinologist_agent import EndocrinologistAgent

            result = EndocrinologistAgent(config).run(
                context=base_context,
                image=image,
            )
            results["endocrinologist"] = result
        except Exception as exc:
            logger.error("EndocrinologistAgent failed: %s", exc)
            results["endocrinologist"] = {"_error": str(exc), "requires_review": True}

    logger.info(
        "Orchestrator: %d specialist(s) invoked: %s",
        len(results),
        list(results.keys()),
    )
    return results


def _build_specialist_context(
    transcript: str,
    ehr_summary: str,
    context_packets: str,
) -> str:
    """Build a context string for specialist agents."""
    parts = [f"CLINICAL TRANSCRIPT:\n{transcript}"]
    if ehr_summary:
        parts.append(f"PATIENT EHR SUMMARY:\n{ehr_summary}")
    if context_packets:
        parts.append(f"GP ATTENDING CONTEXT:\n{context_packets}")
    return "\n\n".join(parts)
