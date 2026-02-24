"""
Side-effect aggregation across a list of INNs.

Accepts any SideEffectProvider (openFDA, SIDER JSON, …) and combines results
by normalised effect name, computing combined probability and maximum severity.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, TypedDict

from src.pharmacology.side_effect_provider import SideEffect, SideEffectProvider

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = ["mild", "moderate", "severe", "serious", "unknown"]


class AggregatedEffect(TypedDict):
    effect: str
    contributors: List[str]                 # INNs that contribute this effect
    combined_probability: Optional[float]   # naive independence combination
    max_severity: Optional[str]
    details: List[SideEffect]


def aggregate_side_effects(
    provider: SideEffectProvider,
    inns: List[str],
) -> List[AggregatedEffect]:
    """
    Aggregate side effects for a list of INNs using a pluggable provider.

    - Groups identical (normalised) effects across all INNs
    - Combines probabilities with 1 − Π(1−p) (independence assumption)
    - Takes the highest severity when reported

    Args:
        provider: Any object implementing SideEffectProvider protocol.
        inns:     List of INN strings.

    Returns:
        Sorted list of AggregatedEffect dicts (highest combined probability first).
    """
    bucket: Dict[str, List[tuple]] = defaultdict(list)

    for inn in inns:
        try:
            effects = provider.get_side_effects(inn)
        except Exception as exc:
            logger.warning("Side-effect provider failed for %r: %s", inn, exc)
            effects = []

        for se in effects:
            key = _norm_effect(se["effect"])
            bucket[key].append((inn, se))

    out: List[AggregatedEffect] = []
    for key, items in bucket.items():
        contributors = _dedup_preserve([inn for inn, _ in items])
        details = [se for _, se in items]
        combined_p = _combine_probabilities([se.get("probability") for se in details])
        max_sev = _max_severity([se.get("severity") for se in details])

        out.append({
            "effect": key,
            "contributors": contributors,
            "combined_probability": combined_p,
            "max_severity": max_sev,
            "details": details,
        })

    # Sort: known probability first (descending), then alphabetical
    return sorted(
        out,
        key=lambda x: (x["combined_probability"] is None, -(x["combined_probability"] or 0.0)),
    )


def _combine_probabilities(ps: List[Optional[float]]) -> Optional[float]:
    clean = [p for p in ps if isinstance(p, (int, float)) and 0.0 <= float(p) <= 1.0]
    if not clean:
        return None
    product = 1.0
    for p in clean:
        product *= (1.0 - float(p))
    return round(1.0 - product, 4)


def _max_severity(severities: List[Optional[str]]) -> Optional[str]:
    clean = [s.strip().lower() for s in severities if s and s.strip()]
    if not clean:
        return None
    ranked = {name: i for i, name in enumerate(_SEVERITY_ORDER)}

    def rank(s: str) -> int:
        return ranked.get(s, ranked.get("unknown", 999))

    return max(clean, key=rank)


def _norm_effect(effect: str) -> str:
    return " ".join(effect.strip().lower().split())


def _dedup_preserve(items: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for x in items:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out
