"""
Tests for data loading and de-identification modules.

All tests use synthetic data — no real patient data.

Owner agent: test-engineer, medical-data-engineer
"""
import numpy as np
import pytest

from src.data.text_loader import deidentify_text
from src.data.audio_loader import validate_audio_input
from src.data.dicom_loader import validate_dicom_input, extract_safe_metadata, PHI_TAGS


class TestTextDeidentification:
    def test_ssn_redacted(self):
        text = "Patient SSN: 123-45-6789"
        result = deidentify_text(text)
        assert "123-45-6789" not in result
        assert "[REDACTED]" in result

    def test_mrn_redacted(self):
        text = "MRN: 1234567 was reviewed"
        result = deidentify_text(text)
        assert "1234567" not in result

    def test_clean_text_unchanged(self):
        text = "Patient presents with productive cough and fever."
        result = deidentify_text(text)
        assert result == text

    def test_date_redacted(self):
        text = "Date of birth: 01/15/1990"
        result = deidentify_text(text)
        assert "1990" not in result or "[REDACTED]" in result


class TestAudioValidation:
    def test_valid_audio_passes(self, synthetic_audio_waveform):
        # Should not raise
        validate_audio_input(synthetic_audio_waveform)

    def test_wrong_sample_rate_raises(self, synthetic_audio_waveform):
        bad_audio = {**synthetic_audio_waveform, "sample_rate": 8000}
        with pytest.raises(ValueError, match="16000"):
            validate_audio_input(bad_audio)

    def test_empty_waveform_raises(self):
        bad_audio = {"waveform": np.array([]), "sample_rate": 16000}
        with pytest.raises(ValueError):
            validate_audio_input(bad_audio)

    def test_stereo_raises(self, synthetic_audio_waveform):
        bad_audio = {
            **synthetic_audio_waveform,
            "waveform": np.stack([
                synthetic_audio_waveform["waveform"],
                synthetic_audio_waveform["waveform"]
            ])
        }
        with pytest.raises(ValueError, match="mono"):
            validate_audio_input(bad_audio)


class TestDicomValidation:
    def test_valid_2d_array_passes(self, synthetic_dicom_metadata):
        pixel_array = np.zeros((512, 512), dtype=np.uint16)
        validate_dicom_input(pixel_array, synthetic_dicom_metadata)

    def test_valid_3d_array_passes(self, synthetic_dicom_metadata):
        pixel_array = np.zeros((64, 512, 512), dtype=np.int16)
        validate_dicom_input(pixel_array, synthetic_dicom_metadata)

    def test_1d_array_raises(self, synthetic_dicom_metadata):
        with pytest.raises(ValueError):
            validate_dicom_input(np.zeros(100), synthetic_dicom_metadata)

    def test_missing_modality_raises(self):
        pixel_array = np.zeros((512, 512), dtype=np.uint16)
        with pytest.raises(ValueError, match="Modality"):
            validate_dicom_input(pixel_array, {})

    def test_phi_tags_list_not_empty(self):
        """PHI tag list must not be emptied by accident."""
        assert len(PHI_TAGS) > 0, "PHI_TAGS list must contain tags to strip"

    def test_patient_name_tag_in_phi_list(self):
        """PatientName tag must always be in the PHI tags list."""
        assert (0x0010, 0x0010) in PHI_TAGS, "PatientName must be in PHI_TAGS"
