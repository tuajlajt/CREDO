"""
Chest X-ray preprocessing pipeline.

Converts DICOM CXR to normalised float32 tensors suitable for:
- CXR Foundation (google/cxr-foundation)
- MedGemma 4B (google/medgemma-4b-it)
- MedSigLIP (google/medsiglip-so400m-patch14-384)

IMPORTANT: Call medical-data-engineer de-identification BEFORE this module.
Never receive raw DICOM with PHI tags present.

Owner agent: medical-cv-agent
Config: configs/default.yaml → preprocessing.cxr
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def preprocess_cxr(
    dicom_path: str,
    target_size: tuple = (224, 224),
) -> np.ndarray:
    """
    Standard CXR preprocessing.
    - Applies DICOM rescale slope/intercept
    - Inverts MONOCHROME1 images
    - Percentile normalisation (robust to outliers)
    - Resizes to target_size
    Returns float32 array normalised to [0, 1].
    """
    # TODO: implement — see medical-cv-agent.md for reference code
    # Requires: pydicom, PIL
    raise NotImplementedError


def check_cxr_quality(pixel_array: np.ndarray) -> dict:
    """
    Automated quality control checks on a CXR pixel array.
    Returns dict: {passed: bool, issues: list[str]}
    Flags: extreme mean pixel value, very low contrast.
    """
    issues = []
    if pixel_array.mean() < 0.05 or pixel_array.mean() > 0.95:
        issues.append("Extreme mean pixel value — possible over/underexposed image")
    if pixel_array.std() < 0.05:
        issues.append("Very low contrast — possible blank or nearly blank image")
    return {"passed": len(issues) == 0, "issues": issues}
