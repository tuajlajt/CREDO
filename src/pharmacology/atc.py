"""
ATC code lookup and therapy-duration inference.

ATC codes are retrieved from RxNav RxClass (ATC mapping).
Therapy duration is inferred from fill history (number of fills in last 365 days).
"""
from __future__ import annotations

import logging
from typing import List, Optional, TypedDict

from src.pharmacology.normalization import approximate_rxcui
from src.pharmacology.rxnav_client import RxNavClient, get_default_client

logger = logging.getLogger(__name__)


class AtcInfo(TypedDict):
    inn: str
    atc_codes: List[str]
    therapy_duration_label: str   # "unknown" | "probable_short_term" | "probable_long_term"
    confidence: str               # "low" | "medium" | "high"
    basis: List[str]


def get_atc_codes_for_inn(
    inn: str,
    client: Optional[RxNavClient] = None,
) -> List[str]:
    """
    Look up ATC codes for an INN via RxNav RxClass API.

    Returns an empty list if the INN cannot be resolved or has no ATC mapping.
    """
    _client = client or get_default_client()
    rxcui = approximate_rxcui(_client, inn)
    if not rxcui:
        logger.debug("get_atc_codes_for_inn: no RxCUI for %r", inn)
        return []

    try:
        data = _client.get_json(
            "/rxclass/class/byRxcui.json",
            params={"rxcui": rxcui, "relaSource": "ATC"},
        )
    except Exception as exc:
        logger.warning("ATC lookup failed for inn=%r rxcui=%s: %s", inn, rxcui, exc)
        return []

    items = data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []) or []
    codes: List[str] = []
    for item in items:
        cls = item.get("rxclassMinConceptItem", {}) or {}
        class_id = cls.get("classId")
        if class_id:
            codes.append(class_id)

    return _dedup_preserve(codes)


def get_atc_and_duration_tag(
    inn: str,
    fills_last_365d: Optional[int] = None,
    client: Optional[RxNavClient] = None,
) -> AtcInfo:
    """
    Return ATC codes plus a therapy-duration label for an INN.

    Duration is inferred from fill history:
        ≥ 4 fills  → probable_long_term  (high confidence)
        3 fills    → probable_long_term  (medium confidence)
        1–2 fills  → unknown             (low confidence)
        0 / None   → unknown             (low confidence)

    Args:
        inn:             INN string.
        fills_last_365d: Number of fills dispensed in the last 365 days.
        client:          RxNavClient instance (defaults to module-level client).

    Returns:
        AtcInfo TypedDict.
    """
    atc_codes = get_atc_codes_for_inn(inn, client=client)

    if fills_last_365d is None:
        return {
            "inn": inn,
            "atc_codes": atc_codes,
            "therapy_duration_label": "unknown",
            "confidence": "low",
            "basis": ["no fill history provided"],
        }

    if fills_last_365d >= 4:
        return {
            "inn": inn,
            "atc_codes": atc_codes,
            "therapy_duration_label": "probable_long_term",
            "confidence": "high",
            "basis": [f"{fills_last_365d} fills in last 365 days"],
        }

    if fills_last_365d == 3:
        return {
            "inn": inn,
            "atc_codes": atc_codes,
            "therapy_duration_label": "probable_long_term",
            "confidence": "medium",
            "basis": ["3 fills in last 365 days"],
        }

    if fills_last_365d in (1, 2):
        return {
            "inn": inn,
            "atc_codes": atc_codes,
            "therapy_duration_label": "unknown",
            "confidence": "low",
            "basis": [f"{fills_last_365d} fill(s) in last 365 days — insufficient to infer"],
        }

    return {
        "inn": inn,
        "atc_codes": atc_codes,
        "therapy_duration_label": "unknown",
        "confidence": "low",
        "basis": ["no fills in last 365 days"],
    }


def _dedup_preserve(items: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out
