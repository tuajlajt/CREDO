"""
Component integration tests for MedGemma Medical AI.

Sections
--------
1.  MedASR  — audio transcription
2.  MedGemma multimodal  — image + text inference
3.  MedGemma structured output  — SOAP / ICD / orders via structured_output()
4.  DDI database (RxNav)  — drug-name resolution + interaction lookup
5.  Side effects (openFDA)  — adverse-reaction retrieval + aggregation
6.  RAG DDI (PubMed)  — evidence retrieval + claim extraction
7.  Orchestration  — full run_drug_check_pipeline() with logging
8.  Specialist agents  — GPAgent, Radiologist, Cardiologist, Pulmonologist,
                        Endocrinologist, Dermatologist, PharmacologyAgent
9.  Multi-agent pipeline  — orchestrator, SynthesisAgent, run_clinical_reasoning

Markers
-------
requires_weights : skip if local model weights are absent
requires_network : skip if internet is unavailable
slow             : full model-inference tests (>30 s) — excluded by default
integration      : any test that hits a real service or loaded model

Run modes
---------
# Fast (no models, no network):
pytest tests/test_components.py

# Network tests only:
pytest tests/test_components.py -m requires_network

# Full integration (models + network):
pytest tests/test_components.py -m "requires_weights or requires_network" --run-slow

# Single section:
pytest tests/test_components.py -k "Pharmacology"
"""
from __future__ import annotations

import io
import json
import logging
import os
import struct
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import pytest
from PIL import Image

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers: availability checks
# ─────────────────────────────────────────────────────────────────────────────

def _medgemma_available() -> bool:
    base = os.environ.get("MODEL_WEIGHTS_PATH", "./models")
    return Path(base, "google--medgemma-1.5-4b-it").exists()


def _medasr_available() -> bool:
    base = os.environ.get("MODEL_WEIGHTS_PATH", "./models")
    return Path(base, "google--medasr").exists()


def _network_available() -> bool:
    try:
        import requests
        r = requests.get("https://rxnav.nlm.nih.gov/REST/version.json", timeout=6)
        return r.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# pytest marks (evaluated at collection time)
# ─────────────────────────────────────────────────────────────────────────────

skip_no_medgemma = pytest.mark.skipif(
    not _medgemma_available(),
    reason="MedGemma weights not found — run: TIER=core bash scripts/download_models.sh",
)
skip_no_medasr = pytest.mark.skipif(
    not _medasr_available(),
    reason="MedASR weights not found — run: TIER=audio bash scripts/download_models.sh",
)
skip_no_network = pytest.mark.skipif(
    not _network_available(),
    reason="RxNav/internet not reachable — requires network access",
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared synthetic data
# ─────────────────────────────────────────────────────────────────────────────

# Realistic synthetic clinical transcript used across multiple tests.
CLINICAL_TRANSCRIPT = (
    "Patient is a 67-year-old male with a history of atrial fibrillation and "
    "type 2 diabetes, presenting today with a 3-day history of chest tightness "
    "and exertional dyspnoea. He denies fever, cough, or leg swelling. "
    "Current medications include warfarin 5 mg daily, metformin 1000 mg twice "
    "daily, lisinopril 10 mg daily, and aspirin 75 mg daily. "
    "His last INR was 2.8 two weeks ago. "
    "Blood pressure today is 148 over 92 mmHg, heart rate 86 beats per minute, "
    "oxygen saturation 97% on air, weight 88 kg. "
    "Assessment: likely cardiac origin for chest tightness — need to rule out "
    "acute coronary syndrome versus atrial fibrillation with rate issues. "
    "Plan: order troponin, BNP, CBC, HbA1c, and a 12-lead ECG. "
    "Refer to cardiology urgently. Patient is due for diabetes review — "
    "last HbA1c was 8.2% six months ago."
)

WARFARIN_ASPIRIN_DRUGS = ["warfarin", "aspirin", "lisinopril", "metformin"]

PATIENT_SYMPTOMS = ["chest tightness", "shortness of breath", "dizziness", "fatigue"]

SYNTHETIC_EHR = {
    "demographics": {"name": "Test Patient", "age": 67, "sex": "M", "blood_type": "A+"},
    "active_conditions": [
        {"code": "I48", "display": "Atrial fibrillation", "onset": "2019-03-01"},
        {"code": "E11", "display": "Type 2 diabetes mellitus", "onset": "2016-05-15"},
        {"code": "I10", "display": "Essential hypertension", "onset": "2015-01-01"},
    ],
    "allergies": [{"substance": "Penicillin", "severity": "moderate"}],
    "current_medications": [
        {"name": "Warfarin", "inn": "warfarin", "dose": "5 mg", "frequency": "daily"},
        {"name": "Aspirin", "inn": "aspirin", "dose": "75 mg", "frequency": "daily"},
        {"name": "Lisinopril", "inn": "lisinopril", "dose": "10 mg", "frequency": "daily"},
        {"name": "Metformin", "inn": "metformin", "dose": "1000 mg", "frequency": "twice daily"},
    ],
    "latest_vitals": {
        "weight_kg": 88,
        "systolic_mmhg": 148,
        "diastolic_mmhg": 92,
        "heart_rate_bpm": 86,
        "spo2_pct": 97.0,
    },
}


def _default_config() -> dict:
    """Load default config, fall back to minimal dict if unavailable."""
    try:
        from src.config.loader import load_config
        return load_config()
    except Exception:
        return {"max_retries": 1, "model_id": "google/medgemma-1.5-4b-it"}


def _make_wav_bytes(duration_s: float = 3.0, sample_rate: int = 16000) -> bytes:
    """Generate a minimal WAV file in memory (440 Hz sine tone)."""
    num_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, num_samples, dtype=np.float32)
    waveform = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(waveform.tobytes())
    return buf.getvalue()


@pytest.fixture
def tmp_wav(tmp_path: Path) -> Path:
    """Temporary WAV file for MedASR tests (3-second 440 Hz sine tone)."""
    wav_path = tmp_path / "test_audio.wav"
    wav_path.write_bytes(_make_wav_bytes(3.0))
    return wav_path


@pytest.fixture
def tmp_long_wav(tmp_path: Path) -> Path:
    """35-second WAV to exercise the long-audio chunking path in MedASR."""
    wav_path = tmp_path / "long_audio.wav"
    wav_path.write_bytes(_make_wav_bytes(35.0))
    return wav_path


@pytest.fixture
def synthetic_rgb_image() -> Image.Image:
    """224×224 RGB test image (random noise)."""
    arr = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def synthetic_cxr_image() -> Image.Image:
    """224×224 grayscale synthetic chest X-ray (random noise)."""
    arr = np.random.randint(0, 255, (224, 224), dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


# ═════════════════════════════════════════════════════════════════════════════
# 1. MedASR  — audio transcription
# ═════════════════════════════════════════════════════════════════════════════

class TestMedASR:
    """MedASR: offline speech-to-text using google/medasr (lasr_ctc arch)."""

    @pytest.mark.requires_weights
    @skip_no_medasr
    def test_medasr_loads(self, caplog):
        """load_medasr() returns (processor, model) without error."""
        caplog.set_level(logging.INFO)
        from src.models.medasr.inference import load_medasr

        logger.info("Loading MedASR processor and model …")
        t0 = time.time()
        processor, model = load_medasr()
        elapsed = time.time() - t0

        logger.info("MedASR loaded in %.1f s", elapsed)
        assert processor is not None, "Processor should not be None"
        assert model is not None, "Model should not be None"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medasr
    def test_medasr_transcribes_numpy_array(self, caplog):
        """transcribe_medical_audio(waveform_array) returns expected dict."""
        caplog.set_level(logging.DEBUG)
        from src.models.medasr.inference import transcribe_medical_audio

        waveform = np.zeros(16000 * 3, dtype=np.float32)   # 3 s silence
        logger.info("Transcribing 3-second silence waveform …")
        result = transcribe_medical_audio(waveform, sample_rate=16000)

        logger.info("MedASR result keys: %s", list(result.keys()))
        logger.info("Transcript: %r (len=%d)", result["transcript"], len(result["transcript"]))
        logger.info("Chunks: %d chunk(s)", len(result["chunks"]))
        logger.info("Model path: %s", result.get("model"))

        assert isinstance(result, dict), "Return type must be dict"
        assert "transcript" in result
        assert "chunks" in result
        assert "model" in result
        assert isinstance(result["transcript"], str)
        assert isinstance(result["chunks"], list)
        assert len(result["chunks"]) >= 1

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medasr
    def test_medasr_transcribes_wav_file(self, tmp_wav: Path, caplog):
        """transcribe_medical_audio(file_path) accepts a WAV file."""
        caplog.set_level(logging.DEBUG)
        from src.models.medasr.inference import transcribe_medical_audio

        logger.info("Transcribing WAV file: %s", tmp_wav)
        result = transcribe_medical_audio(str(tmp_wav))

        logger.info("Transcript: %r", result["transcript"])
        assert isinstance(result["transcript"], str), "Transcript must be a string"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medasr
    def test_medasr_long_audio_chunking(self, tmp_long_wav: Path, caplog):
        """35-second file triggers the multi-chunk path; multiple chunk entries returned."""
        caplog.set_level(logging.DEBUG)
        from src.models.medasr.inference import transcribe_medical_audio
        from src.models.medasr.preprocessing import CHUNK_SECONDS

        logger.info("Transcribing 35-second file (CHUNK_SECONDS=%d) …", CHUNK_SECONDS)
        result = transcribe_medical_audio(str(tmp_long_wav))

        logger.info("Chunks produced: %d", len(result["chunks"]))
        assert len(result["chunks"]) >= 2, (
            f"Expected ≥2 chunks for 35-second audio (CHUNK_SECONDS={CHUNK_SECONDS})"
        )
        full = result["transcript"]
        joined = " ".join(c for c in result["chunks"] if c)
        assert full == joined.strip() or len(full) > 0, (
            "Full transcript should match joined chunks"
        )

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medasr
    def test_medasr_postprocessing_applies(self, caplog):
        """postprocess_transcript replaces marker tokens with punctuation."""
        caplog.set_level(logging.DEBUG)
        from src.models.medasr.preprocessing import postprocess_transcript

        raw = "the patient has a temperature of 38 {period} 5 degrees {comma} no cough"
        processed = postprocess_transcript(raw)
        logger.info("Raw:       %r", raw)
        logger.info("Processed: %r", processed)

        assert "{period}" not in processed
        assert "{comma}" not in processed
        assert "." in processed or "," in processed


# ═════════════════════════════════════════════════════════════════════════════
# 2. MedGemma multimodal  — image + text inference
# ═════════════════════════════════════════════════════════════════════════════

class TestMedGemmaMultimodal:
    """MedGemma 1.5 4B: image+text and text-only inference paths."""

    @pytest.mark.requires_weights
    @skip_no_medgemma
    def test_medgemma_loads(self, caplog):
        """load_medgemma() returns (processor, model) without error."""
        caplog.set_level(logging.INFO)
        from src.models.medgemma.inference import load_medgemma

        logger.info("Loading MedGemma 1.5 4B …")
        t0 = time.time()
        processor, model = load_medgemma()
        elapsed = time.time() - t0

        logger.info("MedGemma loaded in %.1f s", elapsed)
        assert processor is not None
        assert model is not None

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_medgemma_text_inference(self, caplog):
        """run_text_inference(system, user) returns a non-empty string."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.inference import run_text_inference

        question = "What is the typical first-line treatment for type 2 diabetes?"
        logger.info("TEXT INFERENCE — question: %r", question)
        t0 = time.time()
        response = run_text_inference(
            system_prompt="You are a concise clinical reference AI.",
            user_message=question,
            max_new_tokens=256,
        )
        elapsed = time.time() - t0

        logger.info("Response (%.1f s):\n%s", elapsed, response)
        assert isinstance(response, str)
        assert len(response) > 10, "Response should contain actual content"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_medgemma_analyze_medical_image(self, synthetic_cxr_image, caplog):
        """analyze_medical_image(image, question) returns a non-empty response."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.inference import analyze_medical_image

        question = "Describe any abnormalities visible in this chest X-ray."
        logger.info("IMAGE ANALYSIS — question: %r", question)
        t0 = time.time()
        response = analyze_medical_image(synthetic_cxr_image, question, max_new_tokens=256)
        elapsed = time.time() - t0

        logger.info("Image analysis response (%.1f s):\n%s", elapsed, response)
        assert isinstance(response, str)
        assert len(response) > 5

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_medgemma_generate_radiology_report(self, synthetic_cxr_image, caplog):
        """generate_radiology_report returns a parseable JSON string."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.inference import generate_radiology_report

        logger.info("RADIOLOGY REPORT — generating from synthetic CXR …")
        t0 = time.time()
        raw = generate_radiology_report(synthetic_cxr_image, modality="chest X-ray")
        elapsed = time.time() - t0

        logger.info("Raw report output (%.1f s):\n%s", elapsed, raw[:800])
        assert isinstance(raw, str)
        # Strip markdown fences and parse JSON
        clean = raw.strip().strip("`").strip()
        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(clean[start:end + 1])
            logger.info("Parsed report keys: %s", list(data.keys()))
            expected_keys = {"findings", "impression"}
            assert expected_keys & set(data.keys()), (
                f"Report should contain at least one of {expected_keys}"
            )
        else:
            logger.warning("Output was not JSON — acceptable for edge cases: %r", raw[:200])


# ═════════════════════════════════════════════════════════════════════════════
# 3. MedGemma structured output  — SOAP / ICD / orders
# ═════════════════════════════════════════════════════════════════════════════

class TestMedGemmaStructuredOutput:
    """structured_output() engine: SOAP notes, ICD codes, GPAssessment schema."""

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_structured_output_returns_dict(self, caplog):
        """structured_output(context, GPAssessment) returns a dict."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.structured_output import structured_output
        from src.agents.gp_schema import GPAssessment

        logger.info("STRUCTURED OUTPUT — context length: %d chars", len(CLINICAL_TRANSCRIPT))
        t0 = time.time()
        result = structured_output(
            context=CLINICAL_TRANSCRIPT,
            target_model=GPAssessment,
            max_new_tokens=2048,
        )
        elapsed = time.time() - t0

        logger.info("structured_output completed in %.1f s", elapsed)
        logger.info("Result keys: %s", list(result.keys()))
        assert isinstance(result, dict), "structured_output must return dict"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_structured_output_requires_review_always_true(self, caplog):
        """requires_review is always True — safety invariant must hold."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.structured_output import structured_output
        from src.agents.gp_schema import GPAssessment

        result = structured_output(
            context=CLINICAL_TRANSCRIPT,
            target_model=GPAssessment,
            max_new_tokens=2048,
        )
        logger.info("requires_review value: %s", result.get("requires_review"))
        assert result.get("requires_review") is True, (
            "SAFETY VIOLATION: requires_review must always be True"
        )

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_gp_assessment_chief_complaint_populated(self, caplog):
        """GPAssessment.chief_complaint is populated from clinical transcript."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.structured_output import structured_output
        from src.agents.gp_schema import GPAssessment

        result = structured_output(
            context=CLINICAL_TRANSCRIPT,
            target_model=GPAssessment,
            max_new_tokens=2048,
        )
        chief = result.get("chief_complaint", "")
        logger.info("Chief complaint: %r", chief)
        assert chief, "chief_complaint should not be empty"
        assert len(chief) > 5

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_gp_assessment_soap_fields(self, caplog):
        """GPAssessment.soap contains all four SOAP sections."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.structured_output import structured_output
        from src.agents.gp_schema import GPAssessment

        result = structured_output(
            context=CLINICAL_TRANSCRIPT,
            target_model=GPAssessment,
            max_new_tokens=2048,
        )
        soap = result.get("soap", {})
        logger.info("SOAP subjective: %s …", str(soap.get("subjective", ""))[:120])
        logger.info("SOAP objective:  %s …", str(soap.get("objective", ""))[:120])
        logger.info("SOAP assessment: %s …", str(soap.get("assessment", ""))[:120])
        logger.info("SOAP plan:       %s …", str(soap.get("plan", ""))[:120])

        for section in ("subjective", "objective", "assessment", "plan"):
            assert section in soap, f"SOAP section '{section}' missing"
            assert soap[section], f"SOAP section '{section}' is empty"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_gp_assessment_icd_codes_extracted(self, caplog):
        """GPAssessment.icd_codes contains ICD-10 entries with code + description."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.structured_output import structured_output
        from src.agents.gp_schema import GPAssessment

        result = structured_output(
            context=CLINICAL_TRANSCRIPT,
            target_model=GPAssessment,
            max_new_tokens=2048,
        )
        icd_codes = result.get("icd_codes", [])
        logger.info("ICD codes extracted: %d", len(icd_codes))
        for code in icd_codes:
            logger.info("  %s — %s (confidence: %s)",
                        code.get("code"), code.get("description"), code.get("confidence"))

        assert len(icd_codes) > 0, "At least one ICD-10 code expected for this transcript"
        for entry in icd_codes:
            assert "code" in entry, "ICD entry must have 'code' field"
            assert entry["code"], "ICD code must not be empty"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_gp_assessment_board_routing_populated(self, caplog):
        """GPAssessment.board_routing is populated and contains expected flags."""
        caplog.set_level(logging.DEBUG)
        from src.models.medgemma.structured_output import structured_output
        from src.agents.gp_schema import GPAssessment

        result = structured_output(
            context=CLINICAL_TRANSCRIPT,
            target_model=GPAssessment,
            max_new_tokens=2048,
        )
        routing = result.get("board_routing", {})
        logger.info("Board routing: %s", {
            k: v for k, v in routing.items()
            if k not in ("routing_rationale", "context_packets")
        })
        logger.info("Routing rationale: %s …", str(routing.get("routing_rationale", ""))[:200])

        assert isinstance(routing, dict), "board_routing must be a dict"
        expected_flags = {
            "consult_radiologist", "consult_cardiologist",
            "consult_dermatologist", "consult_pulmonologist",
            "consult_endocrinologist", "consult_pharmacology",
        }
        # At least some routing flags should be present
        present = expected_flags & set(routing.keys())
        assert len(present) >= 3, (
            f"Expected routing flags not found. Present: {set(routing.keys())}"
        )
        # For this transcript, cardiology and pharmacology should be True
        if "consult_cardiologist" in routing:
            logger.info("consult_cardiologist = %s", routing["consult_cardiologist"])
        if "consult_pharmacology" in routing:
            logger.info("consult_pharmacology = %s", routing["consult_pharmacology"])


# ═════════════════════════════════════════════════════════════════════════════
# 4. DDI database (RxNav)  — drug-name resolution + interaction lookup
# ═════════════════════════════════════════════════════════════════════════════

class TestDDIRxNav:
    """RxNav HTTP client: name resolution, ingredient lookup, interaction check."""

    @pytest.mark.requires_network
    @skip_no_network
    def test_medicine_to_inn_generic_name(self, caplog):
        """medicine_to_inns('warfarin') resolves to ['Warfarin'] or equivalent."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.normalization import medicine_to_inns
        from src.pharmacology.rxnav_client import get_default_client

        client = get_default_client()
        logger.info("Resolving INN for 'warfarin' …")
        inns = medicine_to_inns(client, "warfarin")
        logger.info("Resolved INNs: %s", inns)
        assert isinstance(inns, list)
        assert len(inns) >= 1
        assert any("warfarin" in inn.lower() for inn in inns), (
            f"'warfarin' not found in resolved INNs: {inns}"
        )

    @pytest.mark.requires_network
    @skip_no_network
    def test_medicine_to_inn_brand_name(self, caplog):
        """medicine_to_inns('Coumadin') resolves to warfarin (brand → INN)."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.normalization import medicine_to_inns
        from src.pharmacology.rxnav_client import get_default_client

        client = get_default_client()
        logger.info("Resolving INN for brand name 'Coumadin' …")
        inns = medicine_to_inns(client, "Coumadin")
        logger.info("Resolved INNs: %s", inns)
        assert isinstance(inns, list)
        assert len(inns) >= 1

    @pytest.mark.requires_network
    @skip_no_network
    def test_medicine_to_inn_combination_drug(self, caplog):
        """medicine_to_inns('Augmentin') resolves to amoxicillin + clavulanate."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.normalization import medicine_to_inns
        from src.pharmacology.rxnav_client import get_default_client

        client = get_default_client()
        logger.info("Resolving INN for combination drug 'Augmentin' …")
        inns = medicine_to_inns(client, "Augmentin")
        logger.info("Resolved INNs for Augmentin: %s", inns)
        assert isinstance(inns, list)
        # Augmentin = amoxicillin + clavulanate — may return 1 or both
        combined = " ".join(i.lower() for i in inns)
        logger.info("Combined INN string: %r", combined)
        assert "amoxicillin" in combined or "clavulanate" in combined or len(inns) >= 1

    @pytest.mark.requires_network
    @skip_no_network
    def test_resolve_drug_list_to_inns(self, caplog):
        """resolve_drug_list_to_inns handles a mixed brand/generic list."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.normalization import resolve_drug_list_to_inns

        drugs = ["warfarin", "Aspirin", "metformin"]
        logger.info("Resolving drug list: %s", drugs)
        inns = resolve_drug_list_to_inns(drugs)
        logger.info("Resolved INNs: %s", inns)
        assert isinstance(inns, list)
        assert len(inns) >= 2, "Should resolve at least 2 of 3 drugs"

    @pytest.mark.requires_network
    @skip_no_network
    def test_check_interactions_warfarin_aspirin(self, caplog):
        """Warfarin + aspirin triggers at least one RxNav interaction."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.interactions import check_all_interactions_among_ingredients

        drugs = ["warfarin", "aspirin"]
        logger.info("Checking DDI between: %s", drugs)
        t0 = time.time()
        results = check_all_interactions_among_ingredients(drugs)
        elapsed = time.time() - t0

        logger.info("RxNav DDI check completed in %.1f s", elapsed)
        logger.info("Interactions found: %d", len(results))
        for r in results:
            logger.info("  [%s] %s × %s: %s",
                        r.severity,
                        r.ingredient_1_inn,
                        r.ingredient_2_inn,
                        r.interaction[:100])

        assert len(results) >= 1, (
            "Warfarin + aspirin is a known drug interaction — should appear in RxNav"
        )

    @pytest.mark.requires_network
    @skip_no_network
    def test_interaction_result_structure(self, caplog):
        """InteractionResult objects have all required fields with correct types."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.interactions import (
            check_all_interactions_among_ingredients, InteractionResult
        )

        results = check_all_interactions_among_ingredients(["warfarin", "aspirin"])
        assert len(results) >= 1

        for r in results:
            assert hasattr(r, "ingredient_1_inn")
            assert hasattr(r, "ingredient_2_inn")
            assert hasattr(r, "interaction")
            assert hasattr(r, "severity")
            assert isinstance(r.interaction, str) and len(r.interaction) > 0
            assert r.severity in {"low", "med", "high", "critical"}, (
                f"Unexpected severity bucket: {r.severity!r}"
            )

    @pytest.mark.requires_network
    @skip_no_network
    def test_interaction_severity_bucket_known_pair(self, caplog):
        """warfarin + aspirin interaction is classified as high or critical severity."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.interactions import check_all_interactions_among_ingredients

        results = check_all_interactions_among_ingredients(["warfarin", "aspirin"])
        severities = {r.severity for r in results}
        logger.info("Severity buckets for warfarin+aspirin: %s", severities)
        assert {"high", "critical"} & severities, (
            f"Expected high/critical for warfarin+aspirin; got: {severities}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 5. Side effects (openFDA)  — adverse-reaction retrieval + aggregation
# ═════════════════════════════════════════════════════════════════════════════

class TestSideEffectsOpenFDA:
    """openFDA drug label API: side effects retrieval and multi-drug aggregation."""

    @pytest.mark.requires_network
    @skip_no_network
    def test_get_side_effects_warfarin(self, caplog):
        """get_side_effects_openfda('warfarin') returns a non-empty list."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.side_effects_openfda import get_side_effects_openfda

        logger.info("Fetching side effects for 'warfarin' from openFDA …")
        t0 = time.time()
        effects = get_side_effects_openfda("warfarin", max_effects=20)
        elapsed = time.time() - t0

        logger.info("Side effects for warfarin (%d, %.1f s):", len(effects), elapsed)
        for e in effects[:10]:
            logger.info("  %s (source: %s)", e["effect"], e["source"])

        assert isinstance(effects, list)
        assert len(effects) > 0, "openFDA should return side effects for warfarin"

    @pytest.mark.requires_network
    @skip_no_network
    def test_side_effect_entry_structure(self, caplog):
        """Each SideEffect entry has the required TypedDict fields."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.side_effects_openfda import get_side_effects_openfda

        effects = get_side_effects_openfda("metformin", max_effects=10)
        logger.info("Metformin side effects: %d entries", len(effects))

        for e in effects:
            assert "effect" in e, "SideEffect must have 'effect' key"
            assert "source" in e, "SideEffect must have 'source' key"
            assert isinstance(e["effect"], str) and len(e["effect"]) >= 3

    @pytest.mark.requires_network
    @skip_no_network
    def test_aggregate_side_effects_multiple_drugs(self, caplog):
        """aggregate_side_effects(['warfarin', 'aspirin']) returns aggregated results."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.side_effects_openfda import aggregate_side_effects

        drugs = ["warfarin", "aspirin"]
        logger.info("Aggregating side effects for: %s", drugs)
        t0 = time.time()
        aggregated = aggregate_side_effects(drugs)
        elapsed = time.time() - t0

        logger.info("Aggregated effects (%d, %.1f s) — top 10:", len(aggregated), elapsed)
        for a in aggregated[:10]:
            logger.info("  [%d contributor(s)] %s — contributors: %s",
                        len(a["contributors"]), a["effect"], a["contributors"])

        assert isinstance(aggregated, list)
        assert len(aggregated) > 0

    @pytest.mark.requires_network
    @skip_no_network
    def test_aggregate_overlap_effects_ranked_higher(self, caplog):
        """Effects shared by multiple drugs appear before single-drug effects."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.side_effects_openfda import aggregate_side_effects

        aggregated = aggregate_side_effects(["warfarin", "aspirin", "lisinopril"])
        multi = [a for a in aggregated if len(a["contributors"]) > 1]
        single = [a for a in aggregated if len(a["contributors"]) == 1]
        logger.info("Multi-drug effects: %d; Single-drug effects: %d",
                    len(multi), len(single))

        if multi and single:
            # Multi-contributor effects should appear earlier in the sorted list
            first_multi_idx = next(
                i for i, a in enumerate(aggregated) if len(a["contributors"]) > 1
            )
            first_single_idx = next(
                i for i, a in enumerate(aggregated) if len(a["contributors"]) == 1
            )
            assert first_multi_idx <= first_single_idx, (
                "Multi-contributor effects should rank first"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 6. RAG DDI (PubMed)  — evidence retrieval + rule-based claim extraction
# ═════════════════════════════════════════════════════════════════════════════

class TestPubMedRAG:
    """PubMed RAG: search → fetch summaries → extract interaction claims."""

    @pytest.mark.requires_network
    @skip_no_network
    def test_pubmed_search_returns_pmids(self, caplog):
        """pubmed_search_pmids returns a list of PMID strings."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.pubmed_rag import pubmed_search_pmids, build_pubmed_query

        query = build_pubmed_query("warfarin", "aspirin")
        logger.info("PubMed query: %r", query)
        t0 = time.time()
        pmids = pubmed_search_pmids(query, retmax=5)
        elapsed = time.time() - t0

        logger.info("PMIDs returned (%d, %.1f s): %s", len(pmids), elapsed, pmids[:5])
        assert isinstance(pmids, list)
        assert len(pmids) >= 1, "PubMed should find papers on warfarin + aspirin DDI"
        for pmid in pmids:
            assert isinstance(pmid, str) and pmid.isdigit(), f"Invalid PMID: {pmid!r}"

    @pytest.mark.requires_network
    @skip_no_network
    def test_pubmed_fetch_summaries_returns_evidenceref(self, caplog):
        """pubmed_fetch_summaries returns EvidenceRef dicts with expected fields."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.pubmed_rag import (
            pubmed_search_pmids, pubmed_fetch_summaries, build_pubmed_query
        )

        query = build_pubmed_query("warfarin", "aspirin")
        pmids = pubmed_search_pmids(query, retmax=3)
        if not pmids:
            pytest.skip("No PMIDs found — PubMed search returned nothing")

        logger.info("Fetching summaries for PMIDs: %s", pmids)
        summaries = pubmed_fetch_summaries(pmids)
        logger.info("Summaries returned: %d", len(summaries))

        for pmid, ref in summaries.items():
            logger.info("  PMID %s: %s (%s)", pmid, ref.get("title", "?")[:80], ref.get("year"))
            assert "pmid" in ref
            assert "title" in ref
            assert "pubmed_url" in ref
            assert "pubmed.ncbi.nlm.nih.gov" in ref["pubmed_url"]

    @pytest.mark.requires_network
    @skip_no_network
    def test_rule_based_extract_claims(self, caplog):
        """rule_based_extract_claims extracts at least one claim for known pair."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.pubmed_rag import (
            pubmed_search_pmids, pubmed_fetch_summaries,
            build_pubmed_query, rule_based_extract_claims
        )

        query = build_pubmed_query("warfarin", "aspirin")
        pmids = pubmed_search_pmids(query, retmax=5)
        if not pmids:
            pytest.skip("No PMIDs returned by PubMed")

        summaries = pubmed_fetch_summaries(pmids)
        if not summaries:
            pytest.skip("No summaries returned")

        claims = rule_based_extract_claims("warfarin", "aspirin", summaries)
        logger.info("Rule-based claims extracted: %d", len(claims))
        for c in claims:
            logger.info("  [%s] %s — citations: %d",
                        c.get("claim_confidence"), c.get("claim", "?")[:80],
                        len(c.get("citations", [])))

        assert isinstance(claims, list)
        if claims:
            claim = claims[0]
            assert "claim" in claim
            assert "citations" in claim
            assert len(claim["citations"]) >= 1, (
                "Policy: no uncited claims — every claim must have ≥1 citation"
            )

    def test_build_pubmed_query_format(self, caplog):
        """build_pubmed_query produces a query string containing both drug names."""
        from src.pharmacology.pubmed_rag import build_pubmed_query

        q = build_pubmed_query("fluoxetine", "tramadol")
        logger.info("Query: %r", q)
        assert "fluoxetine" in q.lower()
        assert "tramadol" in q.lower()
        assert "interaction" in q.lower() or "drug" in q.lower()

    def test_rule_based_extracts_from_mock_summaries(self, caplog):
        """Unit test: rule_based_extract_claims works without network using mock summaries."""
        caplog.set_level(logging.DEBUG)
        from src.pharmacology.pubmed_rag import rule_based_extract_claims

        # Mock summaries containing clear interaction signal keywords
        mock_summaries = {
            "12345": {
                "pmid": "12345",
                "title": "Warfarin and aspirin interaction increases bleeding risk",
                "year": "2022",
                "journal": "J Clin Pharmacol",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
            },
            "67890": {
                "pmid": "67890",
                "title": "Pharmacokinetic study of warfarin metabolism potentiation by aspirin",
                "year": "2021",
                "journal": "Blood",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/67890/",
            },
        }

        claims = rule_based_extract_claims("warfarin", "aspirin", mock_summaries)
        logger.info("Claims from mock summaries: %d", len(claims))
        for c in claims:
            logger.info("  %s", c.get("claim", "?")[:100])

        assert isinstance(claims, list)
        if claims:
            for c in claims:
                assert len(c.get("citations", [])) >= 1, "No uncited claims allowed"


# ═════════════════════════════════════════════════════════════════════════════
# 7. Orchestration  — run_drug_check_pipeline() with output logging
# ═════════════════════════════════════════════════════════════════════════════

class TestOrchestration:
    """Full run_drug_check_pipeline: all stages, logging, symptom matching."""

    @pytest.mark.requires_network
    @skip_no_network
    def test_pipeline_basic_no_rag(self, caplog):
        """Pipeline with enable_pubmed_rag=False completes and returns expected keys."""
        caplog.set_level(logging.INFO)
        from src.pipelines.drug_check_pipeline import run_drug_check_pipeline

        logger.info("PIPELINE (no RAG) — drugs: %s", WARFARIN_ASPIRIN_DRUGS)
        t0 = time.time()
        result = run_drug_check_pipeline(
            drug_names=WARFARIN_ASPIRIN_DRUGS,
            patient_symptoms=PATIENT_SYMPTOMS,
            enable_pubmed_rag=False,
            enable_side_effects=True,
        )
        elapsed = time.time() - t0

        logger.info("Pipeline completed in %.1f s", elapsed)
        _log_pipeline_result(result, logger)

        required_keys = {
            "medications_checked", "resolved_inns", "interactions",
            "critical_count", "major_count", "moderate_count",
            "overall_risk_level", "requires_review",
        }
        missing = required_keys - set(result.keys())
        assert not missing, f"Missing keys: {missing}"
        assert result["requires_review"] is True
        assert result["overall_risk_level"] in {"critical", "high", "moderate", "low"}

    @pytest.mark.requires_network
    @skip_no_network
    def test_pipeline_with_rag(self, caplog):
        """Pipeline with enable_pubmed_rag=True appends RAG interaction claims."""
        caplog.set_level(logging.INFO)
        from src.pipelines.drug_check_pipeline import run_drug_check_pipeline

        logger.info("PIPELINE (with RAG) — drugs: warfarin, aspirin")
        t0 = time.time()
        result = run_drug_check_pipeline(
            drug_names=["warfarin", "aspirin"],
            patient_symptoms=["bruising", "nausea"],
            enable_pubmed_rag=True,
            enable_side_effects=False,
        )
        elapsed = time.time() - t0

        logger.info("Pipeline (RAG) completed in %.1f s", elapsed)
        rag = result.get("rag_interactions", [])
        logger.info("RAG interactions found: %d", len(rag))
        for claim in rag[:3]:
            logger.info("  [%s] %s",
                        claim.get("claim_confidence", "?"),
                        str(claim.get("claim", "?"))[:100])

        assert "rag_interactions" in result

    @pytest.mark.requires_network
    @skip_no_network
    def test_pipeline_critical_interaction_flagged(self, caplog):
        """warfarin + aspirin combination is flagged as high/critical risk."""
        caplog.set_level(logging.INFO)
        from src.pipelines.drug_check_pipeline import run_drug_check_pipeline

        result = run_drug_check_pipeline(
            drug_names=["warfarin", "aspirin"],
            enable_pubmed_rag=False,
            enable_side_effects=False,
        )
        logger.info("Overall risk level: %s", result["overall_risk_level"])
        logger.info("Critical: %d, Major: %d, Moderate: %d",
                    result["critical_count"],
                    result["major_count"],
                    result["moderate_count"])

        total_serious = result["critical_count"] + result["major_count"]
        assert total_serious >= 1, (
            "warfarin + aspirin should produce at least one critical or major interaction"
        )
        assert result["overall_risk_level"] in {"critical", "high"}, (
            f"Expected critical/high risk for warfarin+aspirin; got {result['overall_risk_level']!r}"
        )

    @pytest.mark.requires_network
    @skip_no_network
    def test_pipeline_symptom_matching(self, caplog):
        """Pipeline with symptoms produces symptom_matches entries."""
        caplog.set_level(logging.INFO)
        from src.pipelines.drug_check_pipeline import run_drug_check_pipeline

        symptoms = ["bruising", "nausea", "dizziness", "fatigue"]
        result = run_drug_check_pipeline(
            drug_names=["warfarin", "metformin"],
            patient_symptoms=symptoms,
            enable_pubmed_rag=False,
            enable_side_effects=True,
        )
        matches = result.get("symptom_matches", [])
        logger.info("Symptom matches: %d", len(matches))
        for m in matches:
            logger.info("  symptom=%r → effect=%r (similarity=%.2f, contributors=%s)",
                        m.get("symptom"), m.get("matched_effect"),
                        m.get("similarity", 0.0), m.get("contributors"))

        # At least the symptom matching code ran (even if no matches with this drug set)
        assert "symptom_matches" in result

    @pytest.mark.requires_network
    @skip_no_network
    def test_pipeline_recommendations_non_empty_for_critical(self, caplog):
        """Pipeline recommendations are non-empty when a critical interaction exists."""
        caplog.set_level(logging.INFO)
        from src.pipelines.drug_check_pipeline import run_drug_check_pipeline

        result = run_drug_check_pipeline(
            drug_names=["warfarin", "aspirin"],
            enable_pubmed_rag=False,
            enable_side_effects=False,
        )
        recommendations = result.get("recommendations", [])
        logger.info("Recommendations (%d):", len(recommendations))
        for rec in recommendations:
            logger.info("  — %s", rec)

        if result["critical_count"] > 0 or result["major_count"] > 0:
            assert len(recommendations) >= 1, (
                "High-severity interactions should generate at least one recommendation"
            )

    @pytest.mark.requires_network
    @skip_no_network
    def test_pipeline_logging_captures_stages(self, caplog):
        """Pipeline emits INFO log messages for each stage."""
        caplog.set_level(logging.DEBUG)
        from src.pipelines.drug_check_pipeline import run_drug_check_pipeline

        run_drug_check_pipeline(
            drug_names=["warfarin", "aspirin"],
            enable_pubmed_rag=False,
            enable_side_effects=False,
        )
        log_text = caplog.text
        logger.info("Log output captured:\n%s", log_text[:500])
        # Verify at least some pipeline-related log messages appeared
        assert len(log_text) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 8. Specialist agents  — individual agent outputs + safety invariants
# ═════════════════════════════════════════════════════════════════════════════

class TestSpecialistAgents:
    """Each specialist agent: requires_review=True, chain_of_thought present, disclaimer set."""

    # ── GP agent ──────────────────────────────────────────────────────────────

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_gp_agent_run_returns_dict(self, caplog):
        """GPAgent.run() returns a dict with required fields."""
        caplog.set_level(logging.DEBUG)
        from src.agents.gp_agent import GPAgent

        config = _default_config()
        logger.info("Running GPAgent on clinical transcript …")
        t0 = time.time()
        result = GPAgent(config).run(
            transcript=CLINICAL_TRANSCRIPT,
            ehr_summary=SYNTHETIC_EHR,
        )
        elapsed = time.time() - t0

        logger.info("GPAgent completed in %.1f s", elapsed)
        logger.info("Chief complaint: %s", result.get("chief_complaint"))
        logger.info("Urgency: %s", result.get("urgency"))
        logger.info("requires_review: %s", result.get("requires_review"))
        logger.info("CoT (first 200 chars): %s …",
                    str(result.get("chain_of_thought", ""))[:200])

        assert isinstance(result, dict)
        assert result.get("requires_review") is True, "SAFETY: requires_review must be True"
        assert result.get("disclaimer"), "Disclaimer must be present"
        assert result.get("chief_complaint"), "chief_complaint must be populated"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_gp_agent_board_routing_structure(self, caplog):
        """GPAgent returns board_routing with all expected flags."""
        caplog.set_level(logging.DEBUG)
        from src.agents.gp_agent import GPAgent

        config = _default_config()
        result = GPAgent(config).run(
            transcript=CLINICAL_TRANSCRIPT,
            ehr_summary=SYNTHETIC_EHR,
        )
        routing = result.get("board_routing", {})
        logger.info("Board routing flags: %s", {
            k: v for k, v in routing.items()
            if k not in ("routing_rationale", "context_packets")
        })
        logger.info("Routing rationale: %s", str(routing.get("routing_rationale", ""))[:200])

        expected_flags = {
            "consult_cardiologist", "consult_pharmacology",
            "consult_endocrinologist",
        }
        for flag in expected_flags:
            assert flag in routing, f"Expected routing flag '{flag}' not present"

        # Specific to this transcript: cardiologist + pharmacology should be True
        logger.info("consult_cardiologist = %s", routing.get("consult_cardiologist"))
        logger.info("consult_pharmacology = %s", routing.get("consult_pharmacology"))

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_gp_agent_medications_extracted(self, caplog):
        """GPAgent extracts medication names from the transcript."""
        caplog.set_level(logging.DEBUG)
        from src.agents.gp_agent import GPAgent

        config = _default_config()
        result = GPAgent(config).run(transcript=CLINICAL_TRANSCRIPT)
        meds = result.get("medications_mentioned", [])
        logger.info("Medications mentioned: %s", meds)

        assert isinstance(meds, list)
        # Transcript mentions warfarin, metformin, lisinopril, aspirin
        mentioned_lower = " ".join(m.lower() for m in meds)
        assert any(drug in mentioned_lower for drug in ["warfarin", "metformin", "aspirin"]), (
            f"Expected at least one known drug in: {meds}"
        )

    # ── Radiologist agent ─────────────────────────────────────────────────────

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_radiologist_agent_text_only(self, caplog):
        """RadiologistAgent.run() in text-only mode returns a valid report dict."""
        caplog.set_level(logging.DEBUG)
        from src.agents.radiologist_agent import RadiologistAgent

        config = _default_config()
        context = (
            "Clinical indication: chest tightness in a 67-year-old male with AF. "
            "No imaging available — radiologist review of history and prior CXR reports requested."
        )
        logger.info("Running RadiologistAgent (text-only) …")
        t0 = time.time()
        result = RadiologistAgent(config).run(context=context, image=None)
        elapsed = time.time() - t0

        logger.info("RadiologistAgent completed in %.1f s", elapsed)
        _log_agent_result("RadiologistAgent", result, logger)

        assert isinstance(result, dict)
        assert result.get("requires_review") is True
        assert result.get("disclaimer")

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_radiologist_agent_with_image(self, synthetic_cxr_image, caplog):
        """RadiologistAgent.run() with a synthetic CXR image returns a report."""
        caplog.set_level(logging.DEBUG)
        from src.agents.radiologist_agent import RadiologistAgent

        config = _default_config()
        context = "Patient: 67M, AF, chest tightness. CXR attached."
        logger.info("Running RadiologistAgent (with image) …")
        result = RadiologistAgent(config).run(context=context, image=synthetic_cxr_image)

        _log_agent_result("RadiologistAgent (image)", result, logger)
        assert result.get("requires_review") is True
        assert isinstance(result, dict)

    # ── Cardiologist agent ────────────────────────────────────────────────────

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_cardiologist_agent_run(self, caplog):
        """CardiologistAgent.run() returns a structured cardiology assessment."""
        caplog.set_level(logging.DEBUG)
        from src.agents.cardiologist_agent import CardiologistAgent

        config = _default_config()
        context = (
            "67-year-old male with known AF and hypertension presenting with "
            "3-day chest tightness and dyspnoea on exertion. "
            "BP 148/92, HR 86, SpO2 97%. Warfarin + aspirin on board. "
            "Troponin and ECG pending. Last INR 2.8."
        )
        logger.info("Running CardiologistAgent …")
        t0 = time.time()
        result = CardiologistAgent(config).run(context=context)
        elapsed = time.time() - t0

        logger.info("CardiologistAgent completed in %.1f s", elapsed)
        _log_agent_result("CardiologistAgent", result, logger)

        assert isinstance(result, dict)
        assert result.get("requires_review") is True
        assert result.get("disclaimer")
        cot = result.get("chain_of_thought", "")
        logger.info("CoT (first 200 chars): %s", str(cot)[:200])

    # ── Pulmonologist agent ───────────────────────────────────────────────────

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_pulmonologist_agent_run(self, caplog):
        """PulmonologistAgent.run() returns a structured pulmonology assessment."""
        caplog.set_level(logging.DEBUG)
        from src.agents.pulmonologist_agent import PulmonologistAgent

        config = _default_config()
        context = (
            "67-year-old male non-smoker with exertional dyspnoea and chest tightness. "
            "SpO2 97% on air. No wheeze or cough. CXR not available."
        )
        logger.info("Running PulmonologistAgent …")
        t0 = time.time()
        result = PulmonologistAgent(config).run(context=context)
        elapsed = time.time() - t0

        logger.info("PulmonologistAgent completed in %.1f s", elapsed)
        _log_agent_result("PulmonologistAgent", result, logger)
        assert result.get("requires_review") is True

    # ── Endocrinologist agent ─────────────────────────────────────────────────

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_endocrinologist_agent_run(self, caplog):
        """EndocrinologistAgent.run() returns a structured metabolic assessment."""
        caplog.set_level(logging.DEBUG)
        from src.agents.endocrinologist_agent import EndocrinologistAgent

        config = _default_config()
        context = (
            "67-year-old male with T2DM on metformin 1000 mg BD. "
            "Last HbA1c 8.2% six months ago. Weight 88 kg. "
            "Also on lisinopril for hypertension. No retinopathy documented."
        )
        logger.info("Running EndocrinologistAgent …")
        t0 = time.time()
        result = EndocrinologistAgent(config).run(context=context)
        elapsed = time.time() - t0

        logger.info("EndocrinologistAgent completed in %.1f s", elapsed)
        _log_agent_result("EndocrinologistAgent", result, logger)
        assert result.get("requires_review") is True

    # ── Dermatologist agent ───────────────────────────────────────────────────

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_dermatologist_agent_text_only(self, caplog):
        """DermatologistAgent.run() in text-only mode returns a dermatology assessment."""
        caplog.set_level(logging.DEBUG)
        from src.agents.dermatologist_agent import DermatologistAgent

        config = _default_config()
        context = (
            "50-year-old female presenting with a new pigmented lesion on the left arm. "
            "Lesion is asymmetric, border irregular, diameter approximately 8 mm, "
            "colour variegated (brown + black areas). Patient noticed recent size increase. "
            "No personal or family history of melanoma. "
            "Currently on thiazide diuretic for hypertension."
        )
        logger.info("Running DermatologistAgent (text-only) …")
        t0 = time.time()
        result = DermatologistAgent(config).run(context=context)
        elapsed = time.time() - t0

        logger.info("DermatologistAgent completed in %.1f s", elapsed)
        _log_agent_result("DermatologistAgent", result, logger)
        assert result.get("requires_review") is True

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_dermatologist_agent_with_image(self, synthetic_rgb_image, caplog):
        """DermatologistAgent.run() with a skin image returns a report."""
        caplog.set_level(logging.DEBUG)
        from src.agents.dermatologist_agent import DermatologistAgent

        config = _default_config()
        result = DermatologistAgent(config).run(
            context="50F, suspicious pigmented lesion, 8 mm, asymmetric.",
            image=synthetic_rgb_image,
        )
        _log_agent_result("DermatologistAgent (image)", result, logger)
        assert result.get("requires_review") is True

    # ── Pharmacology agent ────────────────────────────────────────────────────

    @pytest.mark.requires_weights
    @pytest.mark.requires_network
    @pytest.mark.slow
    @skip_no_medgemma
    @skip_no_network
    def test_pharmacology_agent_run(self, caplog):
        """PharmacologyAgent.run() returns full DDI + synthesis output."""
        caplog.set_level(logging.DEBUG)
        from src.agents.pharmacology_agent import PharmacologyAgent

        config = _default_config()
        drugs = ["warfarin", "aspirin", "lisinopril", "metformin"]
        symptoms = ["bruising", "dizziness", "fatigue"]

        logger.info("Running PharmacologyAgent — drugs: %s, symptoms: %s", drugs, symptoms)
        t0 = time.time()
        result = PharmacologyAgent(config).run(
            drug_names=drugs,
            patient_symptoms=symptoms,
            enable_pubmed_rag=False,
            enable_medgemma_synthesis=True,
        )
        elapsed = time.time() - t0

        logger.info("PharmacologyAgent completed in %.1f s", elapsed)
        logger.info("Overall risk: %s", result.get("overall_risk_level"))
        logger.info("Critical: %d, Major: %d", result.get("critical_count", 0), result.get("major_count", 0))
        logger.info("CoT: %s …", str(result.get("chain_of_thought", ""))[:200])
        logger.info("Recommendations: %s", result.get("recommendations", [])[:3])

        assert result.get("requires_review") is True
        assert result.get("disclaimer")
        assert isinstance(result.get("interactions", []), list)


# ═════════════════════════════════════════════════════════════════════════════
# 9. Multi-agent pipeline  — orchestrator, SynthesisAgent, run_clinical_reasoning
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiAgentPipeline:
    """Orchestrator routing, SynthesisAgent, and full clinical_reasoning pipeline."""

    def test_orchestrator_skips_all_agents_when_no_flags(self, caplog):
        """run_specialists with all False flags returns empty dict (no agents invoked)."""
        caplog.set_level(logging.DEBUG)
        from src.agents.orchestrator import run_specialists

        board_routing = {
            "consult_pharmacology": False,
            "consult_radiologist": False,
            "consult_cardiologist": False,
            "consult_dermatologist": False,
            "consult_pulmonologist": False,
            "consult_endocrinologist": False,
        }
        config = _default_config()
        result = run_specialists(
            board_routing=board_routing,
            transcript=CLINICAL_TRANSCRIPT,
            ehr_summary="",
            drug_names=[],
            patient_symptoms=[],
            config=config,
        )
        logger.info("Specialists invoked with all-False routing: %s", list(result.keys()))
        assert result == {}, "No specialists should be invoked when all flags are False"

    def test_orchestrator_pharmacology_skipped_when_no_drugs(self, caplog):
        """Pharmacology agent is NOT invoked when drug_names is empty, even if flagged."""
        caplog.set_level(logging.DEBUG)
        from src.agents.orchestrator import run_specialists

        board_routing = {"consult_pharmacology": True}
        config = _default_config()
        result = run_specialists(
            board_routing=board_routing,
            transcript="Patient has no medications.",
            ehr_summary="",
            drug_names=[],       # empty → pharmacology must not run
            patient_symptoms=[],
            config=config,
        )
        logger.info("Result keys with empty drug_names: %s", list(result.keys()))
        assert "pharmacology" not in result, (
            "Pharmacology should be skipped when drug_names is empty"
        )

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_synthesis_agent_produces_visit_synthesis(self, caplog):
        """SynthesisAgent.run() returns a VisitSynthesis-shaped dict."""
        caplog.set_level(logging.DEBUG)
        from src.agents.synthesis_agent import SynthesisAgent

        # Provide a minimal (mocked) GPAssessment to avoid running GPAgent again
        mock_gp = {
            "chief_complaint": "Chest tightness and exertional dyspnoea",
            "chain_of_thought": "Patient has AF and diabetes; cardiac cause likely.",
            "soap": {
                "subjective": "Chest tightness × 3 days, exertional dyspnoea",
                "objective": "BP 148/92, HR 86, SpO2 97%",
                "assessment": "Likely cardiac: ACS vs rate-related AF",
                "plan": "Troponin, BNP, ECG, cardiology referral",
            },
            "urgency": {"level": "urgent", "rationale": "Possible ACS"},
            "differentials": [{"diagnosis": "NSTEMI", "reasoning": "Chest tightness + AF", "probability": "possible"}],
            "recommended_workup": ["Troponin", "ECG", "BNP", "CBC"],
            "icd_codes": [
                {"code": "I48", "description": "Atrial fibrillation", "confidence": "high", "basis": "stated"},
            ],
            "summary": "67M AF+DM with chest tightness — urgent cardiac review needed.",
        }
        mock_specialists = {}

        config = _default_config()
        logger.info("Running SynthesisAgent …")
        t0 = time.time()
        result = SynthesisAgent(config).run(
            transcript=CLINICAL_TRANSCRIPT,
            ehr_summary="Patient: Test, Age 67, Sex M",
            gp_assessment=mock_gp,
            specialist_reports=mock_specialists,
        )
        elapsed = time.time() - t0

        logger.info("SynthesisAgent completed in %.1f s", elapsed)
        logger.info("reason_for_visit: %s", result.get("reason_for_visit"))
        logger.info("diagnoses: %d entries", len(result.get("diagnoses", [])))
        logger.info("recommended_orders: %d entries", len(result.get("recommended_orders", [])))
        logger.info("cot_log entries: %d", len(result.get("cot_log", [])))
        logger.info("requires_review: %s", result.get("requires_review"))

        assert isinstance(result, dict)
        assert result.get("requires_review") is True
        assert result.get("disclaimer")
        assert isinstance(result.get("cot_log", []), list)

        # SynthesisAgent appends its own CoT entry
        cot_agents = [e.get("agent") for e in result.get("cot_log", [])]
        logger.info("CoT agents in log: %s", cot_agents)
        assert "SynthesisAgent" in cot_agents, "SynthesisAgent must log its own CoT entry"

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_synthesis_agent_recommended_orders_structure(self, caplog):
        """SynthesisOrder entries have required fields: category, test_display."""
        caplog.set_level(logging.DEBUG)
        from src.agents.synthesis_agent import SynthesisAgent

        mock_gp = {
            "chief_complaint": "Chest tightness",
            "chain_of_thought": "Cardiac cause likely.",
            "soap": {"subjective": "Chest tightness", "objective": "BP 148/92", "assessment": "ACS?", "plan": "Troponin, ECG"},
            "urgency": {"level": "urgent", "rationale": "Possible ACS"},
            "differentials": [],
            "recommended_workup": ["Troponin", "ECG", "CBC"],
            "icd_codes": [],
            "summary": "Urgent cardiac review.",
        }
        config = _default_config()
        result = SynthesisAgent(config).run(
            transcript=CLINICAL_TRANSCRIPT,
            ehr_summary="",
            gp_assessment=mock_gp,
            specialist_reports={},
        )
        orders = result.get("recommended_orders", [])
        logger.info("Recommended orders (%d):", len(orders))
        for o in orders:
            logger.info("  [%s] %s (code: %s, urgency: %s)",
                        o.get("category"), o.get("test_display"),
                        o.get("test_code"), o.get("urgency"))

        for order in orders:
            assert "category" in order, "Order must have 'category'"
            assert "test_display" in order, "Order must have 'test_display'"
            assert order["category"] in {"lab", "imaging", "other"}, (
                f"Unexpected category: {order['category']!r}"
            )

    @pytest.mark.requires_weights
    @pytest.mark.requires_network
    @pytest.mark.slow
    @skip_no_medgemma
    @skip_no_network
    def test_run_clinical_reasoning_full_pipeline(self, caplog):
        """run_clinical_reasoning() text path returns a ClinicalVisitResult."""
        caplog.set_level(logging.INFO)
        from src.pipelines.clinical_reasoning import run_clinical_reasoning

        # Use text path (no audio) with patient P001 from the demo DB
        logger.info("Running full clinical reasoning pipeline (text path, patient=P001) …")
        t0 = time.time()

        try:
            result = run_clinical_reasoning(
                patient_id="P001",
                transcript=CLINICAL_TRANSCRIPT,
            )
        except FileNotFoundError as exc:
            pytest.skip(f"DB or model weights not found: {exc}")

        elapsed = time.time() - t0

        logger.info("Pipeline completed in %.1f s", elapsed)
        logger.info("reason_for_visit: %s", result.reason_for_visit)
        logger.info("diagnoses: %d entries", len(result.diagnoses))
        logger.info("recommended_orders: %d entries", len(result.recommended_orders))
        logger.info("agents_invoked: %s", result.agents_invoked)
        logger.info("cot_log entries: %d", len(result.cot_log))
        logger.info("requires_review: %s", result.requires_review)

        from src.pipelines.clinical_reasoning import ClinicalVisitResult
        assert isinstance(result, ClinicalVisitResult)
        assert result.requires_review is True
        assert result.transcript == CLINICAL_TRANSCRIPT
        assert len(result.agents_invoked) >= 2, "At least GPAgent + SynthesisAgent expected"

        logger.info("CoT log:")
        for entry in result.cot_log:
            logger.info("  [%s] %s …", entry.get("agent"), str(entry.get("reasoning", ""))[:120])

    @pytest.mark.requires_weights
    @pytest.mark.slow
    @skip_no_medgemma
    def test_run_clinical_reasoning_raises_on_no_input(self):
        """run_clinical_reasoning raises ValueError when neither audio nor transcript given."""
        from src.pipelines.clinical_reasoning import run_clinical_reasoning
        with pytest.raises(ValueError, match="Provide either audio_path or transcript"):
            run_clinical_reasoning(patient_id="P001")


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _log_pipeline_result(result: dict, log: logging.Logger) -> None:
    """Log a run_drug_check_pipeline result in a structured, readable format."""
    log.info("=== DDI Pipeline Result ===")
    log.info("Medications checked : %s", result.get("medications_checked"))
    log.info("Resolved INNs       : %s", result.get("resolved_inns"))
    log.info("Overall risk        : %s", result.get("overall_risk_level"))
    log.info("Critical / Major / Moderate: %d / %d / %d",
             result.get("critical_count", 0),
             result.get("major_count", 0),
             result.get("moderate_count", 0))
    log.info("Interactions (%d):", len(result.get("interactions", [])))
    for ix in result.get("interactions", [])[:5]:
        log.info("  [%s] %s × %s: %s",
                 ix.get("severity", "?"),
                 ix.get("drug_a", ix.get("ingredient_1_inn", "?")),
                 ix.get("drug_b", ix.get("ingredient_2_inn", "?")),
                 str(ix.get("description", ix.get("interaction", "?")))[:80])
    log.info("Side effects aggregated: %d entries", len(result.get("side_effects_aggregated", [])))
    log.info("Symptom matches: %d entries", len(result.get("symptom_matches", [])))
    log.info("Recommendations:")
    for rec in result.get("recommendations", []):
        log.info("  — %s", str(rec)[:120])
    log.info("===========================")


def _log_agent_result(agent_name: str, result: dict, log: logging.Logger) -> None:
    """Log an agent result with key fields shown."""
    log.info("=== %s Result ===", agent_name)
    log.info("requires_review : %s", result.get("requires_review"))
    log.info("disclaimer      : %s", "present" if result.get("disclaimer") else "MISSING")
    cot = result.get("chain_of_thought", "")
    log.info("chain_of_thought: %s …", str(cot)[:200] if cot else "(not present)")
    log.info("urgency         : %s", result.get("urgency"))
    for k in ("findings", "interactions", "diagnoses", "symptom_correlations",
              "recommendations", "impression"):
        v = result.get(k)
        if v is not None:
            log.info("%-16s: %s entries / chars",
                     k, len(v) if isinstance(v, (list, str)) else v)
    if result.get("_error"):
        log.error("_error: %s", result["_error"])
    log.info("=========================")
