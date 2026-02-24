# CREDO — Clinical Reasoning Ecosystem for Diagnostic Oversight

A clinical AI application using Google's Health AI Developer Foundations (HAI-DEF) model suite.
Designed around the architecture in `docs/solution_architecture.html`: a virtual medical board
where specialist agents study a patient's complete health profile and deliver unified documentation
with full chain-of-thought audit trails.

> **Clinical Safety Notice**: All AI outputs carry `requires_review = True` and a mandatory
> clinician disclaimer. This software is a decision support tool only. No output should be
> acted upon without review by a qualified healthcare professional.

---

## Architecture vs Implementation Status

The `docs/solution_architecture.html` defines 7 stages. Current implementation coverage:

| Stage | Architecture | Status |
|---|---|---|
| S01 EHR data | FHIR/HL7 full patient history | SQLite (10 synthetic patients), full visit/meds/vitals/labs/docs |
| S01 Voice | MedASR, speaker diarization | MedASR working; diarization not implemented |
| S01 Imaging | DICOM/PNG, prior comparison | Basic file upload; DICOM loader stub |
| S01 Labs/Vitals | FHIR observations, trends | SQLite; no FHIR import |
| S02 Image encoding | MedSigLIP 400M, all modalities | **Implemented** — embeddings, zero-shot, progression drift; not yet wired into clinical pipeline |
| S03 Attending + routing | MedGemma 27B, full EHR context | **Working** — GPAgent (4B), board routing, full EHR context |
| S04 Specialist board | Radiologist, Derm, Cardio, Pulm, Endo | **Working** — all 5 agents, text + image |
| S04 Parallel board | Simultaneous dispatch | Sequential (no parallel execution yet) |
| S04 Medication checker | MedGemma 27B + RAG | **Working** — openFDA side effects + fuzzy symptom matching |
| S04 DDI engine | Rule engine + database | **Working** — openFDA label-based (RxNav DDI discontinued Jan 2024) + RxNorm + PubMed RAG |
| S05 Board synthesis | MedGemma 27B, conflict resolution | **Working** — SynthesisAgent (4B), SOAP/ICD/orders, CoT log |
| S05 CPT codes | With justifications | Not implemented |
| S05 Physician review/edit | All fields editable | **Working** — full edit before DB save |
| S06 Post-Rx safety loop | Auto DDI check on new Rx | Not implemented |
| S07 SOAP + ICD-10 | Final structured output | **Working** |
| S07 Progression report | MedSigLIP visual drift | MedSigLIP ready; not connected to pipeline output |
| S07 EHR write-back | FHIR/HL7 | SQLite only |

**Model note**: Architecture specifies MedGemma 27B for attending and synthesis agents.
Current implementation uses MedGemma 1.5 4B (practical GPU constraint — 4B fits on ~8 GB VRAM).

---

## What Is Running Today

### CREDO EHR — ClinDoc (`src/ui/app.jsx`)

Full React EHR application backed by a synthetic SQLite database (10 patients):

- Patient worklist + search
- Visit history with diagnoses and prescriptions
- Medications, Vitals (weight/BP/HR/SpO₂ trends), Labs & Imaging, Patient Background tabs
- **New Visit Log** with multi-agent AI dictation (see pipeline below)

### Multi-Agent Clinical Reasoning Pipeline

```
Doctor records audio (or types a transcript)
  ↓
POST /clinical/visit/{patient_id}
  ├── Step 1: MedASR → transcript
  ├── Step 2: Load EHR context (profile + vitals + meds + visits)
  ├── Step 3: GPAgent → GPAssessment + BoardRoutingDecision
  │           (chain-of-thought, SOAP draft, ICD candidates, board routing flags)
  ├── Step 4: Orchestrator → specialist agents (as flagged by GPAgent)
  │           ├── RadiologistAgent   (if consult_radiologist)
  │           ├── CardiologistAgent  (if consult_cardiologist)
  │           ├── DermatologistAgent (if consult_dermatologist)
  │           ├── PulmonologistAgent (if consult_pulmonologist)
  │           ├── EndocrinologistAgent (if consult_endocrinologist)
  │           └── PharmacologyAgent  (if consult_pharmacology + drugs present)
  │               ├── RxNorm INN resolution
  │               ├── DDI check (openFDA labels)
  │               ├── PubMed RAG evidence
  │               ├── openFDA side effects
  │               └── Symptom-medication correlation
  └── Step 5: SynthesisAgent → VisitSynthesis
              (final SOAP, ICD-10 codes, recommended orders, key findings)
  ↓
ClinicalVisitResult JSON (requires_review=True always)
  ↓
Browser: auto-populates New Visit form (reason, notes, diagnoses, orders)
         + collapsible AI Reasoning panel (CoT per agent)
  ↓
Doctor reviews + edits + adds prescriptions
  ↓
POST /ehr/patients/{id}/visits → saved to DB
```

### DDI Safety Pipeline (standalone, `src/pharmacology/`)

Runs as part of the clinical pipeline or independently:

- RxNorm INN resolution (brand name → generic)
- Drug interaction check via FDA drug labels (openFDA) — RxNav DDI API discontinued Jan 2024
- PubMed literature evidence (rule-based claim extraction)
- Side effect aggregation from openFDA
- Symptom-medication fuzzy matching

### Transcription Pipeline (legacy single-pass)

```
Clinical audio
  → MedASR (google/medasr)
  → MedGemma 1.5 4B (google/medgemma-1.5-4b-it)
  → TranscriptionResult (SOAP + ICD codes, requires_review=True)
```

### MedSigLIP Image Encoder (`src/models/medsiglip/embeddings.py`)

Fully implemented standalone:
- Image embeddings (N × 768 vectors)
- Zero-shot classification (CLIP-style similarity scoring)
- Pairwise similarity between current and prior images
- Progression drift score for longitudinal series
- Not yet wired into the clinical pipeline

---

## Quick Start

### 1. Python environment

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate        # macOS / Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt

# MedASR requires a specific transformers commit
# (transformers ≥5.2 has a LasrFeatureExtractor arity bug)
pip install git+https://github.com/huggingface/transformers.git@65dc261512cbdb1ee72b88ae5b222f2605aad8e5
```

### 3. Seed the demo database

```bash
python scripts/seed_db.py
```

### 4. Download model weights (for AI features)

```bash
export HUGGINGFACE_TOKEN=hf_...

TIER=core  bash scripts/download_models.sh   # MedGemma 1.5 4B  (~8 GB)
TIER=audio bash scripts/download_models.sh   # MedASR            (~1 GB)
```

You must accept HAI-DEF terms on HuggingFace for each model before downloading.

### 5. Start the API

```bash
MODEL_WEIGHTS_PATH=./models uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Navigate to **http://localhost:8000** for the EHR UI.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Transcription UI |
| `GET` | `/health` | Service health |
| `POST` | **`/clinical/visit/{patient_id}`** | **Multi-agent pipeline: audio/text → ClinicalVisitResult** |
| `POST` | `/transcribe/audio` | Single-pass: audio → SOAP note + ICD codes |
| `POST` | `/transcribe/text` | Single-pass: transcript → SOAP note + ICD codes |
| `GET` | `/transcribe/health` | Check model weights present |
| `GET` | `/ehr/worklist` | Patient worklist for demo clinician |
| `GET` | `/ehr/patients/search?name=…` | Patient search |
| `GET` | `/ehr/patients/{id}/profile` | Patient header card |
| `GET` | `/ehr/patients/{id}/visits` | Visit history |
| `GET` | `/ehr/patients/{id}/medications` | Prescription history |
| `GET` | `/ehr/patients/{id}/vitals` | Weight, BP, HR, SpO₂ history |
| `GET` | `/ehr/patients/{id}/documents` | Labs, imaging, documents |
| `GET` | `/ehr/patients/{id}/background` | Lifestyle + family history |
| `POST` | `/ehr/patients/{id}/visits` | Save reviewed visit with vitals/diagnoses/Rx |
| `POST` | `/radiology/analyze` | CXR image → radiology report (stub) |
| `POST` | `/drug-check/` | Medication list → full DDI + side effects report |
| `GET` | `/docs` | Swagger UI |

---

## HAI-DEF Models

| Model | HuggingFace ID | Status |
|---|---|---|
| MedGemma 1.5 4B | `google/medgemma-1.5-4b-it` | **Working** — all agents use this |
| MedASR | `google/medasr` | **Working** — lasr_ctc speech recognition |
| MedSigLIP | `google/medsiglip-448` | **Implemented** — embeddings, zero-shot, drift |
| CXR Foundation | `google/cxr-foundation` | Scaffolded |
| Derm Foundation | `google/derm-foundation` | Scaffolded |
| Path Foundation | `google/path-foundation` | Scaffolded |
| HeAR (PyTorch) | `google/hear-pytorch` | Scaffolded |
| CT Foundation | Vertex AI only | N/A — not on HuggingFace |
| TxGemma 2B | `google/txgemma-2b-predict` | Scaffolded |
| TxGemma 9B | `google/txgemma-9b-predict` | Scaffolded |

---

## Project Structure

```
MedGemmaApp/
│
├── src/
│   ├── models/
│   │   ├── medgemma/
│   │   │   ├── inference.py          # MedGemma 1.5 4B: text + image inference
│   │   │   └── structured_output.py  # Generic Pydantic → JSON extraction engine
│   │   ├── medasr/
│   │   │   ├── inference.py          # MedASR: speech → transcript (lasr_ctc)
│   │   │   └── preprocessing.py      # Audio: load, resample, chunk, postprocess
│   │   └── medsiglip/
│   │       └── embeddings.py         # MedSigLIP: embeddings, zero-shot, progression
│   │
│   ├── agents/
│   │   ├── gp_agent.py               # GPAgent: transcript + EHR → SOAP + routing
│   │   ├── gp_schema.py              # GPAssessment, BoardRoutingDecision schemas
│   │   ├── orchestrator.py           # run_specialists(): route to board agents
│   │   ├── synthesis_agent.py        # SynthesisAgent: collate reports → VisitSynthesis
│   │   ├── visit_synthesis_schema.py # VisitSynthesis, SynthesisOrder, CotEntry
│   │   ├── radiologist_agent.py      # Radiology: text + image
│   │   ├── cardiologist_agent.py     # Cardiology
│   │   ├── dermatologist_agent.py    # Dermatology: text + image
│   │   ├── pulmonologist_agent.py    # Pulmonology
│   │   ├── endocrinologist_agent.py  # Endocrinology
│   │   └── pharmacology_agent.py     # DDI + side effects + MedGemma synthesis
│   │
│   ├── pipelines/
│   │   ├── clinical_reasoning.py     # run_clinical_reasoning(): full 5-step pipeline
│   │   ├── transcription.py          # Single-pass: audio/text → TranscriptionResult
│   │   └── drug_check_pipeline.py    # DDI: INN → interactions → side effects → symptoms
│   │
│   ├── pharmacology/
│   │   ├── interactions.py           # DDI via openFDA labels (RxNav DDI discontinued)
│   │   ├── rxnav_client.py           # RxNorm: name → INN resolution (still working)
│   │   ├── normalization.py          # medicine_to_inns()
│   │   ├── pubmed_rag.py             # PubMed search + rule-based claim extraction
│   │   ├── side_effects_openfda.py   # openFDA adverse reaction retrieval
│   │   └── symptom_matcher.py        # Fuzzy symptom-to-side-effect matching
│   │
│   ├── api/
│   │   ├── main.py                   # FastAPI app
│   │   ├── clinical_reasoning.py     # POST /clinical/visit/{id}
│   │   ├── ehr.py                    # EHR CRUD endpoints
│   │   ├── transcription.py          # POST /transcribe/audio, /text
│   │   ├── drugs.py                  # POST /drug-check/
│   │   ├── radiology.py              # POST /radiology/analyze (stub)
│   │   └── health.py                 # GET /health
│   │
│   ├── data/
│   │   ├── db.py                     # SQLite queries (profile, vitals, meds, visits)
│   │   └── schema/                   # ehr.yaml JSON Schema + EHR.dbml
│   │
│   ├── nlp/
│   │   └── icd_mapper.py             # ICD-10 code parsing + validation
│   │
│   ├── ui/
│   │   ├── app.jsx                   # CREDO EHR React application
│   │   ├── main.jsx                  # Vite entry point
│   │   └── constants.js              # UI constants (lab panels, imaging modalities, CPT lookup)
│   │
│   ├── config/loader.py              # YAML config loader
│   └── utils/
│       ├── audit.py                  # HIPAA audit logging
│       └── logging.py
│
├── tests/
│   ├── conftest.py
│   ├── test_components.py            # Component tests: MedASR, MedGemma, DDI, agents, pipeline
│   └── pytest.ini                   # Markers: requires_weights, requires_network, slow
│
├── data/
│   └── synthetic/
│       ├── patients/                 # P001–P010 JSON patient records
│       └── clindoc_demo.db           # SQLite demo DB (committed — synthetic only)
│
├── configs/
│   ├── default.yaml
│   ├── pharmacology.yaml
│   ├── database.yaml
│   └── agents/*.yaml
│
├── scripts/
│   ├── download_models.sh
│   └── seed_db.py
│
├── docker/                           # Dockerfile.api, .worker, .dev, nginx/
├── docs/
│   ├── solution_architecture.html    # Full 7-stage architecture diagram
│   ├── SETUP.md
│   └── decisions.md
└── requirements.txt
```

---

## Data Architecture

```
data/raw/          ← PHI present — NEVER mounted into containers
data/deidentified/ ← Safe for model input
data/synthetic/    ← Test fixtures + demo DB (no real patient data)
```

Every inference is logged to `logs/audit.log` with: timestamp, model versions,
input hash (never content), agent name, and `requires_review: true`.

---

## Layer Dependencies

```
data → preprocessing → models → agents → pipelines → api
```

Dependencies must only flow in this direction. Violations are a code review failure.

---

## Key Technical Notes

### MedASR
- Architecture: `lasr_ctc` (Conformer + CTC head)
- Requires `transformers 5.0.0.dev0` from commit `65dc261512cbdb1ee72b88ae5b222f2605aad8e5`
- transformers ≥5.2 has a `LasrFeatureExtractor._torch_extract_fbank_features` arity bug
- Audio chunked into non-overlapping 30s segments (overlapping stride duplicates words with CTC)
- Spoken tokens (`{period}`, `{comma}`, `{colon}` etc.) normalised to real punctuation

### MedGemma 1.5 4B
- Architecture: `Gemma3ForConditionalGeneration` (multimodal, text + image)
- `apply_chat_template` requires all message content as lists: `[{"type":"text","text":"..."}]`
- Prompt pattern: field instructions in plain text ABOVE a JSON skeleton; empty values in the JSON
- Runs `device_map="auto"` with `torch_dtype="auto"` (bfloat16 on GPU, float32 on CPU)

### DDI Engine
- **RxNav Drug Interaction API discontinued January 2, 2024** — `/REST/interaction/list.json` returns 404
- Interaction check now uses openFDA drug label `drug_interactions` section
- RxNorm name resolution (`/REST/approximateTerm.json`, `/REST/rxcui/*/related.json`) still working
- Severity inferred from FDA label text: keywords → `critical` / `high` / `med` / `low`

### Structured Output
- `src/models/medgemma/structured_output.py`: generic Pydantic model → JSON extraction
- All agents (GP, specialists, synthesis) use this as their LLM interface
- Pattern: build field-description prompt from Pydantic schema + empty JSON skeleton → model fills it

---

## Testing

```bash
# Pure unit tests (no network, no weights) — runs in <10s
pytest tests/test_components.py -k "not (requires_weights or requires_network)"

# Network tests (DDI, openFDA, PubMed) — no model weights needed
pytest tests/test_components.py -m "requires_network and not requires_weights"

# Full suite including model inference (requires weights + network)
pytest tests/test_components.py -m "requires_weights or requires_network"
```

Test markers:
- `requires_weights` — skipped if MedGemma/MedASR weights not present
- `requires_network` — skipped if internet/RxNav unreachable
- `slow` — full model inference tests (>30s), excluded by default

---

## Requirements

- Python 3.11+
- NVIDIA GPU recommended (8 GB+ VRAM for 4B models)
- CUDA 12.1+ (CPU inference works but is slow)
- HuggingFace account with HAI-DEF model access (accept terms per model)

```
transformers==5.0.0.dev0   # specific commit — see install note above
torch>=2.2.0
accelerate>=0.27.0
librosa>=0.10.0
soundfile>=0.12.0
pillow>=10.0.0
fastapi>=0.110.0
uvicorn>=0.27.0
python-multipart>=0.0.9
requests>=2.31.0
pydantic>=2.0.0
```

---

## License and Model Terms

Template code: MIT license.

HAI-DEF model weights are subject to Google's terms:
- [Health AI Developer Foundations Terms](https://developers.google.com/health-ai-developer-foundations/terms)
- Models are for research and application development only
- Not approved for direct clinical deployment without validation and regulatory clearance
- Review individual model cards on HuggingFace for specific restrictions

---

## Disclaimer

This software is a development template and clinical decision support aid. It is not a
medical device and has not been evaluated by the FDA or any regulatory authority. Do not
use in clinical practice without appropriate validation, regulatory clearance, and
institutional approval.
