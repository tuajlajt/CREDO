"""
Full DDI safety pipeline.

Runs the complete drug-drug interaction and side-effect analysis for a list of
medicines or INNs:

    1. Normalise inputs to INNs via RxNorm
    2. Check RxNav interactions (batch)
    3. PubMed RAG evidence retrieval + rule-based claim extraction
    4. Combine RxNav + RAG results conservatively
    5. Fetch ATC codes + infer therapy duration
    6. Aggregate side effects from openFDA
    7. Fuzzy-match patient symptoms to aggregated side effects

Usage:
    from src.pharmacology.pipeline import run_pipeline
    from src.pharmacology.config import load_config

    cfg = load_config()
    report = run_pipeline(
        cfg,
        medicines_or_inns=["Prozac 20 mg", "bupropion", "methylphenidate"],
        patient_symptoms=["insomnia", "nausea", "heart racing"],
        fills_last_365d_by_inn={"Fluoxetine": 6, "Bupropion": 5},
    )
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from src.pharmacology.atc import get_atc_and_duration_tag
from src.pharmacology.combine_results import combine_interaction_results
from src.pharmacology.config import AppConfig, load_config
from src.pharmacology.interactions import check_all_interactions_among_ingredients
from src.pharmacology.normalization import resolve_drug_list_to_inns
from src.pharmacology.pubmed_rag import (
    build_pubmed_query,
    pubmed_fetch_summaries,
    pubmed_search_pmids,
    rule_based_extract_claims,
)
from src.pharmacology.rxnav_client import RxNavClient, RxNavConfig
from src.pharmacology.side_effects_openfda import aggregate_side_effects
from src.pharmacology.symptom_matcher import match_symptoms_to_effects

logger = logging.getLogger(__name__)


class PipelineReport(TypedDict):
    inns: List[str]
    rxnav_interactions: List[dict]
    rag_interactions: List[dict]
    combined_interactions: List[dict]
    atc_and_duration: List[Dict[str, Any]]
    side_effects_aggregated: List[Dict[str, Any]]
    symptom_matches: List[Dict[str, Any]]


def run_pipeline(
    cfg: AppConfig,
    medicines_or_inns: List[str],
    *,
    patient_symptoms: Optional[List[str]] = None,
    fills_last_365d_by_inn: Optional[Dict[str, int]] = None,
) -> PipelineReport:
    """
    Run the full DDI safety pipeline for a list of medicines or INNs.

    Args:
        cfg:                    AppConfig loaded from configs/pharmacology.yaml.
        medicines_or_inns:      Drug names, brand names, or INN strings.
        patient_symptoms:       Patient-reported symptoms (lay terms accepted).
        fills_last_365d_by_inn: {inn: fill_count} mapping for duration inference.

    Returns:
        PipelineReport TypedDict with all analysis results.
    """
    rx_client = RxNavClient(
        RxNavConfig(
            base_url=cfg.rxnav.base_url,
            timeout_s=cfg.rxnav.timeout_s,
            polite_delay_s=cfg.rxnav.polite_delay_s,
            max_retries=cfg.rxnav.max_retries,
            backoff_factor=cfg.rxnav.backoff_factor,
        )
    )

    # 1) Normalise all inputs to INNs
    inns = resolve_drug_list_to_inns(medicines_or_inns, client=rx_client)
    logger.info("Pipeline: resolved %d medicine(s) → %d INN(s)", len(medicines_or_inns), len(inns))

    # 2) RxNav batch interaction check
    rxnav_interactions = check_all_interactions_among_ingredients(
        inns,
        polite_delay_s=cfg.rxnav.polite_delay_s,
    )
    logger.info("Pipeline: %d RxNav interaction(s) found", len(rxnav_interactions))

    # 3) PubMed RAG — rule-based claim extraction (no LLM required for baseline)
    rag_interactions = []
    for i in range(len(inns)):
        for j in range(i + 1, len(inns)):
            inn_a, inn_b = inns[i], inns[j]
            query = build_pubmed_query(inn_a, inn_b)
            pmids = pubmed_search_pmids(
                query,
                retmax=cfg.rag.pubmed_retmax,
                api_key=cfg.rag.ncbi_api_key,
            )
            summaries = pubmed_fetch_summaries(pmids, api_key=cfg.rag.ncbi_api_key)
            claims = rule_based_extract_claims(inn_a, inn_b, summaries)
            rag_interactions.extend(claims)
    logger.info("Pipeline: %d RAG claim(s) found", len(rag_interactions))

    # 4) Conservative combination
    combined = combine_interaction_results(rxnav_interactions, rag_interactions)

    # 5) ATC codes + therapy duration tags
    fills = fills_last_365d_by_inn or {}
    atc_duration = [
        get_atc_and_duration_tag(inn, fills_last_365d=fills.get(inn), client=rx_client)
        for inn in inns
    ]

    # 6) Side effects from openFDA
    aggregated_effects = aggregate_side_effects(inns)

    # 7) Symptom → side-effect matching
    symptom_matches = match_symptoms_to_effects(
        patient_symptoms or [],
        aggregated_effects,
        threshold=cfg.symptoms.match_threshold,
    )

    return {
        "inns": inns,
        "rxnav_interactions": [
            {
                "ingredient_1_inn": r.ingredient_1_inn,
                "ingredient_2_inn": r.ingredient_2_inn,
                "interaction": r.interaction,
                "severity": r.severity,
            }
            for r in rxnav_interactions
        ],
        "rag_interactions": list(rag_interactions),
        "combined_interactions": list(combined),
        "atc_and_duration": list(atc_duration),
        "side_effects_aggregated": list(aggregated_effects),
        "symptom_matches": list(symptom_matches),
    }


if __name__ == "__main__":
    import json

    cfg = load_config()
    report = run_pipeline(
        cfg,
        medicines_or_inns=["Prozac 20 mg", "bupropion", "methylphenidate"],
        patient_symptoms=["insomnia", "nausea", "heart racing"],
        fills_last_365d_by_inn={"Fluoxetine": 6, "Bupropion": 5},
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
