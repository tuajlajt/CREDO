"""
MedGemma Medical AI — Application entry point.

Two modes:
  1. API server (uvicorn):
       uvicorn main:app --host 0.0.0.0 --port 8000
       docker-compose up  (recommended)

  2. CLI pipeline (development):
       python main.py --step preprocess
       python main.py --step infer --input data/synthetic/sample.dcm

The `app` variable is the FastAPI ASGI application (for uvicorn/Docker).
"""
from __future__ import annotations

import argparse
import sys

# FastAPI app — imported here so uvicorn can find it as main:app
from src.api.main import app  # noqa: F401  (used by uvicorn)


def cli() -> None:
    """CLI entry point for pipeline development and testing."""
    parser = argparse.ArgumentParser(
        description="MedGemma Medical AI pipeline CLI"
    )
    parser.add_argument(
        "--step",
        choices=["preprocess", "infer", "health"],
        required=True,
        help="Pipeline step to run",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input file path (DICOM, audio, etc.)",
    )
    parser.add_argument(
        "--modality",
        type=str,
        default="CXR",
        choices=["CXR", "CT", "MRI", "DERM", "PATH"],
        help="Imaging modality (for imaging steps)",
    )
    args = parser.parse_args()

    from src.utils.logging import setup_logging
    setup_logging()

    if args.step == "health":
        # Quick health check without starting the full API
        import requests  # noqa
        try:
            r = requests.get("http://localhost:8000/health", timeout=5)
            print(r.json())
        except Exception as e:
            print(f"Health check failed: {e}")
        sys.exit(0)

    elif args.step == "preprocess":
        if not args.input:
            parser.error("--input required for preprocess step")
        print(f"Preprocessing {args.input} (modality: {args.modality})")
        # TODO: call appropriate preprocessing pipeline
        raise NotImplementedError("Preprocessing CLI step not yet implemented")

    elif args.step == "infer":
        if not args.input:
            parser.error("--input required for infer step")
        print(f"Running inference on {args.input}")
        # TODO: call medical-workflow-orchestrator pipeline
        raise NotImplementedError("Inference CLI step not yet implemented")


if __name__ == "__main__":
    # When run directly (python main.py --step ...), use CLI mode
    # When imported (uvicorn main:app), the FastAPI app is used
    cli()
