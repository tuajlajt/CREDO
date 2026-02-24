"""
Pharmacology pipeline configuration dataclasses and YAML loader.

Default config file: configs/pharmacology.yaml
Override path via load_config(path="...") or the PHARMACOLOGY_CONFIG env var.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "configs" / "pharmacology.yaml"


@dataclass
class RxNavCfg:
    base_url: str
    timeout_s: int
    polite_delay_s: float
    max_retries: int = 3
    backoff_factor: float = 0.5


@dataclass
class RagCfg:
    pubmed_retmax: int
    ncbi_api_key: Optional[str]


@dataclass
class SymptomsCfg:
    match_threshold: float


@dataclass
class AppConfig:
    rxnav: RxNavCfg
    rag: RagCfg
    symptoms: SymptomsCfg


def load_config(path: Optional[str] = None) -> AppConfig:
    """
    Load pharmacology config from YAML.

    Priority:
        1. Explicit path argument
        2. PHARMACOLOGY_CONFIG environment variable
        3. configs/pharmacology.yaml (project default)
    """
    resolved = (
        Path(path)
        if path
        else Path(os.environ.get("PHARMACOLOGY_CONFIG", str(_DEFAULT_CONFIG)))
    )
    with open(resolved, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    rxnav_raw = raw["rxnav"]
    return AppConfig(
        rxnav=RxNavCfg(
            base_url=rxnav_raw["base_url"],
            timeout_s=rxnav_raw["timeout_s"],
            polite_delay_s=rxnav_raw["polite_delay_s"],
            max_retries=rxnav_raw.get("max_retries", 3),
            backoff_factor=rxnav_raw.get("backoff_factor", 0.5),
        ),
        rag=RagCfg(
            pubmed_retmax=raw["rag"]["pubmed_retmax"],
            ncbi_api_key=raw["rag"].get("ncbi_api_key"),
        ),
        symptoms=SymptomsCfg(
            match_threshold=raw["symptoms"]["match_threshold"],
        ),
    )


def as_dict(cfg: AppConfig) -> Dict[str, Any]:
    return {
        "rxnav": cfg.rxnav.__dict__,
        "rag": cfg.rag.__dict__,
        "symptoms": cfg.symptoms.__dict__,
    }
