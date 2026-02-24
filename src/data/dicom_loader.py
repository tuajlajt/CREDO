"""
DICOM series loading and PHI de-identification.

Loads DICOM imaging data and strips all PHI tags before returning.
NEVER return data with PHI tags present — all downstream code assumes clean data.

PHI DICOM tags stripped (partial list — use a validated de-identification profile in production):
  (0010,0010) PatientName
  (0010,0020) PatientID
  (0010,0030) PatientBirthDate
  (0010,0040) PatientSex
  (0008,0080) InstitutionName
  (0008,1030) StudyDescription (may contain PHI)

For production: use a full DICOM de-identification profile (DICOM PS3.15 Annex E).

Owner agent: medical-data-engineer
"""
from __future__ import annotations

from pathlib import Path
import numpy as np


# PHI DICOM tags to strip (add to this list — never remove from it)
PHI_TAGS = [
    (0x0010, 0x0010),  # PatientName
    (0x0010, 0x0020),  # PatientID
    (0x0010, 0x0030),  # PatientBirthDate
    (0x0010, 0x0040),  # PatientSex
    (0x0008, 0x0080),  # InstitutionName
    (0x0008, 0x1030),  # StudyDescription
    (0x0008, 0x0090),  # ReferringPhysicianName
    (0x0008, 0x1048),  # PhysiciansOfRecord
    (0x0032, 0x1032),  # RequestingPhysician
    (0x0040, 0xA123),  # PersonName (in SR)
]


def load_dicom_series(series_dir: Path) -> dict:
    """
    Load a DICOM series. Strips all PHI tags before returning.

    Args:
        series_dir: Path to directory containing .dcm files

    Returns:
        dict with keys:
          pixels: np.ndarray of shape (slices, H, W) in HU
          metadata: safe (non-PHI) metadata dict
    """
    # TODO: implement — see medical-data-engineer.md for reference code
    # Requires: pydicom
    raise NotImplementedError


def extract_safe_metadata(ds) -> dict:
    """
    Extract only non-PHI DICOM metadata.
    Never include patient identifiers.
    """
    return {
        "modality": getattr(ds, "Modality", None),
        "rows": getattr(ds, "Rows", None),
        "columns": getattr(ds, "Columns", None),
        "pixel_spacing": getattr(ds, "PixelSpacing", None),
        "slice_thickness": getattr(ds, "SliceThickness", None),
        "kvp": getattr(ds, "KVP", None),
        "bits_allocated": getattr(ds, "BitsAllocated", None),
        "photometric_interpretation": getattr(ds, "PhotometricInterpretation", None),
    }


def validate_dicom_input(pixel_array: np.ndarray, metadata: dict) -> None:
    """
    Validate DICOM pixel array and metadata.
    Raises ValueError with clear message on failure.
    """
    if pixel_array.ndim not in [2, 3]:
        raise ValueError(f"Expected 2D or 3D pixel array, got {pixel_array.ndim}D")
    if pixel_array.dtype not in [np.uint8, np.uint16, np.int16, np.float32]:
        raise ValueError(f"Unexpected DICOM pixel dtype: {pixel_array.dtype}")
    if metadata.get("modality") is None:
        raise ValueError("Modality is required in DICOM metadata")
