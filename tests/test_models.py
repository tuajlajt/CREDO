"""
Tests for HAI-DEF model wrapper modules.

These tests verify module structure and interfaces without loading real models.
Real model tests require GPU and downloaded weights — run separately in CI with --run-model-tests.

Owner agent: test-engineer
"""
import pytest


class TestModelModuleStructure:
    """Verify that all model wrapper modules exist and expose the expected interface."""

    def test_medgemma_inference_importable(self):
        from src.models.medgemma import inference
        assert hasattr(inference, "load_medgemma")
        assert hasattr(inference, "analyze_medical_image")
        assert hasattr(inference, "run_text_inference")
        assert hasattr(inference, "generate_radiology_report")

    def test_medasr_inference_importable(self):
        from src.models.medasr import inference
        assert hasattr(inference, "transcribe_medical_audio")

    def test_medasr_preprocessing_importable(self):
        from src.models.medasr import preprocessing
        assert hasattr(preprocessing, "prepare_for_medasr")
        assert hasattr(preprocessing, "chunk_long_audio")

    def test_cxr_foundation_importable(self):
        from src.models.cxr_foundation import embeddings
        assert hasattr(embeddings, "load_cxr_foundation")
        assert hasattr(embeddings, "embed_cxr")

    def test_derm_foundation_importable(self):
        from src.models.derm_foundation import embeddings
        assert hasattr(embeddings, "embed_skin_image")

    def test_path_foundation_importable(self):
        from src.models.path_foundation import embeddings
        assert hasattr(embeddings, "embed_patch")
        assert hasattr(embeddings, "embed_whole_slide")

    def test_medsiglip_importable(self):
        from src.models.medsiglip import embeddings
        assert hasattr(embeddings, "embed_image")
        assert hasattr(embeddings, "embed_text")
        assert hasattr(embeddings, "zero_shot_classify")

    def test_hear_importable(self):
        from src.models.hear import embeddings
        assert hasattr(embeddings, "embed_health_audio")

    def test_ct_foundation_importable(self):
        from src.models.ct_foundation import embeddings
        assert hasattr(embeddings, "embed_ct_volume")
        assert hasattr(embeddings, "normalise_hu")

    def test_txgemma_importable(self):
        from src.models.txgemma import inference
        assert hasattr(inference, "predict_toxicity")
        assert hasattr(inference, "predict_bbb")


class TestHUNormalisation:
    """normalise_hu is pure numpy — can test without GPU."""

    def test_normalise_hu_range(self):
        import numpy as np
        from src.models.ct_foundation.embeddings import normalise_hu
        volume = np.linspace(-1000, 3000, 100).reshape(10, 10)
        result = normalise_hu(volume, window_center=40, window_width=400)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_normalise_hu_clipping(self):
        import numpy as np
        from src.models.ct_foundation.embeddings import normalise_hu
        volume = np.array([-2000.0, 0.0, 40.0, 5000.0])
        result = normalise_hu(volume, window_center=40, window_width=400)
        assert result[0] == 0.0   # below window → 0
        assert result[-1] == 1.0  # above window → 1
