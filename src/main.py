"""
src/ package — MedGemma Medical AI source root.

This file is intentionally minimal. The application entry points are:

  API server:  src/api/main.py  (FastAPI app imported by root main.py)
  CLI runner:  root main.py     (uvicorn / argparse entry point)

Package structure:
  src/agents/        — Clinical AI agent classes (GPAgent, RadiologistAgent, …)
  src/models/        — HAI-DEF model wrappers (load, infer, embed)
  src/preprocessing/ — Medical image and audio preprocessing
  src/data/          — DICOM, FHIR, audio loaders + PHI de-identification
  src/pipelines/     — End-to-end clinical inference pipelines
  src/api/           — FastAPI routers and request/response schemas
  src/nlp/           — Clinical NLP (section detection, entity extraction)
  src/config/        — Configuration loader (reads configs/*.yaml)
  src/utils/         — Logging and HIPAA audit utilities
  src/ui/            — React component templates (JSX + CSS design tokens)
"""
