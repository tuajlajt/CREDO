"""
Symptom → side-effect fuzzy matcher.

Matches patient-reported symptoms from a clinical transcript to known
drug side effects retrieved from openFDA or other providers.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import List, Optional, TypedDict

from src.pharmacology.side_effects_openfda import AggregatedEffect

# Simple synonym dictionary for common clinical/lay term mappings
# Key = patient/lay term, Value = canonical medical term
SYNONYMS: dict[str, str] = {
    "heart racing": "palpitations",
    "fast heartbeat": "palpitations",
    "racing heart": "palpitations",
    "heart pounding": "palpitations",
    "can't sleep": "insomnia",
    "trouble sleeping": "insomnia",
    "difficulty sleeping": "insomnia",
    "tired": "fatigue",
    "exhausted": "fatigue",
    "weak": "weakness",
    "dizzy": "dizziness",
    "light-headed": "dizziness",
    "lightheaded": "dizziness",
    "sick to stomach": "nausea",
    "upset stomach": "nausea",
    "stomach pain": "abdominal pain",
    "belly pain": "abdominal pain",
    "throwing up": "vomiting",
    "being sick": "vomiting",
    "runs": "diarrhoea",
    "loose stool": "diarrhoea",
    "diarrhea": "diarrhoea",
    "constipated": "constipation",
    "dry mouth": "xerostomia",
    "blurry vision": "blurred vision",
    "blurred": "blurred vision",
    "shortness of breath": "dyspnoea",
    "short of breath": "dyspnoea",
    "breathless": "dyspnoea",
    "chest tightness": "chest pain",
    "itching": "pruritus",
    "itchy": "pruritus",
    "rash": "skin rash",
    "hives": "urticaria",
    "swelling": "oedema",
    "swollen": "oedema",
    "weight gain": "increased weight",
    "putting on weight": "increased weight",
    "losing weight": "decreased weight",
    "frequent urination": "polyuria",
    "urinating a lot": "polyuria",
    "thirsty": "polydipsia",
    "very thirsty": "polydipsia",
    "tremor": "trembling",
    "shaking": "trembling",
    "muscle cramps": "muscle cramp",
    "aching muscles": "myalgia",
    "muscle pain": "myalgia",
    "joint pain": "arthralgia",
    "achy joints": "arthralgia",
    "hair loss": "alopecia",
    "losing hair": "alopecia",
    "memory problems": "memory impairment",
    "forgetful": "memory impairment",
    "confused": "confusion",
    "anxiety": "anxiety",
    "anxious": "anxiety",
    "depressed": "depression",
    "feeling low": "depression",
}


class SymptomMatch(TypedDict):
    symptom: str               # as reported by patient
    matched_effect: str        # matched side effect name
    similarity: float          # 0.0–1.0
    contributors: List[str]    # INNs that can cause this effect
    combined_probability: Optional[float]
    max_severity: Optional[str]


def match_symptoms_to_effects(
    symptoms: List[str],
    aggregated_effects: List[AggregatedEffect],
    *,
    threshold: float = 0.78,
) -> List[SymptomMatch]:
    """
    Match patient-reported symptoms to aggregated drug side effects.

    Uses fuzzy string matching (SequenceMatcher) with a synonym dictionary
    to bridge clinical/lay terms to medical terminology.

    Args:
        symptoms:           Patient symptoms from transcript (can be lay terms).
        aggregated_effects: Output from aggregate_side_effects().
        threshold:          Minimum similarity score to report a match (0.0–1.0).
                            0.78 provides good recall; raise to 0.85 for precision.

    Returns:
        List of SymptomMatch dicts, sorted by similarity descending.
        A symptom can match at most one effect (best match only).
    """
    if not symptoms or not aggregated_effects:
        return []

    # Precompute normalised effect names
    norm_effects = [
        (eff, _norm(eff["effect"]))
        for eff in aggregated_effects
    ]

    out: List[SymptomMatch] = []

    for raw_symptom in symptoms:
        if not raw_symptom or not raw_symptom.strip():
            continue

        # Normalise: apply synonym dictionary, then string norm
        canonical = SYNONYMS.get(raw_symptom.strip().lower(), raw_symptom)
        s_norm = _norm(canonical)

        best_eff = None
        best_score = 0.0

        for eff, eff_norm in norm_effects:
            # Direct substring bonus
            if s_norm in eff_norm or eff_norm in s_norm:
                score = 1.0
            else:
                score = SequenceMatcher(None, s_norm, eff_norm).ratio()

            if score > best_score:
                best_score = score
                best_eff = eff

        if best_eff is not None and best_score >= threshold:
            out.append({
                "symptom": raw_symptom,
                "matched_effect": best_eff["effect"],
                "similarity": round(float(best_score), 3),
                "contributors": best_eff["contributors"],
                "combined_probability": best_eff.get("combined_probability"),
                "max_severity": best_eff.get("max_severity"),
            })

    return sorted(out, key=lambda x: -x["similarity"])


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())
