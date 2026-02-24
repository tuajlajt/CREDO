"""
Medical imaging augmentation policies.

CRITICAL: Not all augmentations are valid for medical images.
Wrong augmentations destroy diagnostic information.

Per-modality policies defined below. Never apply augmentations from one modality
to another.

Augmentation rules by modality:
  CXR:         horizontal flip OK, mild rotation/shift OK, NO colour jitter
  Pathology:   horizontal + vertical flip OK, rotate OK, mild colour jitter OK
  CT volumes:  NO horizontal flip (sidedness is diagnostic), NO colour augmentation
  Skin:        mild colour jitter OK, flip OK, mild rotation OK

Owner agent: medical-cv-agent
Config: configs/default.yaml → preprocessing.[modality]
"""
from __future__ import annotations


def get_cxr_augmentation():
    """
    Safe augmentation pipeline for chest X-rays.
    Requires albumentations.
    Returns albumentations.Compose object.
    """
    # TODO: implement — see medical-cv-agent.md for reference code
    # Safe: HorizontalFlip, mild ShiftScaleRotate, mild GridDistortion, GaussianBlur
    # FORBIDDEN: ColorJitter, Hue/Saturation changes, aggressive contrast
    raise NotImplementedError


def get_pathology_augmentation():
    """
    Safe augmentation pipeline for histopathology patches.
    Requires albumentations.
    Returns albumentations.Compose object.
    """
    # TODO: implement — see medical-cv-agent.md for reference code
    # Safe: HorizontalFlip, VerticalFlip, RandomRotate90, mild ColorJitter, GaussianBlur
    raise NotImplementedError


def get_skin_augmentation():
    """
    Safe augmentation pipeline for dermoscopy / skin images.
    Requires albumentations.
    Returns albumentations.Compose object.
    """
    # TODO: implement
    raise NotImplementedError
