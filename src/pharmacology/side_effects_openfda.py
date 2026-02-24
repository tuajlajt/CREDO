"""
Side effects provider using openFDA drug label API.

Retrieves adverse reaction terms from FDA drug labels for a given INN.
Falls back gracefully when the API is unavailable or the drug is not found.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, TypedDict

import requests

logger = logging.getLogger(__name__)

OPENFDA_BASE = "https://api.fda.gov/drug/label.json"


class SideEffect(TypedDict):
    effect: str
    severity: Optional[str]       # not reliably available from openFDA
    probability: Optional[float]  # not available from openFDA
    source: str
    evidence_ref: Optional[str]


def get_side_effects_openfda(
    inn: str,
    max_effects: int = 30,
) -> List[SideEffect]:
    """
    Retrieve adverse reaction terms from openFDA drug labels for a given INN.

    Args:
        inn:         International non-proprietary name (ingredient name).
        max_effects: Maximum number of adverse reaction terms to return.

    Returns:
        List of SideEffect dicts. Empty list if drug not found or API unavailable.
    """
    # openFDA label search by active ingredient
    params = {
        "search": f'openfda.generic_name:"{inn}" OR openfda.substance_name:"{inn}"',
        "limit": "5",  # fetch up to 5 labels and aggregate
    }

    try:
        r = requests.get(OPENFDA_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.debug("openFDA: no label found for %r", inn)
        else:
            logger.warning("openFDA request failed for %r: %s", inn, exc)
        return []
    except Exception as exc:
        logger.warning("openFDA request error for %r: %s", inn, exc)
        return []

    results = data.get("results", []) or []
    if not results:
        return []

    # Aggregate adverse reaction terms from all returned labels
    all_terms: List[str] = []
    for label in results:
        ar_sections = label.get("adverse_reactions", []) or []
        for section_text in ar_sections:
            terms = _extract_terms_from_section(section_text)
            all_terms.extend(terms)

    # Deduplicate preserving order
    seen = set()
    unique_terms: List[str] = []
    for t in all_terms:
        key = t.lower()
        if key not in seen and len(t) > 2:
            seen.add(key)
            unique_terms.append(t)

    unique_terms = unique_terms[:max_effects]

    return [
        {
            "effect": term,
            "severity": None,
            "probability": None,
            "source": "openFDA",
            "evidence_ref": f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{inn}",
        }
        for term in unique_terms
    ]


def _extract_terms_from_section(text: str) -> List[str]:
    """
    Extract individual adverse effect terms from a free-text adverse reactions section.

    openFDA label text is unstructured. We use a simple heuristic:
    split on commas, semicolons, and common delimiters then clean up.
    """
    if not text:
        return []

    # Split on common delimiters
    raw_terms = re.split(r"[,;/\n•\*\-\(\)]", text)

    terms: List[str] = []
    for t in raw_terms:
        # Clean up whitespace and digits
        clean = re.sub(r"\d+\.?\d*%?", "", t).strip()
        clean = re.sub(r"\s+", " ", clean).strip("(). \t")

        # Keep terms between 3 and 40 characters
        # (shorter = abbreviations; longer = usually sentences)
        if 3 <= len(clean) <= 40 and not any(
            stop in clean.lower() for stop in [
                "include", "following", "patient", "clinical", "study",
                "treatment", "adverse", "reaction", "report", "table",
            ]
        ):
            terms.append(clean.lower())

    return terms


class AggregatedEffect(TypedDict):
    effect: str
    contributors: List[str]
    combined_probability: Optional[float]
    max_severity: Optional[str]
    details: List[SideEffect]


def aggregate_side_effects(
    inns: List[str],
) -> List[AggregatedEffect]:
    """
    Aggregate side effects across all INNs in a medication list.

    - Fetches effects from openFDA for each INN
    - Groups identical/similar effects by normalized name
    - Returns sorted list (by number of contributing drugs, then alphabetical)
    """
    from collections import defaultdict

    bucket: dict = defaultdict(list)

    for inn in inns:
        effects = get_side_effects_openfda(inn)
        for se in effects:
            key = _norm_effect(se["effect"])
            bucket[key].append((inn, se))

    out: List[AggregatedEffect] = []
    for key, items in bucket.items():
        contributors = _dedup_preserve([inn for inn, _ in items])
        details = [se for _, se in items]
        out.append({
            "effect": key,
            "contributors": contributors,
            "combined_probability": None,  # openFDA has no probability data
            "max_severity": None,
            "details": details,
        })

    # Sort: more contributors first (multi-drug effects are more clinically relevant)
    return sorted(out, key=lambda x: (-len(x["contributors"]), x["effect"]))


def _norm_effect(effect: str) -> str:
    return " ".join(effect.strip().lower().split())


def _dedup_preserve(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out
