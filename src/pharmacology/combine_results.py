"""
Combine RxNav interaction results and RAG-derived claims into a unified report.

Conservative policy:
- If RxNav has interactions → overall_risk_signal = "present"
- If RAG has claims → overall_risk_signal = "present"
- If both empty → "none_found"
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple, TypedDict

from src.pharmacology.interactions import InteractionResult
from src.pharmacology.pubmed_rag import RagInteractionClaim

logger = logging.getLogger(__name__)


class CombinedInteraction(TypedDict):
    ingredient_1_inn: str
    ingredient_2_inn: str
    rxnav: List[dict]
    rag: List[RagInteractionClaim]
    conservative_summary: str
    overall_risk_signal: str   # "present" | "none_found" | "uncertain"


def combine_interaction_results(
    rxnav_results: List[InteractionResult],
    rag_results: List[RagInteractionClaim],
) -> List[CombinedInteraction]:
    """
    Merge RxNav and RAG interaction results by drug pair.

    Returns one CombinedInteraction per unique pair, with conservative_summary
    and overall_risk_signal derived from both sources.
    """
    idx: Dict[Tuple[str, str], CombinedInteraction] = {}

    def _norm_pair(a: str, b: str) -> Tuple[str, str]:
        left, right = sorted([a.strip(), b.strip()], key=lambda x: x.lower())
        return left, right

    # Merge RxNav results (dataclasses → access via attributes)
    for r in rxnav_results:
        pair = _norm_pair(r.ingredient_1_inn, r.ingredient_2_inn)
        if pair not in idx:
            idx[pair] = _empty_combined(pair[0], pair[1])
        idx[pair]["rxnav"].append({
            "ingredient_1_inn": r.ingredient_1_inn,
            "ingredient_2_inn": r.ingredient_2_inn,
            "interaction": r.interaction,
            "severity": r.severity,
        })

    # Merge RAG results (TypedDicts)
    for c in rag_results:
        pair = _norm_pair(c["ingredient_1_inn"], c["ingredient_2_inn"])
        if pair not in idx:
            idx[pair] = _empty_combined(pair[0], pair[1])
        idx[pair]["rag"].append(c)

    # Compute summaries and risk signals
    for item in idx.values():
        has_rxnav = len(item["rxnav"]) > 0
        has_rag = len(item["rag"]) > 0
        item["overall_risk_signal"] = "present" if (has_rxnav or has_rag) else "none_found"
        item["conservative_summary"] = _make_summary(item["rxnav"], item["rag"])

    return list(idx.values())


def _empty_combined(inn_a: str, inn_b: str) -> CombinedInteraction:
    return {
        "ingredient_1_inn": inn_a,
        "ingredient_2_inn": inn_b,
        "rxnav": [],
        "rag": [],
        "conservative_summary": "",
        "overall_risk_signal": "uncertain",
    }


def _make_summary(rxnav: List[dict], rag: List[RagInteractionClaim]) -> str:
    parts: List[str] = []

    if rxnav:
        severities = sorted({(x.get("severity") or "unknown").lower() for x in rxnav})
        parts.append(
            f"RxNav flags interaction(s). Severities reported: {', '.join(severities)}."
        )
    else:
        parts.append("RxNav did not report an interaction for this pair.")

    if rag:
        parts.append(
            f"Literature retrieval found {len(rag)} structured claim(s) with PubMed citations."
        )
    else:
        parts.append(
            "Literature retrieval produced no structured claims "
            "(may be retrieval or model limits)."
        )

    parts.append(
        "Treat as clinically relevant if patient has risk factors or symptoms; "
        "verify with pharmacist or prescriber."
    )
    return " ".join(parts)
