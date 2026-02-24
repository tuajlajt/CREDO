"""
Histopathology / Whole Slide Image (WSI) preprocessing.

Tiles WSI into patches, filters background regions using Otsu thresholding.
Prepared patches feed into Path Foundation (google/path-foundation).

Supported: FFPE H&E stained slides, TIFF/SVS formats.
NOT supported: frozen sections, IHC without specific fine-tuning.

Recommended patch size: 224x224 at 20x magnification.

Owner agent: medical-cv-agent
Config: configs/default.yaml → preprocessing.pathology
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def extract_patches(
    wsi_path: str,
    patch_size: int = 224,
    level: int = 0,
    stride: int = 224,
    tissue_threshold: float = 0.5,
) -> list[Image.Image]:
    """
    Extract tissue patches from a whole slide image.
    Filters out background (white) regions using Otsu thresholding.
    Requires openslide-python.
    Returns list of PIL Images (RGB, patch_size x patch_size).
    """
    # TODO: implement — see medical-cv-agent.md for reference code
    raise NotImplementedError


def is_tissue(patch: Image.Image, threshold: float = 0.5) -> bool:
    """
    Return True if patch contains enough tissue (not background).
    Uses Otsu thresholding on greyscale image.
    Requires opencv-python.
    """
    # TODO: implement — see medical-cv-agent.md for reference code
    raise NotImplementedError
