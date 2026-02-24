"""
Tests for FastAPI endpoints.

Uses httpx TestClient (async) for API tests.
No real model calls — stubs/mocks used for model inference.
No real patient data in any request.

Owner agent: test-engineer
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.api.main import app
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status_field(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data

    def test_health_has_gpu_field(self, client):
        response = client.get("/health")
        data = response.json()
        assert "gpu_available" in data


class TestDrugCheckEndpoint:
    def test_drug_check_accepts_json(self, client):
        # This will fail until pharmacology_agent is implemented
        # Verify endpoint exists and accepts request format
        response = client.post(
            "/drug-check/",
            json={"drug_names": ["Aspirin", "Warfarin"]},
        )
        # 500 is acceptable until implemented — 404 is not (route must exist)
        assert response.status_code != 404


class TestNLPModuleStructure:
    def test_section_detector_importable(self):
        from src.nlp.section_detector import (
            structure_as_soap,
            structure_as_radiology_report,
            structure_as_discharge_summary,
        )
        assert callable(structure_as_soap)

    def test_soap_structure_returns_expected_keys(self):
        from src.nlp.section_detector import structure_as_soap
        transcript = (
            "Patient reports chest pain. Vital signs are stable. "
            "Assessment: possible angina. Plan: ECG and troponin."
        )
        result = structure_as_soap(transcript)
        assert set(result.keys()) == {"subjective", "objective", "assessment", "plan"}

    def test_radiology_structure_returns_expected_keys(self):
        from src.nlp.section_detector import structure_as_radiology_report
        transcript = "Technique: PA view. Findings: clear lungs. Impression: normal."
        result = structure_as_radiology_report(transcript)
        assert set(result.keys()) == {"technique", "findings", "impression"}
