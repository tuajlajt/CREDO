# Next Session Work Plan — CREDO
Generated: 2026-02-24

## Gap Analysis: Architecture vs. Implementation

The solution architecture (`docs/solution_architecture.html`) defines 7 pipeline stages.
Below is the current implementation status and a priority-ordered work plan for the next session.

---

## Current Implementation Status

### IMPLEMENTED (this session + prior)
| Component | File | Notes |
|---|---|---|
| MedASR pipeline | `src/models/medasr/` | Fully working |
| MedGemma 1.5 inference | `src/models/medgemma/inference.py` | Fully working |
| Structured output engine | `src/models/medgemma/structured_output.py` | Fully working |
| EHR schema + validator | `src/data/ehr_validator.py`, `schema/ehr.yaml` | 10 synthetic patients |
| EHR loader | `src/data/ehr_loader.py` | Working |
| Transcription pipeline | `src/pipelines/transcription.py` | End-to-end working |
| GP agent (Stage 03) | `src/agents/gp_agent.py` + `gp_schema.py` | Uses structured_output |
| Radiologist agent | `src/agents/radiologist_agent.py` + `radiology_schema.py` | Board routing ready |
| Dermatologist agent | `src/agents/dermatologist_agent.py` + `dermatology_schema.py` | ABCDE + atopic march |
| Cardiologist agent | `src/agents/cardiologist_agent.py` + `cardiology_schema.py` | ACS + HF staging |
| Pulmonologist agent | `src/agents/pulmonologist_agent.py` + `pulmonology_schema.py` | GOLD + spirometry |
| Endocrinologist agent | `src/agents/endocrinologist_agent.py` + `endocrinology_schema.py` | Diabetes + thyroid |
| Pharmacology agent | `src/agents/pharmacology_agent.py` + `pharmacology_schema.py` | DDI + synthesis |
| DDI pipeline | `src/pipelines/drug_check_pipeline.py` | RxNav + openFDA + PubMed |
| DDI API | `src/api/drugs.py` | POST /drug-check/ |
| MedSigLIP Stage 02 | `src/models/medsiglip/embeddings.py` | Full encoder with drift |
| Document extractor | `src/data/document_extractor.py` | docling + PyMuPDF fallback |
| UI transcription | `src/ui/static/transcription.html` | Dark SPA served at GET / |
| ICD-10 mapper | `src/nlp/icd_mapper.py` | Parse + validate format |
| FastAPI server | `src/api/main.py` | Port 8000 |

### MISSING — Not Yet Implemented
| Component | Stage | Priority |
|---|---|---|
| **Board synthesis agent** | Stage 05 | CRITICAL |
| **Clinical pipeline orchestrator** | All | CRITICAL |
| **De-identifier (PHI removal)** | Data layer | CRITICAL |
| Radiology pipeline + API | Stage 04 | HIGH |
| Post-prescription DDI endpoint | Stage 06 | HIGH |
| Confidence gating + escalation | Stage 06 | HIGH |
| Pathologist agent | Stage 04 | MEDIUM |
| CXR Foundation embeddings | Stage 04 | MEDIUM |
| Derm Foundation embeddings | Stage 04 | MEDIUM |
| Path Foundation embeddings | Stage 04 | MEDIUM |
| TxGemma inference | Stage 04 | MEDIUM |
| DICOM loader | Stage 01 | MEDIUM |
| FHIR bidirectional loader | Stage 01/07 | MEDIUM |
| CXR preprocessing | Stage 01 | MEDIUM |
| CT preprocessing | Stage 01 | MEDIUM |
| Pathology preprocessing | Stage 01 | MEDIUM |
| HeAR audio embeddings | Stage 04 | LOW |
| Full React UI (JSX wiring) | Stage 07 | LOW |
| CPT code generation | Stage 07 | LOW |
| EHR write-back (FHIR) | Stage 07 | LOW |

---

## Next Session: Priority-Ordered Task List

### TASK 1 — De-identifier (PHI removal) [CRITICAL]
**File:** `src/data/deidentifier.py`
**Why first:** Non-negotiable per CLAUDE.md. All model calls must process de-identified data.
Current file has 2 stub functions that raise NotImplementedError.

**Implementation instructions:**
1. Read the current stub file to see the expected function signatures
2. Implement `deidentify_text(text: str) -> str` using Microsoft Presidio or spaCy NER:
   - Install: `pip install presidio-analyzer presidio-anonymizer`
   - Replace names, dates, MRNs, phone numbers, addresses, emails with `[REDACTED]` tokens
   - Keep clinical terms intact — only strip patient identifiers
   - Fallback: regex-based approach if Presidio not available (patterns for NHS/MRN numbers, dates, postcodes)
3. Implement `deidentify_image(image: PIL.Image.Image) -> PIL.Image.Image`:
   - Blur/black-out DICOM overlay text regions (typically top/bottom 10% of image)
   - For now: return image unchanged with a `logger.warning` that manual review is required
   - Note: full DICOM PHI removal requires pydicom tag stripping — implement in dicom_loader.py instead
4. Add `deidentify_document(text: str) -> str` as alias for `deidentify_text`
5. Hardcode `requires_review = True` in audit log entry — PHI removal is never 100% guaranteed

**Key pattern:**
```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()
results = analyzer.analyze(text=text, language="en")
anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
return anonymized.text
```

---

### TASK 2 — Board Synthesis Agent (Stage 05) [CRITICAL]
**Files to create:**
- `src/agents/synthesis_schema.py`
- `src/agents/synthesis_agent.py`

**Why critical:** Stage 05 is the "chief of staff" that produces the final output — SOAP note, ICD-10/CPT codes, cross-specialty reconciliation, safety dashboard. Without it, the pipeline has no unified output.

**synthesis_schema.py — Pydantic models:**
```python
class ICDCode(BaseModel):
    code: str          # e.g. "E11.9"
    description: str
    confidence: float  # 0.0-1.0
    source_agent: str  # which specialist suggested this

class CPTCode(BaseModel):
    code: str
    description: str
    justification: str

class CrossSpecialtyConflict(BaseModel):
    finding: str
    agent_a: str
    agent_b: str
    resolution: str
    chain_of_thought: str

class SafetyAlert(BaseModel):
    severity: str      # critical | major | moderate | minor
    source: str        # which agent raised this
    description: str
    action_required: str

class DiseaseProgressionSummary(BaseModel):
    condition: str
    trend: str         # improving | stable | worsening | new_finding
    evidence: str
    medsiglip_drift_score: Optional[float]

class SynthesisAssessment(BaseModel):
    chain_of_thought: str
    final_soap: SOAPFields  # reuse from gp_schema
    icd10_codes: List[ICDCode]
    cpt_codes: List[CPTCode]
    safety_alerts: List[SafetyAlert]
    progression_summary: List[DiseaseProgressionSummary]
    cross_specialty_conflicts: List[CrossSpecialtyConflict]
    clinical_recommendations: List[str]
    requires_review: bool = True
    disclaimer: str = ""
```

**synthesis_agent.py — SynthesisAgent class:**
- System prompt: "You are the chief of clinical medicine reviewing all specialist reports. Your role is to synthesize — not repeat — the specialist findings into unified, non-redundant documentation."
- Key synthesis rules:
  - When two specialists agree on a finding: mention once, cite both
  - When two specialists conflict: document both perspectives + reasoning for resolution
  - ICD-10 selection: prefer highest-confidence codes from most relevant specialist
  - CPT codes: based on procedures documented in visit (this visit's encounter)
  - Safety alerts: escalate ALL critical/major flags from pharmacology agent first
- Input: dict containing all specialist assessment dicts from Stage 04
- Build context by calling `_build_synthesis_context(all_reports: dict) -> str`
- Call `structured_output(context, SynthesisAssessment, system_hint=SYSTEM_PROMPT)`
- Log with `audit.log_inference`

---

### TASK 3 — Clinical Pipeline Orchestrator [CRITICAL]
**File:** `src/pipelines/clinical_pipeline.py`

**Why critical:** The `src/api/main.py` currently has no end-to-end clinical pipeline endpoint. There is no way to call a single API with a transcript + EHR and get a full report. This is the central integration piece.

**Instructions:**
1. Create `run_clinical_pipeline(request: ClinicalRequest) -> ClinicalReport` function
2. The pipeline executes the full architecture:

```
Stage 01: Input collection (already available via ehr_loader + audio_loader)
Stage 02: MedSigLIP encoding (if images present)
    → encode_visit_images(current_images, prior_images) from medsiglip/embeddings.py
Stage 03: GP assessment + board routing
    → GPAgent.run(transcript, ehr_summary, medsiglip_summary)
    → Extract: routing_decisions, medication_list
Stage 04: Parallel specialist dispatch (based on routing_decisions from Stage 03)
    → Use ThreadPoolExecutor to run selected agents concurrently
    → Always run: PharmacologyAgent.run(medication_list, symptoms)
    → Conditionally run: RadiologistAgent, DermatologistAgent, CardiologistAgent,
      PulmonologistAgent, EndocrinologistAgent based on GPAssessment.board_routing
Stage 05: Board synthesis
    → SynthesisAgent.run(all_reports)
Stage 06: Confidence gating
    → Block on critical DDIs (require acknowledgement field in request)
    → Return all safety_alerts prominently
```

3. Add `POST /clinical/assess` API endpoint in new file `src/api/clinical.py`
4. Register the new router in `src/api/main.py`

**Request model:**
```python
class ClinicalRequest(BaseModel):
    transcript: str
    ehr_patient_id: Optional[str]
    ehr_summary: Optional[dict]
    images: Optional[List[bytes]]       # base64-encoded image bytes
    enable_pubmed_rag: bool = False
    critical_ddi_acknowledged: bool = False
```

**Response model:**
```python
class ClinicalReport(BaseModel):
    gp_assessment: dict
    specialist_reports: dict     # {agent_name: assessment_dict}
    pharmacology_assessment: dict
    synthesis: dict              # SynthesisAssessment
    requires_review: bool = True
    audit_id: str
```

---

### TASK 4 — Radiology Pipeline + API [HIGH]
**Files:**
- `src/pipelines/radiology_pipeline.py` (stub → full)
- `src/api/radiology.py` (stub → full)

**Instructions:**
1. Read both files to see current stub signatures
2. `radiology_pipeline.py`:
   - `run_radiology_pipeline(image, context, medsiglip_data, ehr_summary) -> dict`
   - Calls: `deidentifier.deidentify_image(image)` → `RadiologistAgent.run(context, image, medsiglip_data)`
   - Returns RadiologistReport dict + requires_review=True
3. `radiology_pipeline.py` also: `run_cxr_pipeline(image) -> dict` for standalone CXR
4. `radiology.py` API:
   - `POST /radiology/analyze` — accepts image upload + optional context JSON
   - Parse multipart form: image file + context string
   - Call `run_radiology_pipeline`
   - Return RadiologistReport

---

### TASK 5 — Post-Prescription Safety + Confidence Gating (Stage 06) [HIGH]
**File to update:** `src/api/drugs.py`
**New file:** `src/pipelines/safety_gate.py`

**Instructions for `src/api/drugs.py`:**
- Add `POST /drug-check/post-rx` endpoint
- Takes: `{new_medications: List[str], all_active_medications: List[str], patient_conditions: Optional[List[str]]}`
- Runs DDI check on `new_medications + all_active_medications`
- Returns: severity-graded alerts, highlights interactions involving `new_medications`

**Instructions for `src/pipelines/safety_gate.py`:**
- `confidence_gate(clinical_report: dict) -> GateResult`
- `GateResult.blocked = True` if any critical DDI exists AND `critical_ddi_acknowledged=False`
- `GateResult.escalation_items` — list of items requiring physician sign-off
- `GateResult.audit_entry` — log all gate decisions to `src/utils/audit.py`
- Rule: critical findings in specialist reports also go to escalation_items

---

### TASK 6 — Foundation Model Implementations [MEDIUM]
**Files (all currently raise NotImplementedError):**
- `src/models/cxr_foundation/embeddings.py`
- `src/models/derm_foundation/embeddings.py`
- `src/models/path_foundation/embeddings.py`

**These follow the same pattern as `src/models/medsiglip/embeddings.py` which is fully implemented.**

For each foundation model, implement:
1. `load_{model}()` → (processor, model) — loads from `models/google--{model_id}/`
2. `embed_{modality}(image) -> torch.Tensor` — returns L2-normalised embedding
3. `classify_{modality}(image, labels) -> Dict[str, float]` — zero-shot classification

**CXR Foundation:** `google/cxr-foundation` — EfficientNet-L2 architecture
- Input: chest X-rays (PA/AP views)
- Output: 1376-dim embedding (CheXpert-trained)
- Key difference from MedSigLIP: CXR-only, higher accuracy on chest pathology

**Derm Foundation:** `google/derm-foundation`
- Input: skin images (any body location)
- Output: 1024-dim embedding
- Trained on 26M+ dermatology images

**Path Foundation:** `google/path-foundation`
- Input: histopathology tiles (224×224 typically)
- Output: 128-dim or 768-dim embedding
- Use `AutoModel.from_pretrained` — check config for architecture details

**Implementation note:** Follow the exact pattern of `medsiglip/embeddings.py`:
- Module-level `_model`, `_processor` cache
- `_get_model_path()` reading from `MODEL_WEIGHTS_PATH` env var
- `load_*()` raises `FileNotFoundError` if weights not present
- All public functions accept optional `processor=None, model=None` and call `load_*()` if needed

---

### TASK 7 — Pathologist Agent [MEDIUM]
**File:** `src/agents/pathologist_agent.py` (stub → full)

**Instructions:**
1. Read the current stub to see existing function signatures
2. Create `src/agents/pathology_schema.py` with:
   - `TissueFindings(BaseModel)`: architecture, cellularity, necrosis, mitotic_index, margins
   - `PathologyAssessment(BaseModel)`: chain_of_thought, tissue_type, primary_diagnosis, differential, grade, biomarkers, ihc_results, clinical_significance, requires_review=True

3. Implement `PathologistAgent.run(context, image, path_foundation_data)`:
   - System prompt covering: H&E staining interpretation, WHO grading systems, IHC panel interpretation (ER/PR/HER2 for breast; CD markers for lymphoma), Gleason score for prostate, tumor microenvironment assessment, margin assessment
   - Call `structured_output_with_image(context, image, PathologyAssessment, SYSTEM_PROMPT)` if image present
   - Call `structured_output(context, PathologyAssessment, SYSTEM_PROMPT)` if text-only
   - Log critical findings (high-grade malignancy, positive margins) with `logger.warning`

---

### TASK 8 — DICOM Loader + CXR Preprocessing [MEDIUM]
**Files:**
- `src/data/dicom_loader.py` (partial stub → full)
- `src/preprocessing/cxr.py` (stub → full)
- `src/preprocessing/ct.py` (stub → full)

**dicom_loader.py instructions:**
1. Read current file to see stub signatures
2. Implement `load_dicom(path: str) -> dict`:
   - Use `pydicom` to load .dcm files
   - Extract pixel array and convert to PIL Image (handle windowing for CT HU values)
   - Strip PHI tags from DICOM header: PatientName, PatientID, PatientBirthDate, InstitutionName, etc. (use pydicom `ds.remove_private_tags()`)
   - Return `{"image": PIL.Image, "modality": str, "metadata": dict (safe fields only)}`
3. Implement `load_dicom_series(directory: str) -> List[dict]` for CT series

**cxr.py preprocessing instructions:**
1. Implement `preprocess_cxr(image: PIL.Image.Image) -> PIL.Image.Image`:
   - Resize to 448×448 (MedSigLIP input) or 224×224 (CXR Foundation)
   - Convert to RGB if grayscale (DICOM CXRs are often single-channel)
   - Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for better contrast
   - Normalize pixel values to [0, 1] range
   - Return PIL Image (the model processors handle final normalization)

**ct.py preprocessing instructions:**
1. `preprocess_ct_slice(image: PIL.Image.Image, window_center: int = 40, window_width: int = 400) -> PIL.Image.Image`:
   - Apply CT windowing: clip HU values to [WC - WW/2, WC + WW/2]
   - Normalize to [0, 255] uint8
   - Standard windows: soft tissue (WC=40, WW=400), lung (WC=-600, WW=1500), bone (WC=700, WW=3000)

---

### TASK 9 — TxGemma Inference [MEDIUM]
**File:** `src/models/txgemma/inference.py` (stub → full)

**Model:** `google/txgemma-2b-predict` (smallest, most practical)

**Instructions:**
1. Read current stub to see expected function signatures
2. Implement following the same pattern as `src/models/medgemma/inference.py`:
   - `load_txgemma()` → (tokenizer, model) — loads from `models/google--txgemma-2b-predict/`
   - Uses `AutoTokenizer` + `AutoModelForCausalLM` (TxGemma is text-only)
   - `predict_treatment_outcome(context: str, treatment: str) -> dict`:
     - Returns: `{"prediction": str, "confidence": float, "reasoning": str}`
     - TxGemma is trained on clinical trial data — use for treatment response prediction
   - `predict_adverse_event(drug: str, patient_context: str) -> dict`:
     - Returns probability of adverse events
   - `summarize_clinical_trial(trial_text: str) -> str`
3. Note: TxGemma uses specialized prompt format — check model card on HuggingFace for exact prompt template
4. Add `requires_review = True` to all prediction outputs

---

### TASK 10 — Full UI Wiring [LOW]
**Existing JSX components (not currently served):**
- `src/ui/pages/DrugCheck.jsx`
- `src/ui/pages/RadiologyReport.jsx`
- `src/ui/pages/Worklist.jsx`
- `src/ui/components/AIOutputCard.jsx`, `ConfidenceIndicator.jsx`, `CriticalAlert.jsx`, `DrugInteractionAlert.jsx`

**Instructions:**
1. Create `src/ui/static/app.html` — main SPA shell that loads React + Babel from CDN
2. For each page component, embed as a script tag in the HTML (no build system needed for demo)
3. Wire components to the FastAPI API endpoints:
   - DrugCheck.jsx → `POST /drug-check/`
   - RadiologyReport.jsx → `POST /radiology/analyze`
   - Worklist.jsx → `GET /clinical/worklist` (new endpoint — list of patients)
4. Add navigation tab bar between transcription / drug-check / radiology / worklist views
5. Register a new static mount in `src/api/main.py` serving `src/ui/static/`

---

## Session Starting Instructions for Claude Code

Paste the following at the start of the next Claude Code session:

```
I need you to continue implementing CREDO (MedGemmaApp at C:\Users\test\PycharmProjects\MedGemmaApp).
Completed in the previous session: structured_output engine, all 5 specialist agent schemas + .py files,
DDI pipeline, pharmacology agent, document extractor, MedSigLIP Stage 02 encoder.

Working model: google/medgemma-1.5-4b-it. Weights path env var: MODEL_WEIGHTS_PATH.
Pattern: requires_review=True on all clinical outputs. PHI de-identified before any model call.
Architecture: docs/solution_architecture.html. Next session plan: docs/next_session_workplan.md.

Execute the tasks in the next_session_workplan.md in order, starting with Task 1 (deidentifier).
Pre-approve all file edits and bash commands within the project folder.
Do NOT ask for confirmation mid-task. Ask clarifying questions before starting if needed.
```

---

## Notes on CT Foundation and HeAR

**CT Foundation** (`google/ct-foundation`) is NOT available on HuggingFace.
It requires Google Cloud Vertex AI Model Garden access.
The `src/models/ct_foundation/embeddings.py` stub should be updated to raise a clear
`NotImplementedError("CT Foundation requires Google Cloud Vertex AI — not available via HuggingFace.")`.
Do not attempt to implement this without Vertex AI credentials.

**HeAR** (`google/hear-pytorch`) — heart sound analysis model.
Lower priority for the demo. The `src/models/hear/embeddings.py` stub can remain as-is
unless the demo case includes auscultation audio. If implementing, it uses a 1D audio
encoder — see `google/hear-pytorch` model card for input format (PCM, 16kHz).

---

## Architecture Coverage After This Plan

| Architecture Stage | After next session |
|---|---|
| Stage 01: Health Profile | 80% (FHIR write-back still TODO) |
| Stage 02: Image Encoding | 100% (MedSigLIP complete) |
| Stage 03: Attending + Routing | 100% |
| Stage 04: Medical Board | 90% (pathologist partial) |
| Stage 05: Board Synthesis | 100% (after Task 2+3) |
| Stage 06: Post-Rx Safety | 90% (after Task 5) |
| Stage 07: Final Output | 70% (no EHR write-back) |
