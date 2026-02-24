"""
CLI entry point for the DDI safety pipeline.

Usage:
    python -m src.pharmacology.main "aspirin" "warfarin" "ibuprofen"
    python -m src.pharmacology.main --symptoms "bleeding,bruising" aspirin warfarin
"""
from __future__ import annotations

import argparse
import json
import sys

from src.pharmacology.config import load_config
from src.pharmacology.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DDI safety pipeline — check interactions among a list of drugs.",
    )
    parser.add_argument(
        "drugs",
        nargs="+",
        help="Drug names or INNs to check (brand names resolved automatically).",
    )
    parser.add_argument(
        "--symptoms",
        default="",
        help="Comma-separated patient symptoms to match against side effects.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to pharmacology.yaml config file (optional).",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    symptoms = [s.strip() for s in args.symptoms.split(",") if s.strip()]

    report = run_pipeline(cfg, medicines_or_inns=args.drugs, patient_symptoms=symptoms)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
