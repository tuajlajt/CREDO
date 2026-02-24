"""
CT volume preprocessing pipeline.

Loads DICOM CT series, resamples to isotropic spacing, applies HU windowing.
Produces normalised 3D numpy volumes for CT Foundation and MedGemma.

Window presets by anatomy:
  Soft tissue / abdomen: center=40,  width=400
  Lung:                  center=-600, width=1500
  Bone:                  center=700,  width=1000
  Brain:                 center=40,   width=80

IMPORTANT: Left-right flip is FORBIDDEN on CT — sidedness is diagnostic.
Colour augmentation is FORBIDDEN on CT — HU values carry physiological meaning.

Owner agent: medical-cv-agent
Config: configs/default.yaml → preprocessing.ct
"""
from __future__ import annotations

import numpy as np


def preprocess_ct_volume(
    series_dir: str,
    window_center: int = 40,
    window_width: int = 400,
    target_spacing: tuple = (1.0, 1.0, 1.0),
) -> np.ndarray:
    """
    Load, resample, and window a CT volume.
    Returns float32 array normalised to [0, 1].
    Requires SimpleITK.
    """
    # TODO: implement — see medical-cv-agent.md for reference code
    raise NotImplementedError


def resample_to_spacing(image, target_spacing: tuple = (1.0, 1.0, 1.0)):
    """
    Resample a SimpleITK image to isotropic voxel spacing.
    Uses linear interpolation.
    """
    # TODO: implement — see medical-cv-agent.md for reference code
    raise NotImplementedError
