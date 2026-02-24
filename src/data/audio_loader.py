"""
Clinical audio loading and preprocessing.

Loads audio files and resamples to MedASR requirements: 16kHz, mono.

De-identification note: audio files may contain patient name spoken aloud.
Run audio de-identification (speaker diarisation + name detection) before
passing to any model. This module handles FORMAT loading only, not de-identification.

Owner agent: medical-data-engineer
"""
from __future__ import annotations


def load_clinical_audio(path: str, target_sr: int = 16000) -> dict:
    """
    Load audio file and resample to target sample rate.
    MedASR expects 16kHz mono PCM.

    Args:
        path: Path to audio file (.wav, .mp3, .m4a, .flac supported)
        target_sr: Target sample rate (must be 16000 for MedASR)

    Returns:
        dict with keys: waveform (np.ndarray), sample_rate (int), duration_seconds (float)
    """
    # TODO: implement — see medical-data-engineer.md for reference code
    # Requires: librosa
    raise NotImplementedError


def validate_audio_input(audio: dict) -> None:
    """
    Validate audio dict for MedASR compatibility.
    Raises ValueError with clear message on failure.
    """
    if audio.get("sample_rate") != 16000:
        raise ValueError(
            f"MedASR requires 16kHz audio, got {audio.get('sample_rate')}Hz"
        )
    import numpy as np
    waveform = audio.get("waveform")
    if waveform is None or len(waveform) == 0:
        raise ValueError("Empty audio waveform")
    if waveform.ndim != 1:
        raise ValueError(f"Expected mono audio (1D), got {waveform.ndim}D")
