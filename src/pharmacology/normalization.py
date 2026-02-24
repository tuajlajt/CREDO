"""
Drug name normalization via RxNorm API.

Resolves brand names, dose-form strings, and INNs → canonical INN ingredient names.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from src.pharmacology.rxnav_client import RxNavClient, get_default_client

logger = logging.getLogger(__name__)


def approximate_rxcui(
    client: RxNavClient,
    term: str,
) -> Optional[str]:
    """Resolve a drug string to its best-matching RxCUI."""
    try:
        data = client.get_json(
            "/approximateTerm.json",
            params={"term": term, "maxEntries": "1"},
            use_cache=True,
        )
    except Exception as exc:
        logger.warning("approximate_rxcui failed for %r: %s", term, exc)
        return None

    candidates = data.get("approximateGroup", {}).get("candidate", []) or []
    if not candidates:
        return None
    return candidates[0].get("rxcui")


def rxcui_to_ingredients(
    client: RxNavClient,
    rxcui: str,
) -> List[Tuple[str, str]]:
    """
    Fetch ingredient (TTY=IN) concepts for an RxCUI.
    Returns list of (ingredient_rxcui, ingredient_name).
    """
    try:
        related = client.get_json(
            f"/rxcui/{rxcui}/related.json",
            params={"tty": "IN"},
            use_cache=True,
        )
    except Exception as exc:
        logger.warning("rxcui_to_ingredients failed for rxcui=%s: %s", rxcui, exc)
        return []

    out: List[Tuple[str, str]] = []
    groups = related.get("relatedGroup", {}).get("conceptGroup", []) or []
    for group in groups:
        for prop in group.get("conceptProperties", []) or []:
            ing_rxcui = prop.get("rxcui")
            ing_name = prop.get("name")
            if ing_rxcui and ing_name:
                out.append((ing_rxcui, ing_name))
    return out


def rxcui_name(client: RxNavClient, rxcui: str) -> Optional[str]:
    """Get the display name for a given RxCUI."""
    try:
        data = client.get_json(
            f"/rxcui/{rxcui}/properties.json",
            use_cache=True,
        )
        return data.get("properties", {}).get("name")
    except Exception as exc:
        logger.warning("rxcui_name failed for rxcui=%s: %s", rxcui, exc)
        return None


def medicine_to_inns(
    client: RxNavClient,
    medicine_str: str,
) -> List[str]:
    """
    Map a medicine string (brand name, dose-form string, or INN) → list of INN names.

    Examples:
        "Prozac 20 mg"  → ["Fluoxetine"]
        "Augmentin"     → ["Amoxicillin", "Clavulanate"]
        "fluoxetine"    → ["Fluoxetine"]

    Returns [] if the name cannot be resolved.
    """
    term = medicine_str.strip()
    if not term:
        return []

    rxcui = approximate_rxcui(client, term)
    if not rxcui:
        logger.debug("medicine_to_inns: no RxCUI found for %r", term)
        return []

    ings = rxcui_to_ingredients(client, rxcui)
    if ings:
        return _dedup_preserve([name for _, name in ings])

    # Fallback: if RxCUI is already an ingredient itself
    name = rxcui_name(client, rxcui)
    if name:
        return [name]

    return []


def inns_to_ingredient_rxcuis(
    client: RxNavClient,
    inns: List[str],
) -> Dict[str, str]:
    """
    Resolve a list of INN strings → {ingredient_rxcui: inn_name} mapping.
    Used by the DDI checker to build the RxCUI set for the interaction query.
    """
    out: Dict[str, str] = {}
    for inn in inns:
        rxcui = approximate_rxcui(client, inn)
        if not rxcui:
            logger.debug("inns_to_ingredient_rxcuis: no RxCUI for %r", inn)
            continue

        ings = rxcui_to_ingredients(client, rxcui)
        if ings:
            for ing_rxcui, ing_name in ings:
                out[ing_rxcui] = ing_name
        else:
            name = rxcui_name(client, rxcui)
            if name:
                out[rxcui] = name

    return out


def resolve_drug_list_to_inns(
    medicine_strings: List[str],
    client: Optional[RxNavClient] = None,
) -> List[str]:
    """
    Convenience function: resolve a list of drug strings → deduplicated INN list.
    Uses the default RxNavClient if none provided.
    """
    _client = client or get_default_client()
    inns: List[str] = []
    for med in medicine_strings:
        resolved = medicine_to_inns(_client, med)
        if resolved:
            inns.extend(resolved)
        else:
            # Keep original name if resolution fails so we don't silently drop it
            logger.warning("Could not resolve %r to INN — keeping original name", med)
            inns.append(med.strip())
    return _dedup_preserve(inns)


def _dedup_preserve(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        key = x.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out
