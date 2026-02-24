"""
EHR record validator.

Loads src/data/schema/ehr.yaml and validates patient JSON dicts against it
using jsonschema.Draft202012Validator.

Usage:
    from src.data.ehr_validator import validate, validate_strict, validate_file

    errors = validate(patient_dict)        # returns list of error strings
    validate_strict(patient_dict)          # raises ValidationError on first error
    errors = validate_file("P001.json")    # load + validate a file
    results = validate_directory("data/synthetic/patients/")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import jsonschema
import yaml

_SCHEMA_PATH = Path(__file__).parent / "schema" / "ehr.yaml"
_schema: dict | None = None


def _load_schema() -> dict:
    global _schema
    if _schema is None:
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            _schema = yaml.safe_load(fh)
    return _schema


def validate(record: dict) -> list[str]:
    """
    Validate a patient EHR dict against the schema.
    Returns a list of human-readable error strings.
    An empty list means the record is valid.
    """
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(record), key=lambda e: str(e.absolute_path))
    return [
        "{}: {}".format(
            " -> ".join(str(p) for p in e.absolute_path) or "<root>",
            e.message,
        )
        for e in errors
    ]


def validate_strict(record: dict) -> None:
    """
    Validate a patient EHR dict and raise jsonschema.ValidationError on the
    first error found.  Use this in contexts that want an exception rather than
    an error list (e.g. pipeline ingestion guards).
    """
    schema = _load_schema()
    jsonschema.validate(
        instance=record,
        schema=schema,
        cls=jsonschema.Draft202012Validator,
    )


def validate_file(path: Union[str, Path]) -> list[str]:
    """
    Load a JSON file from *path* and validate it.
    Returns a list of error strings (empty = valid).
    """
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    return validate(record)


def validate_directory(
    directory: Union[str, Path],
    *,
    verbose: bool = True,
) -> dict[str, list[str]]:
    """
    Validate all *.json files in *directory*.

    Returns a dict mapping filename → list of error strings.
    Files with no errors map to an empty list.
    Prints a summary when verbose=True (default).
    """
    directory = Path(directory)
    results: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.json")):
        errors = validate_file(path)
        results[path.name] = errors
        if verbose:
            status = "OK" if not errors else f"FAIL ({len(errors)} error(s))"
            print(f"  {path.name}: {status}")
            for err in errors:
                print(f"    - {err}")
    if verbose:
        n_ok = sum(1 for e in results.values() if not e)
        n_fail = len(results) - n_ok
        print(f"\n{n_ok}/{len(results)} valid, {n_fail} invalid")
    return results
