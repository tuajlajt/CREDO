"""
Image quality control checks.

Automated QC before batch inference — never run a model on a bad image silently.

Owner agent: medical-cv-agent
"""
from __future__ import annotations

import numpy as np


def check_cxr_quality(pixel_array: np.ndarray) -> dict:
    """
    Automated CXR quality checks.
    Returns {passed: bool, issues: list[str]}
    """
    issues = []
    if pixel_array.mean() < 0.05 or pixel_array.mean() > 0.95:
        issues.append("Extreme mean pixel value — possible over/underexposed image")
    if pixel_array.std() < 0.05:
        issues.append("Very low contrast — possible blank image")
    return {"passed": len(issues) == 0, "issues": issues}


def check_ct_volume_quality(volume: np.ndarray) -> dict:
    """
    Basic CT volume QC.
    Returns {passed: bool, issues: list[str]}
    """
    issues = []
    if volume.ndim != 3:
        issues.append(f"Expected 3D volume, got {volume.ndim}D")
    if volume.shape[0] < 10:
        issues.append(f"Very few slices ({volume.shape[0]}) — may be incomplete series")
    return {"passed": len(issues) == 0, "issues": issues}


def check_audio_quality(waveform: np.ndarray, sample_rate: int) -> dict:
    """
    Basic audio QC for MedASR input.
    Returns {passed: bool, issues: list[str]}
    """
    issues = []
    if sample_rate != 16000:
        issues.append(f"Wrong sample rate: {sample_rate}Hz (MedASR requires 16000Hz)")
    if waveform.ndim != 1:
        issues.append("Expected mono audio (1D array)")
    if len(waveform) == 0:
        issues.append("Empty audio waveform")
    if np.abs(waveform).max() < 0.001:
        issues.append("Near-silent audio — possible recording failure")
    return {"passed": len(issues) == 0, "issues": issues}
