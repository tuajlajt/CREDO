"""
Clinical named entity recognition (NER).

Extracts: medications, diseases/conditions, procedures, anatomy from clinical text.
Recommended for production: scispaCy with en_core_sci_lg model.

Install:
  pip install scispacy
  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_lg-0.5.4.tar.gz

Owner agent: medical-transcriber-agent
"""
from __future__ import annotations


def load_medical_nlp():
    """Load scispaCy medical NLP model."""
    # TODO: implement — requires scispacy and en_core_sci_lg
    # import spacy
    # return spacy.load("en_core_sci_lg")
    raise NotImplementedError("Install scispacy and en_core_sci_lg to use medical NLP")


def extract_medical_entities(text: str, nlp=None) -> dict:
    """
    Extract medical entities from clinical text.

    Returns dict with keys:
      medications (list[str])
      diseases    (list[str])
      procedures  (list[str])
      anatomy     (list[str])

    Requires scispaCy for full extraction.
    Falls back to empty lists if NLP model not available.
    """
    try:
        if nlp is None:
            nlp = load_medical_nlp()
        doc = nlp(text)
        return {
            "medications": [e.text for e in doc.ents if e.label_ in ["CHEMICAL", "DRUG"]],
            "diseases":    [e.text for e in doc.ents if e.label_ in ["DISEASE", "CONDITION"]],
            "procedures":  [e.text for e in doc.ents if e.label_ == "PROCEDURE"],
            "anatomy":     [e.text for e in doc.ents if e.label_ in ["ORGAN", "ANATOMY"]],
        }
    except NotImplementedError:
        # Graceful fallback — scispaCy not installed
        return {
            "medications": [],
            "diseases": [],
            "procedures": [],
            "anatomy": [],
        }
