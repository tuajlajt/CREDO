"""
Dermatology image preprocessing.

Prepares clinical skin images and dermoscopy images for:
- Derm Foundation (google/derm-foundation)
- MedGemma 4B (google/medgemma-4b-it)
- MedSigLIP

Uses ImageNet normalisation (Derm Foundation training distribution).

Pre-processing checklist:
1. Crop to lesion area of interest
2. Remove metadata overlays, scale markers, rulers
3. De-identify: ensure no visible patient-identifying features (face, tattoos)
4. Then call preprocess_skin_image()

Owner agent: medical-cv-agent
Config: configs/default.yaml → preprocessing.dermoscopy
"""
from __future__ import annotations

import numpy as np
from PIL import Image

# ImageNet normalisation constants (Derm Foundation training distribution)
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def preprocess_skin_image(
    image: Image.Image,
    target_size: tuple = (224, 224),
) -> np.ndarray:
    """
    Preprocess dermoscopy or clinical skin image.
    Resizes, converts to float, applies ImageNet normalisation.
    Returns float32 array of shape (H, W, 3).
    """
    image = image.convert("RGB").resize(target_size, Image.LANCZOS)
    arr = np.array(image).astype(np.float32) / 255.0
    mean = np.array(IMAGENET_MEAN)
    std = np.array(IMAGENET_STD)
    return (arr - mean) / std
