"""
Drug-drug interaction checker using FDA drug label data (openFDA).

The RxNav Drug-Drug Interaction API was discontinued on 2024-01-02.
This module uses the openFDA drug label endpoint to identify interactions:
  1. Resolve input names to canonical INNs via RxNorm (still working).
  2. For each pair (A, B), fetch drug A's FDA label and scan the
     drug_interactions section for mentions of drug B.
  3. Infer severity from keywords in the interaction text.

Interface is identical to the old RxNav-based version so downstream
code (drug_check_pipeline.py, tests) requires no changes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_LABEL_BASE = "https://api.fda.gov/drug/label.json"

# Severity keyword groups (checked in descending priority)
_CRITICAL_WORDS = [
    "contraindicated", "do not use", "must not", "fatal",
    "life-threatening", "severe bleeding", "intracranial hemorrhage",
]
_HIGH_WORDS = [
    "avoid", "major", "serious", "significantly increase",
    "substantially", "bleeding risk", "risk of bleeding",
    "increase the risk of bleeding", "hemorrhage", "dangerous",
    "marked increase", "markedly increased",
]
_LOW_WORDS = [
    "minor", "minimal", "slight", "small increase", "unlikely",
]


@dataclass(frozen=True)
class InteractionResult:
    ingredient_1_inn: str
    ingredient_2_inn: str
    interaction: str
    severity: str  # low | med | high | critical


# ── RxNorm helpers (still working) ────────────────────────────────────────────

def _get_json(url: str, params: Optional[Dict[str, str]] = None) -> dict:
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _approximate_rxcui(term: str) -> Optional[str]:
    data = _get_json(
        f"{RXNAV_BASE}/approximateTerm.json",
        params={"term": term, "maxEntries": "1"},
    )
    candidates = data.get("approximateGroup", {}).get("candidate", []) or []
    if not candidates:
        return None
    return candidates[0].get("rxcui")


def _rxcui_name(rxcui: str) -> Optional[str]:
    data = _get_json(f"{RXNAV_BASE}/rxcui/{rxcui}/properties.json")
    return data.get("properties", {}).get("name")


def _rxcui_to_ingredient_inn(rxcui: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Given any RxCUI (ingredient or product), attempt to return:
      (ingredient_rxcui, ingredient_name_inn-ish)
    """
    related = _get_json(
        f"{RXNAV_BASE}/rxcui/{rxcui}/related.json",
        params={"tty": "IN"},
    )
    concept_groups = related.get("relatedGroup", {}).get("conceptGroup", []) or []
    for group in concept_groups:
        for prop in group.get("conceptProperties", []) or []:
            ing_rxcui = prop.get("rxcui")
            ing_name = prop.get("name")
            if ing_rxcui and ing_name:
                return ing_rxcui, ing_name

    name = _rxcui_name(rxcui)
    return rxcui, name


def resolve_to_inn_ingredients(
    ingredients: Iterable[str],
    *,
    polite_delay_s: float = 0.05,
) -> Dict[str, str]:
    """
    Resolve user-provided ingredient strings to a mapping:
      IN_RxCUI -> INN name
    """
    resolved: Dict[str, str] = {}

    for raw in ingredients:
        term = raw.strip()
        if not term:
            continue

        rxcui = _approximate_rxcui(term)
        if not rxcui:
            continue

        ing_rxcui, ing_name = _rxcui_to_ingredient_inn(rxcui)
        if ing_rxcui and ing_name:
            resolved[ing_rxcui] = ing_name

        if polite_delay_s:
            time.sleep(polite_delay_s)

    return resolved


# ── OpenFDA label-based interaction helpers ────────────────────────────────────

def _get_fda_interaction_text(inn: str) -> str:
    """
    Fetch the drug_interactions section text from the FDA label for a given INN.
    Returns empty string if not found or request fails.
    """
    try:
        r = requests.get(
            OPENFDA_LABEL_BASE,
            params={
                "search": f'openfda.generic_name:"{inn}" OR openfda.substance_name:"{inn}"',
                "limit": "3",
            },
            timeout=15,
        )
        if r.status_code == 404:
            return ""
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.debug("openFDA label fetch failed for %r: %s", inn, exc)
        return ""

    results = data.get("results", [])
    texts: list[str] = []
    for label in results:
        for section in label.get("drug_interactions", []):
            if section:
                texts.append(section)
    return " ".join(texts)


def _extract_interaction_sentence(text: str, drug_name: str) -> str:
    """
    Extract the most relevant sentence mentioning drug_name from text.
    Falls back to a generic description if no specific sentence found.
    """
    # Split on period, semicolon, or newline
    for sep in (".", ";", "\n"):
        for sent in text.split(sep):
            if drug_name.lower() in sent.lower():
                clean = sent.strip()
                if len(clean) > 20:
                    return clean[:300]
    return f"Interaction with {drug_name} noted in FDA drug label."


def _infer_severity(text: str) -> str:
    """Infer severity bucket (low | med | high | critical) from free text."""
    lower = text.lower()
    if any(w in lower for w in _CRITICAL_WORDS):
        return "critical"
    if any(w in lower for w in _HIGH_WORDS):
        return "high"
    if any(w in lower for w in _LOW_WORDS):
        return "low"
    return "med"


# ── Public API ─────────────────────────────────────────────────────────────────

def check_all_interactions_among_ingredients(
    ingredients: List[str],
    *,
    polite_delay_s: float = 0.05,
) -> List[InteractionResult]:
    """
    Takes a list of ingredient strings (ideally INNs) and returns all interactions
    among them using FDA drug label data (openFDA).

    Note: The RxNav Drug Interaction API was discontinued 2024-01-02.
    Interaction data is now sourced from FDA drug labels via openFDA.

    Output fields:
      - ingredient_1_inn
      - ingredient_2_inn
      - interaction (text description from FDA label)
      - severity bucket: low | med | high | critical
    """
    # 1) Resolve to canonical INN names via RxNorm (still works)
    inn_map = resolve_to_inn_ingredients(ingredients, polite_delay_s=polite_delay_s)
    inn_names = list(inn_map.values())

    # If fewer than 2 resolved, fall back to raw names so the check still runs
    if len(inn_names) < 2:
        inn_names = [i.strip().lower() for i in ingredients if i.strip()]

    if len(inn_names) < 2:
        return []

    # 2) For each ordered pair (A, B): check A's FDA label for mention of B
    results: Dict[Tuple[str, str], InteractionResult] = {}

    for i, inn_a in enumerate(inn_names):
        interaction_text_a = _get_fda_interaction_text(inn_a)
        if polite_delay_s:
            time.sleep(polite_delay_s)

        for j, inn_b in enumerate(inn_names):
            if i == j:
                continue

            # Canonical dedup key: sorted pair
            left, right = (inn_a, inn_b) if inn_a.lower() < inn_b.lower() else (inn_b, inn_a)
            key = (left.lower(), right.lower())
            if key in results:
                continue  # already found from the other direction

            if inn_b.lower() in interaction_text_a.lower():
                description = _extract_interaction_sentence(interaction_text_a, inn_b)
                severity = _infer_severity(description)
                logger.debug(
                    "FDA label interaction: %s + %s [%s]", inn_a, inn_b, severity
                )
                results[key] = InteractionResult(
                    ingredient_1_inn=left,
                    ingredient_2_inn=right,
                    interaction=description,
                    severity=severity,
                )

    return list(results.values())


if __name__ == "__main__":
    ings = ["warfarin", "aspirin", "metformin"]
    out = check_all_interactions_among_ingredients(ings)
    for item in sorted(out, key=lambda x: (x.severity, x.ingredient_1_inn, x.ingredient_2_inn)):
        print(item)
