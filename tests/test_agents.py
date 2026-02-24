"""
Tests for clinical AI agents.

Verifies agent interfaces and safety constraints without running real models.
Tests that requires_review=True is enforced and disclaimers are present.

Owner agent: test-engineer
"""
import pytest


class TestAgentModuleStructure:
    """Verify all clinical agents are importable and expose expected classes."""

    def test_gp_agent_importable(self):
        from src.agents.gp_agent import GPAgent, GPInput, GPOutput, DISCLAIMER
        assert GPAgent is not None
        assert "clinical judgement" in DISCLAIMER.lower()

    def test_radiologist_agent_importable(self):
        from src.agents.radiologist_agent import (
            RadiologistAgent, RadiologyReport, DISCLAIMER, CRITICAL_FINDINGS
        )
        assert len(CRITICAL_FINDINGS) > 0
        assert "tension pneumothorax" in CRITICAL_FINDINGS

    def test_dermatologist_agent_importable(self):
        from src.agents.dermatologist_agent import DermatologistAgent, DermatologyAssessment

    def test_pathologist_agent_importable(self):
        from src.agents.pathologist_agent import PathologistAgent, PathologyReport

    def test_pharmacology_agent_importable(self):
        from src.agents.pharmacology_agent import (
            PharmacologyAgent, PharmacologyReport, DISCLAIMER
        )
        assert "pharmacist" in DISCLAIMER.lower()


class TestRequiresReviewDefault:
    """Verify that output dataclasses default to requires_review=True."""

    def test_gp_output_requires_review_default(self):
        from src.agents.gp_agent import GPOutput
        output = GPOutput(
            urgency="routine",
            differentials=[],
            recommended_workup=[],
            referral_recommendation=None,
            raw_response="test",
        )
        assert output.requires_review is True

    def test_radiology_report_requires_review_default(self):
        from src.agents.radiologist_agent import RadiologyReport
        report = RadiologyReport(
            modality="CXR",
            technique="PA",
            findings="Normal",
            impression="No acute findings",
            critical_findings=[],
        )
        assert report.requires_review is True

    def test_dermatology_assessment_requires_review_default(self):
        from src.agents.dermatologist_agent import DermatologyAssessment
        assessment = DermatologyAssessment(
            primary_finding="test",
            differential_diagnoses=[],
            lesion_characteristics={},
            urgency="routine",
            recommendation="follow-up",
        )
        assert assessment.requires_review is True

    def test_pathology_report_requires_review_default(self):
        from src.agents.pathologist_agent import PathologyReport
        report = PathologyReport(
            specimen_type="skin",
            tissue_assessment="test",
            malignancy_indicator="benign",
            grade=None,
            margin_status=None,
            additional_findings=[],
        )
        assert report.requires_review is True

    def test_pharmacology_report_requires_review_default(self):
        from src.agents.pharmacology_agent import PharmacologyReport
        report = PharmacologyReport(
            drugs_checked=[],
            interactions=[],
            major_interactions=[],
            recommendations=[],
            alternatives={},
            database_version="test",
        )
        assert report.requires_review is True


class TestCriticalFindingsDetection:
    def test_detects_tension_pneumothorax(self):
        from src.agents.radiologist_agent import RadiologistAgent
        agent = RadiologistAgent({})
        findings = "There is evidence of tension pneumothorax on the left side."
        critical = agent._check_critical_findings(findings)
        assert "tension pneumothorax" in critical

    def test_no_false_positive_on_normal(self):
        from src.agents.radiologist_agent import RadiologistAgent
        agent = RadiologistAgent({})
        findings = "Lungs are clear. Heart size is normal. No acute findings."
        critical = agent._check_critical_findings(findings)
        assert len(critical) == 0
