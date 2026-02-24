"""
PubMed RAG component for DDI evidence retrieval.

Searches PubMed for literature on drug-drug interactions and returns
structured evidence references with PMIDs and citations.

All claims must have at least one citation — no uncited claims are produced.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, TypedDict

import requests

logger = logging.getLogger(__name__)

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Interaction-signal keywords for rule-based extraction
_INTERACTION_SIGNALS = [
    "interaction", "inhibit", "induc", "increas", "decreas", "elevat", "reduc",
    "potentiat", "contraindic", "adverse", "toxicit", "serotonin", "bleeding",
    "clearance", "metabolism", "cytochrome", "CYP", "P450", "QT prolongat",
    "additive", "synergistic", "antagonist",
]
_SIGNAL_RE = re.compile(
    "|".join(_INTERACTION_SIGNALS),
    flags=re.IGNORECASE,
)


class EvidenceRef(TypedDict):
    pmid: str
    title: str
    year: Optional[str]
    journal: Optional[str]
    pubmed_url: str


class RagInteractionClaim(TypedDict):
    ingredient_1_inn: str
    ingredient_2_inn: str
    claim: str
    mechanism: Optional[str]
    severity_or_risk: Optional[str]
    claim_confidence: str      # "high" | "medium" | "low"
    citations: List[EvidenceRef]


def pubmed_search_pmids(
    query: str,
    retmax: int = 8,
    api_key: Optional[str] = None,
) -> List[str]:
    """Search PubMed and return a list of PMIDs."""
    params: Dict[str, str] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(retmax),
    }
    if api_key:
        params["api_key"] = api_key

    try:
        r = requests.get(f"{NCBI_EUTILS}/esearch.fcgi", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        return data.get("esearchresult", {}).get("idlist", []) or []
    except Exception as exc:
        logger.warning("PubMed search failed for query=%r: %s", query[:80], exc)
        return []


def pubmed_fetch_summaries(
    pmids: List[str],
    api_key: Optional[str] = None,
) -> Dict[str, EvidenceRef]:
    """Fetch PubMed document summaries for a list of PMIDs."""
    if not pmids:
        return {}

    params: Dict[str, str] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key

    try:
        r = requests.get(f"{NCBI_EUTILS}/esummary.fcgi", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.warning("PubMed fetch failed for pmids=%s: %s", pmids[:3], exc)
        return {}

    result = data.get("result", {}) or {}
    out: Dict[str, EvidenceRef] = {}
    for pmid in pmids:
        item = result.get(pmid)
        if not item or not isinstance(item, dict):
            continue
        out[pmid] = {
            "pmid": pmid,
            "title": item.get("title", ""),
            "year": ((item.get("pubdate", "") or "")[:4]) or None,
            "journal": item.get("fulljournalname") or item.get("source"),
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
    return out


def build_pubmed_query(inn_a: str, inn_b: str) -> str:
    """Build a conservative PubMed search query for a drug pair."""
    return (
        f'("{inn_a}"[Title/Abstract]) AND ("{inn_b}"[Title/Abstract]) '
        f'AND (interaction OR "drug-drug" OR "adverse" OR contraindicat* '
        f'OR pharmacokinetic OR pharmacodynamic OR "CYP" OR "serotonin syndrome")'
    )


def rule_based_extract_claims(
    inn_a: str,
    inn_b: str,
    summaries: Dict[str, EvidenceRef],
) -> List[RagInteractionClaim]:
    """
    Rule-based interaction signal extraction from PubMed titles.

    This is the baseline extractor that runs WITHOUT an LLM.
    It looks for interaction-signal keywords in titles and produces
    low-confidence claims so the pipeline is always runnable.

    For higher-quality extraction, use medgemma_extract_claims() below.

    Claims require at least one citation — no uncited claims are produced.
    """
    if not summaries:
        return []

    signal_refs: List[EvidenceRef] = []
    for ref in summaries.values():
        title = ref.get("title", "")
        if _SIGNAL_RE.search(title):
            signal_refs.append(ref)

    if not signal_refs:
        return []

    # Build a single aggregated claim from all signalling papers
    titles_snippet = "; ".join(r["title"][:80] for r in signal_refs[:3])
    claim: RagInteractionClaim = {
        "ingredient_1_inn": inn_a,
        "ingredient_2_inn": inn_b,
        "claim": (
            f"Literature signals suggest a possible interaction between {inn_a} and {inn_b}. "
            f"Relevant papers: {titles_snippet}..."
        ),
        "mechanism": None,
        "severity_or_risk": None,
        "claim_confidence": "low",
        "citations": signal_refs,
    }
    return [claim]


def medgemma_extract_claims(
    inn_a: str,
    inn_b: str,
    summaries: Dict[str, EvidenceRef],
    max_new_tokens: int = 512,
) -> List[RagInteractionClaim]:
    """
    MedGemma-powered interaction claim extraction from PubMed evidence.

    Uses the structured output engine to extract structured claims from
    paper titles and available context.

    Falls back to rule_based_extract_claims() if MedGemma is not available.
    Claims require at least one citation — no uncited claims are produced.
    """
    if not summaries:
        return []

    # Build evidence text
    evidence_text = "\n".join(
        f"PMID {ref['pmid']} ({ref.get('year','?')}): {ref['title']}"
        for ref in list(summaries.values())[:8]
    )

    context = (
        f"Drug pair: {inn_a} and {inn_b}\n\n"
        f"PubMed abstracts/titles retrieved:\n{evidence_text}\n\n"
        f"Extract any drug-drug interaction claims for this pair from the above evidence. "
        f"If no interaction is documented, return an empty claims list."
    )

    try:
        from src.models.medgemma.inference import _run_text_inference

        system = (
            "You are a pharmacology AI. Extract drug-drug interaction claims from PubMed evidence. "
            "Rules: (1) Only use claims from the provided evidence. "
            "(2) Each claim must cite at least one PMID from the evidence. "
            "(3) State mechanism if identifiable. "
            "(4) Set claim_confidence: high (RCT/systematic review), medium (observational), "
            "low (case report/single study). "
            "(5) Output JSON only: {\"claims\": [{\"claim\": str, \"mechanism\": str|null, "
            "\"severity_or_risk\": str|null, \"claim_confidence\": str, \"pmids\": [str]}]}"
        )

        messages = [
            {"role": "system", "content": [{"type": "text", "text": system}]},
            {"role": "user", "content": [{"type": "text", "text": context}]},
        ]

        raw = _run_text_inference(messages, max_new_tokens=max_new_tokens, do_sample=False)

        import json
        import re as _re
        # Extract JSON
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        if not m:
            return rule_based_extract_claims(inn_a, inn_b, summaries)

        parsed = json.loads(m.group())
        claims_raw = parsed.get("claims", [])

        results: List[RagInteractionClaim] = []
        for c in claims_raw:
            pmids_used = c.get("pmids", [])
            cited_refs = [summaries[p] for p in pmids_used if p in summaries]
            if not cited_refs:
                continue  # no citation — skip (policy: no uncited claims)
            results.append({
                "ingredient_1_inn": inn_a,
                "ingredient_2_inn": inn_b,
                "claim": c.get("claim", ""),
                "mechanism": c.get("mechanism"),
                "severity_or_risk": c.get("severity_or_risk"),
                "claim_confidence": c.get("claim_confidence", "low"),
                "citations": cited_refs,
            })
        return results

    except Exception as exc:
        logger.warning(
            "medgemma_extract_claims failed for (%s, %s): %s — falling back to rule-based",
            inn_a, inn_b, exc,
        )
        return rule_based_extract_claims(inn_a, inn_b, summaries)
