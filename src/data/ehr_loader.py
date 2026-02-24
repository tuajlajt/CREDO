"""
EHR patient record loader.

Loads patient JSON files from data/synthetic/patients/ (or a configurable path).
All records are plain Python dicts that conform to the ehr.yaml schema.

Default search directory is resolved relative to this file's location:
    <project_root>/data/synthetic/patients/

Usage:
    from src.data.ehr_loader import load_patient, load_all, iter_patients, get_patient_by_id

    record  = load_patient("data/synthetic/patients/P001.json")
    records = load_all()                          # all patients, no validation
    records = load_all(validate=True)             # validate each; raise on error
    records = load_all(validate=True, skip_invalid=True)  # skip bad records

    for record in iter_patients(validate=True):
        process(record)

    record = get_patient_by_id("P005")           # search by patient_id
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Optional, Union

from src.data.ehr_validator import validate as _validate_record

_DEFAULT_DIR = Path(__file__).parent.parent.parent / "data" / "synthetic" / "patients"


def load_patient(
    path: Union[str, Path],
    *,
    validate: bool = False,
) -> dict:
    """
    Load a single patient EHR JSON file from *path*.
    If validate=True, raises ValueError with all schema errors if the record
    is invalid.
    """
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    if validate:
        errors = _validate_record(record)
        if errors:
            raise ValueError(
                f"EHR validation failed for {path}:\n" + "\n".join(errors)
            )
    return record


def load_all(
    directory: Optional[Union[str, Path]] = None,
    *,
    validate: bool = False,
    skip_invalid: bool = False,
) -> list[dict]:
    """
    Load all *.json files from *directory* (default: data/synthetic/patients/).

    validate     – validate each record against the schema
    skip_invalid – if True and validate=True, log and skip invalid records
                   instead of raising
    """
    directory = Path(directory) if directory is not None else _DEFAULT_DIR
    records: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        if validate:
            errors = _validate_record(record)
            if errors:
                if skip_invalid:
                    print(f"[ehr_loader] Skipping invalid {path.name}: {errors[0]}")
                    continue
                raise ValueError(
                    f"EHR validation failed for {path.name}:\n" + "\n".join(errors)
                )
        records.append(record)
    return records


def iter_patients(
    directory: Optional[Union[str, Path]] = None,
    *,
    validate: bool = False,
) -> Iterator[dict]:
    """
    Yield patient EHR records one at a time from *directory*.
    If validate=True, raises ValueError before yielding any invalid record.
    """
    directory = Path(directory) if directory is not None else _DEFAULT_DIR
    for path in sorted(directory.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        if validate:
            errors = _validate_record(record)
            if errors:
                raise ValueError(
                    f"EHR validation failed for {path.name}:\n" + "\n".join(errors)
                )
        yield record


def get_patient_by_id(
    patient_id: str,
    directory: Optional[Union[str, Path]] = None,
) -> Optional[dict]:
    """
    Search *directory* for a patient record with the given patient_id.
    Returns the record dict, or None if not found.
    """
    directory = Path(directory) if directory is not None else _DEFAULT_DIR
    for path in sorted(directory.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        if record.get("patient_profile", {}).get("patient_id") == patient_id:
            return record
    return None
