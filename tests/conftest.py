"""
Test fixtures for MedGemma Medical AI tests.

CRITICAL: No real patient data in any fixture.
All test data is synthetic — generated, not derived from real cases.

Owner agent: test-engineer
"""
import sqlite3

import numpy as np
import pytest
from PIL import Image


# ── Database fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_conn() -> sqlite3.Connection:
    """
    SQLite connection to the demo database (data/synthetic/credo_demo.db).

    Session-scoped — one connection for the whole test session, read-only.
    Skips automatically if the database file has not been generated yet.

    Run first:  python scripts/seed_db.py
    """
    try:
        from src.data.db import get_connection
        conn = get_connection(row_factory=True)
        yield conn
        conn.close()
    except FileNotFoundError:
        pytest.skip("Demo database not found — run: python scripts/seed_db.py")


# ── Synthetic imaging fixtures ───────────────────────────────────────────────

@pytest.fixture
def synthetic_cxr_image() -> Image.Image:
    """224x224 grayscale synthetic chest X-ray (random noise — not real CXR)."""
    arr = np.random.randint(0, 255, (224, 224), dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


@pytest.fixture
def synthetic_skin_image() -> Image.Image:
    """224x224 RGB synthetic skin image (random noise — not real dermoscopy)."""
    arr = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def synthetic_ct_volume() -> np.ndarray:
    """
    Small synthetic CT volume (20 slices, 64x64) in Hounsfield Units.
    Values in [-1000, 3000] HU range (physiologically plausible range).
    """
    return np.random.randint(-1000, 3000, (20, 64, 64), dtype=np.int16)


@pytest.fixture
def synthetic_pathology_patch() -> Image.Image:
    """224x224 RGB synthetic H&E pathology patch."""
    arr = np.random.randint(150, 230, (224, 224, 3), dtype=np.uint8)  # Pinkish
    return Image.fromarray(arr, mode="RGB")


# ── Synthetic audio fixtures ─────────────────────────────────────────────────

@pytest.fixture
def synthetic_audio_waveform() -> dict:
    """2-second synthetic audio at 16kHz (sine wave — not real clinical audio)."""
    t = np.linspace(0, 2.0, 32000, dtype=np.float32)
    waveform = np.sin(2 * np.pi * 440 * t) * 0.5
    return {"waveform": waveform, "sample_rate": 16000, "duration_seconds": 2.0}


# ── Synthetic clinical data fixtures ─────────────────────────────────────────

@pytest.fixture
def synthetic_gp_input() -> dict:
    """Synthetic GP agent input — no real patient data."""
    return {
        "chief_complaint": "Persistent dry cough for 2 weeks",
        "history": "No relevant past medical history. Non-smoker.",
        "vitals": {"bp": "120/78", "hr": "72", "temp": "36.8", "spo2": "98"},
        "medications": ["Vitamin D 1000IU"],
        "allergies": ["Penicillin"],
        "age": 35,
        "sex": "F",
    }


@pytest.fixture
def synthetic_drug_list() -> list[str]:
    """Synthetic medication list for pharmacology agent tests."""
    return ["Warfarin", "Aspirin", "Lisinopril"]


# ── DICOM metadata fixture ───────────────────────────────────────────────────

@pytest.fixture
def synthetic_dicom_metadata() -> dict:
    """Safe (non-PHI) DICOM metadata for testing."""
    return {
        "modality": "CR",
        "rows": 2048,
        "columns": 2048,
        "pixel_spacing": [0.143, 0.143],
        "slice_thickness": None,
        "kvp": 120,
        "bits_allocated": 16,
        "photometric_interpretation": "MONOCHROME2",
    }
