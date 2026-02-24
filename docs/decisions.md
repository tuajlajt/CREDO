# Architecture Decision Records (ADR)

Log of significant technical decisions made during the MedGemma Medical AI project.

---

## ADR Format

Each ADR follows this structure:
- **Status**: Proposed / Accepted / Deprecated / Superseded
- **Context**: What problem prompted this decision
- **Decision**: What was decided
- **Consequences**: Trade-offs and downstream impacts

---

## ADR-001: HAI-DEF as Primary Model Suite

**Status**: Accepted
**Date**: 2025

**Context**:
Multiple medical AI model suites are available (BioMedCLIP, Med-PaLM, RadImageNet, etc.). A single coherent suite from a trusted provider simplifies integration, licensing, and maintenance.

**Decision**:
Use Google's HAI-DEF (Health AI Developer Foundations) suite exclusively. This covers CXR, Derm, Pathology, CT, Audio (HeAR), multimodal (MedSigLIP), text+vision (MedGemma), drug (TxGemma), and ASR (MedASR).

**Consequences**:
+ Single HuggingFace organisation to track
+ Consistent model interfaces and token authentication
+ Strong clinical validation publications
- Hard dependency on Google's model update cadence
- Some modalities (e.g. MRI) not covered by HAI-DEF

---

## ADR-002: FastAPI over Django/Flask

**Status**: Accepted
**Date**: 2025

**Context**:
Need async API for handling large model inference requests and file uploads without blocking.

**Decision**:
Use FastAPI with uvicorn. Async-native, Pydantic v2 validation, automatic OpenAPI docs, minimal overhead.

**Consequences**:
+ Native async/await for non-blocking inference
+ Automatic request validation via Pydantic
+ OpenAPI docs auto-generated
- Smaller ecosystem than Django for admin/ORM features (not needed here)

---

## ADR-003: HIPAA Compliance via De-identification Pipeline

**Status**: Accepted
**Date**: 2025

**Context**:
Real patient data (DICOM, clinical notes, audio) must never be stored in identifiable form outside secure enclaves.

**Decision**:
All data entering the pipeline passes through `src/data/deidentifier.py` (Microsoft Presidio + custom DICOM tag stripping). Raw data is never written to disk by the application. Audit log records every data access event.

**Consequences**:
+ HIPAA Safe Harbor de-identification compliance
+ Audit trail for all PHI access
- Performance overhead from Presidio NER on every clinical note
- Some PHI patterns (e.g. rare name+date combinations) may survive de-identification

---

## ADR-004: All AI Outputs Require `requires_review=True`

**Status**: Accepted
**Date**: 2025

**Context**:
Medical AI outputs must not be acted on autonomously without clinician review. This is both an ethical requirement and an FDA SaMD requirement for CDSS (Clinical Decision Support Software).

**Decision**:
Every agent output dataclass (`GPOutput`, `RadiologyReport`, `DermatologyAssessment`, etc.) has `requires_review: bool = True` hardcoded. No code path may set this to False. UI components display an AI badge and acknowledgement prompt.

**Consequences**:
+ Clear audit trail that outputs are advisory only
+ Regulatory compliance for CDSS classification
- Additional UX friction for clinicians

---

## ADR-005: Separate Dev Agent Layer from Clinical Agent Layer

**Status**: Accepted
**Date**: 2025

**Context**:
Two distinct concerns: (1) software development workflow orchestration; (2) clinical inference routing at runtime. Mixing these creates confusion about responsibilities.

**Decision**:
- `claude/agents/` — development orchestration agents (workflow-orchestrator, code-architect, etc.)
- `med_agents/` — clinical model agents (radiologist-agent, medgemma-agent, etc.) + `medical-workflow-orchestrator.md`

**Consequences**:
+ Clear separation of development vs. clinical concerns
+ Each layer can evolve independently
- Two locations to maintain agent .md files

---

## ADR-006: LoRA Fine-Tuning via PEFT

**Status**: Proposed
**Date**: 2025

**Context**:
Full fine-tuning of 4B–27B parameter models requires prohibitive GPU memory and time. Adapters allow task-specific fine-tuning on domain data.

**Decision**:
Use Hugging Face PEFT library with LoRA adapters for fine-tuning MedGemma on institution-specific data.

**Consequences**:
+ Fine-tune with 1–2 GPUs instead of 8+
+ Adapter weights are small (<100MB) and swappable
- LoRA may not fully capture complex domain shifts
- Requires careful rank selection (r=8–64) per task

---

<!-- Add new ADRs below this line -->
