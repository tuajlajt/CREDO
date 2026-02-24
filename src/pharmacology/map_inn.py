from __future__ import annotations

from typing import List
import requests


RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


def _get_json(url: str, params: dict[str, str] | None = None) -> dict:
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def drug_to_ingredients(drug_name: str) -> List[str]:
    """
    Translate a drug name (ingredient OR proprietary name with dose)
    into a list of active ingredient names using RxNorm.

    Examples:
        "fluoxetine"      -> ["Fluoxetine"]
        "Prozac 20 mg"    -> ["Fluoxetine"]
        "Augmentin"       -> ["Amoxicillin", "Clavulanate"]

    Returns empty list if resolution fails.
    """
    # 1. Resolve input to an RxCUI (fuzzy match)
    approx = _get_json(
        f"{RXNAV_BASE}/approximateTerm.json",
        params={
            "term": drug_name,
            "maxEntries": "1",
        },
    )

    candidates = approx.get("approximateGroup", {}).get("candidate", [])
    if not candidates:
        return []

    rxcui = candidates[0].get("rxcui")
    if not rxcui:
        return []

    # 2. Fetch ingredients (TTY = IN)
    related = _get_json(
        f"{RXNAV_BASE}/rxcui/{rxcui}/related.json",
        params={"tty": "IN"},
    )

    ingredients = []
    groups = related.get("relatedGroup", {}).get("conceptGroup", [])

    for group in groups:
        for prop in group.get("conceptProperties", []) or []:
            name = prop.get("name")
            if name:
                ingredients.append(name)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for ing in ingredients:
        key = ing.lower()
        if key not in seen:
            seen.add(key)
            unique.append(ing)

    return unique


if __name__ == "__main__":
    tests = [
        "fluoxetine",
        "Prozac 20 mg",
        "Wellbutrin XL",
        "Augmentin",
    ]

    for t in tests:
        print(f"{t!r} -> {drug_to_ingredients(t)}")