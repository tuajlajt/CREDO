"""
HL7/FHIR clinical record loading and parsing.

Extracts clinical data from FHIR bundles: observations, medications,
conditions, procedures. Returns only coded values — never patient identifiers.

HIPAA minimum necessary: only extract fields the model actually needs.
Never pass patient name, DOB, MRN, or insurance information downstream.

Owner agent: medical-data-engineer
"""
from __future__ import annotations


def extract_observations(fhir_bundle: dict) -> list[dict]:
    """
    Extract lab observations from a FHIR bundle.
    Returns only coded values — no patient identifiers.

    Returns list of dicts with keys: code, display, value, unit, status
    """
    # TODO: implement — see medical-data-engineer.md for reference code
    # Requires: fhir.resources
    raise NotImplementedError


def extract_medications(fhir_bundle: dict) -> list[dict]:
    """
    Extract active medications from a FHIR bundle.
    Returns list of dicts with keys: code, display, dose, route, status
    No patient identifiers.
    """
    # TODO: implement
    raise NotImplementedError


def extract_conditions(fhir_bundle: dict) -> list[dict]:
    """
    Extract conditions/diagnoses from a FHIR bundle.
    Returns list of dicts with keys: code, display, status, onset
    No patient identifiers.
    """
    # TODO: implement
    raise NotImplementedError
