# Setup Guide

This guide covers everything you need to get CREDO running locally — from a fresh clone
to a working EHR demo with multi-agent clinical reasoning.

---

## Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.11 |
| CUDA GPU | None (CPU works) | RTX 3090 / A100 (8 GB+ VRAM) |
| RAM | 16 GB | 32 GB |
| Disk | 10 GB (demo only) | 80 GB (all models) |
| OS | Windows 10 / Ubuntu 22.04 / macOS 13 | Ubuntu 22.04 |

> **GPU note**: MedGemma 4B requires ~8 GB VRAM in bfloat16. MedASR needs ~2 GB.
> CPU-only mode works but inference is significantly slower (minutes per transcription).

---

## 1. Clone the repository

```bash
git clone <repo-url>
cd MedGemmaApp
```

---

## 2. Python environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

---

## 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### Special dependency: transformers (MedASR)

MedASR requires `transformers 5.0.0.dev0` from a specific commit. The published 5.2.x has
a `LasrFeatureExtractor` arity bug that prevents MedASR from loading.

```bash
pip install git+https://github.com/huggingface/transformers.git@65dc261512cbdb1ee72b88ae5b222f2605aad8e5
```

> If you only need the EHR demo (no AI transcription), you can skip this step.

---

## 4. Environment variables

Copy the template and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Required for downloading HAI-DEF model weights from HuggingFace
HUGGINGFACE_TOKEN=hf_...

# Optional: override default SQLite database path
# CREDO_DB_PATH=data/synthetic/credo_demo.db

# Optional: NCBI API key for higher PubMed rate limits (3/s → 10/s)
# NCBI_API_KEY=...

# Optional: override pharmacology pipeline config
# PHARMACOLOGY_CONFIG=configs/pharmacology.yaml
```

---

## 5. Seed the demo database

The EHR demo uses a SQLite database with 10 fully synthetic patients. Generate it with:

```bash
python scripts/seed_db.py
```

This creates `data/synthetic/credo_demo.db`.

To re-seed a **running server** without restarting (append-only mode):

```bash
python scripts/seed_db.py --append
```

> The database file is committed to git (it is synthetic, not PHI). If the file is missing,
> the API returns HTTP 503 with instructions to run `seed_db.py`.

---

## 6. Download model weights (for AI features)

Model weights are **not in the repository** — they must be downloaded from HuggingFace.
You must accept the HAI-DEF terms for each model on HuggingFace before downloading.

### Accept model terms (one-time per model)

Visit each model page on HuggingFace and click "Accept":
- https://huggingface.co/google/medgemma-1.5-4b-it
- https://huggingface.co/google/medasr

### Download via script (recommended)

```bash
export HUGGINGFACE_TOKEN=hf_...

# Core (MedGemma 1.5 4B — required for transcription + EHR dictation)
TIER=core bash scripts/download_models.sh

# Audio (MedASR — required for voice recording)
TIER=audio bash scripts/download_models.sh

# All models
bash scripts/download_models.sh
```

### Download manually

```bash
pip install huggingface_hub

python - <<'EOF'
from huggingface_hub import snapshot_download
import os
token = os.environ["HUGGINGFACE_TOKEN"]

# MedGemma 1.5 4B
snapshot_download(
    "google/medgemma-1.5-4b-it",
    local_dir="models/google--medgemma-1.5-4b-it",
    token=token,
)

# MedASR
snapshot_download(
    "google/medasr",
    local_dir="models/google--medasr",
    token=token,
)
EOF
```

Models are stored under `models/` (gitignored). The server auto-detects them via the
`MODEL_WEIGHTS_PATH` environment variable (default: `./models`).

---

## 7. Run the server

### Option A: Python directly

```bash
MODEL_WEIGHTS_PATH=./models python main.py
```

### Option B: uvicorn

```bash
MODEL_WEIGHTS_PATH=./models uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option C: Docker Compose (recommended for production)

```bash
# Development
docker-compose up

# Production
docker-compose -f docker-compose.prod.yml up -d
```

The Docker images are defined in `docker/`. Set secrets in `.env` before running Docker.

---

## 8. Open the application

| URL | What you get |
|---|---|
| http://localhost:8000 | CREDO EHR (after Vite build) |
| http://localhost:8000/transcribe | Transcription UI (static HTML, no build needed) |
| http://localhost:8000/docs | Swagger API documentation |
| http://localhost:8000/health | Health check |

> **Note**: The EHR React app (`src/ui/app.jsx`) requires a Vite build step to serve as a
> static file. See [Building the EHR UI](#building-the-ehr-ui-optional) below.
> Without the build, all API endpoints still work — only the browser UI is unavailable.

---

## 9. Verify the setup

### Health check

```bash
curl http://localhost:8000/health
# → {"status": "ok", ...}

curl http://localhost:8000/transcribe/health
# → {"status": "ok", "model": "google/medgemma-1.5-4b-it", ...}
```

### EHR data

```bash
curl http://localhost:8000/ehr/worklist
# → [{patient_id: "P001", full_name: "Alice Johnson", ...}, ...]

curl "http://localhost:8000/ehr/patients/P001/profile"
# → {patient_id: "P001", given_names: "Alice", ...}
```

### Transcription (text mode — no audio file needed)

```bash
curl -X POST http://localhost:8000/transcribe/text \
  -F "transcript=45-year-old male presenting with chest pain radiating to left arm.
      BP 145/90. Impression: unstable angina. Plan: admit for monitoring,
      start aspirin and heparin." \
  -F "note_type=soap"
```

### Multi-agent clinical reasoning

Submit a transcript and patient ID to run the full pipeline (MedASR → GPAgent → Specialists → SynthesisAgent):

```bash
# Text-based (no audio required)
curl -X POST http://localhost:8000/clinical/visit/P001 \
  -F "transcript=Patient presents with acute shortness of breath and bilateral leg swelling.
      Currently on warfarin and furosemide. SpO2 88% on room air."

# Audio file
curl -X POST http://localhost:8000/clinical/visit/P001 \
  -F "file=@visit_recording.wav"
```

Response includes `reason_for_visit`, `soap`, `diagnoses`, `recommended_orders`, and
`cot_log` (chain-of-thought from every agent that ran).

---

## Building the EHR UI (optional)

The EHR frontend (`src/ui/app.jsx`) is a React + Vite application. To build it:

```bash
# Install Node dependencies (one-time)
cd src/ui
npm install

# Build for production
npm run build
# Output: src/ui/static/dist/

# Development server (hot reload, proxies /ehr/* to FastAPI at :8000)
npm run dev
```

After building, the FastAPI server automatically serves `src/ui/static/dist/index.html`.

### package.json scaffold

If `package.json` is not present in `src/ui/`, create it:

```json
{
  "name": "credo-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "lucide-react": "^0.469.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "tailwindcss": "^3.4.17",
    "vite": "^6.0.5"
  }
}
```

---

## DDI Pipeline (standalone)

The drug-drug interaction pipeline can be run independently:

```bash
python -m src.pharmacology.main "aspirin" "warfarin" "ibuprofen" \
  --symptoms "bleeding,bruising,dizziness"
```

This checks pairwise interactions, retrieves PubMed evidence, and matches symptoms to
known side effects. No model weights needed — it uses public APIs only.

**API note**: The RxNav Drug-Drug Interaction API was **discontinued on January 2, 2024**
(`/REST/interaction/*.json` returns 404). Pairwise interaction text is now sourced from
FDA drug labels via [openFDA](https://api.fda.gov/drug/label.json). RxNorm name resolution
(`/REST/approximateTerm.json`) is unaffected and still in use.

Configuration is in `configs/pharmacology.yaml`.

---

## Configuration reference

| File | Purpose |
|---|---|
| `configs/default.yaml` | Global defaults: model IDs, inference parameters |
| `configs/models/medgemma.yaml` | MedGemma model config |
| `configs/models/medasr.yaml` | MedASR model config |
| `configs/pharmacology.yaml` | DDI pipeline: RxNav, PubMed, symptom matching |
| `configs/database.yaml` | SQLite path and EHR demo settings |
| `configs/agents/*.yaml` | Per-agent configuration |
| `.env` | Secrets and path overrides (gitignored) |

All configuration values flow from YAML files. Nothing important is hardcoded in `src/`.

---

## Troubleshooting

### `Demo database not found. Run: python scripts/seed_db.py`

The SQLite database was not created. Run:
```bash
python scripts/seed_db.py
```

### `NotImplementedError` from radiology endpoints

The radiology pipeline (`src/api/radiology.py`) is scaffolded but not yet wired to a model.
The EHR, transcription, drug-check, and clinical reasoning pipelines are all fully working.

### `LasrFeatureExtractor._torch_extract_fbank_features` error

Wrong version of `transformers`. Install the pinned commit:
```bash
pip install git+https://github.com/huggingface/transformers.git@65dc261512cbdb1ee72b88ae5b222f2605aad8e5
```

### `CUDA out of memory`

- Try `CUDA_VISIBLE_DEVICES=""` to force CPU mode
- Or reduce batch size in `configs/models/medgemma.yaml`
- For 4B model: 8 GB VRAM minimum in bfloat16

### `401 Unauthorized` from HuggingFace download

Your token is missing or the model terms have not been accepted. Go to the model page on
HuggingFace, click "Accept", then re-export `HUGGINGFACE_TOKEN`.

### Windows: `Device or resource busy` when re-seeding DB

The FastAPI server holds an open connection to the SQLite file. Use `--append` to add data
without deleting and recreating the file:
```bash
python scripts/seed_db.py --append
```

---

## Running tests

Tests are organised with markers defined in `pytest.ini`:

| Marker | Description |
|---|---|
| *(no marker)* | Pure unit tests — no network, no model weights |
| `requires_network` | Hits RxNorm, openFDA, PubMed APIs |
| `requires_weights` | Loads MedGemma or MedASR model weights |
| `slow` | Full model inference (>30 s per test) |
| `integration` | End-to-end against live models and APIs |

```bash
# Fast unit tests only (no I/O)
pytest tests/ -v -m "not requires_network and not requires_weights and not slow"

# Network tests (DDI, PubMed) — no GPU required
pytest tests/ -v -m "requires_network and not requires_weights"

# Component tests requiring model weights (GPU recommended)
pytest tests/test_components.py -v -m "requires_weights"

# Full suite (slow — allow 30+ minutes)
pytest tests/ -v

# Single test class
pytest tests/test_components.py::TestDDIRxNav -v
pytest tests/test_components.py::TestOrchestration -v
```

Tests use only synthetic data from `data/synthetic/`. No real patient data is ever used.

---

## Project conventions

- `requires_review=True` is hardcoded on all clinical output dataclasses — never remove it
- PHI is de-identified before any model call; `data/raw/` is never mounted to containers
- Every inference is audit-logged via `src/utils/audit.py`
- All config values live in `configs/` — no hardcoded model IDs, paths, or thresholds in `src/`
- Synthetic data only in tests

See `CLAUDE.md` for the full development conventions guide.
