"""
“Importance” / priority of meds (Rx vs OTC) — reality check

There’s no universal “importance” field that reliably tells you “this is prescribed so it’s more important than OTC”
purely from the ingredient name. That’s a clinical judgement + context problem.

What we can do programmatically:

- Add a tag like rx_otc_status by looking up products in openFDA (drug label / NDC data),
  which includes structured label fields and product metadata.

- If you only have ingredients (INNs), the mapping to “Rx vs OTC”
  can be ambiguous because some substances exist in both contexts (dose/form dependent).

So the honest approach:
-  If you have the exact product (or NDC / package): you can often classify Rx/OTC from label/NDC metadata.

-  If you only have ingredient: you can only say “commonly Rx”, “commonly OTC”, or “both” —
   and you’ll still be wrong sometimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time

import requests

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"


@dataclass(frozen=True)
class InteractionFinding:
    ingredient_1_inn: str
    ingredient_2_inn: str
    interaction: str
    severity: Optional[str]  # keep RxNav's label as-is


def _get_json(url: str, params: Optional[Dict[str, str]] = None) -> dict:
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _resolve_to_ingredient_rxcui(inn_or_name: str) -> Optional[Tuple[str, str]]:
    """
    Resolve a drug string to an ingredient (TTY=IN) RxCUI + ingredient name.
    Works best when input is an INN, but also often works for branded strings.
    """
    term = inn_or_name.strip()
    if not term:
        return None

    approx = _get_json(
        f"{RXNAV_BASE}/approximateTerm.json",
        params={"term": term, "maxEntries": "1"},
    )
    candidates = approx.get("approximateGroup", {}).get("candidate", []) or []
    if not candidates:
        return None

    rxcui = candidates[0].get("rxcui")
    if not rxcui:
        return None

    # Get ingredient(s) (TTY=IN) related to that concept
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

    # Fallback: if it already was an ingredient, use its properties name
    props = _get_json(f"{RXNAV_BASE}/rxcui/{rxcui}/properties.json")
    name = props.get("properties", {}).get("name")
    if name:
        return rxcui, name

    return None


def check_interactions_pairwise(
    ingredients_inn: List[str],
    *,
    polite_delay_s: float = 0.05,
) -> List[InteractionFinding]:
    """
    Checks all unique ingredient pairs (i<j) for interactions using RxNav.

    Returns:
        List[InteractionFinding]. If no interactions exist among the set, returns [].
    """
    # Resolve inputs to ingredient RxCUIs + canonical names
    inn_by_rxcui: Dict[str, str] = {}
    for raw in ingredients_inn:
        resolved = _resolve_to_ingredient_rxcui(raw)
        if resolved:
            ing_rxcui, ing_name = resolved
            inn_by_rxcui[ing_rxcui] = ing_name
        if polite_delay_s:
            time.sleep(polite_delay_s)

    rxcuis = list(inn_by_rxcui.keys())
    if len(rxcuis) < 2:
        return []

    results: Dict[Tuple[str, str, str, str], InteractionFinding] = {}

    for i in range(len(rxcuis)):
        for j in range(i + 1, len(rxcuis)):
            a_rxcui = rxcuis[i]
            b_rxcui = rxcuis[j]

            data = _get_json(
                f"{RXNAV_BASE}/interaction/list.json",
                params={"rxcuis": f"{a_rxcui}+{b_rxcui}"},
            )

            groups = data.get("fullInteractionTypeGroup", []) or []
            if not groups:
                continue

            a_name = inn_by_rxcui[a_rxcui]
            b_name = inn_by_rxcui[b_rxcui]
            left, right = sorted([a_name, b_name], key=lambda x: x.lower())

            for group in groups:
                for fit in group.get("fullInteractionType", []) or []:
                    for pair in fit.get("interactionPair", []) or []:
                        desc = (pair.get("description") or "").strip()
                        sev = pair.get("severity")  # keep raw label
                        if not desc:
                            continue

                        key = (left.lower(), right.lower(), (sev or "").lower(), desc.lower())
                        results[key] = InteractionFinding(
                            ingredient_1_inn=left,
                            ingredient_2_inn=right,
                            interaction=desc,
                            severity=sev,
                        )

            if polite_delay_s:
                time.sleep(polite_delay_s)

    return list(results.values())