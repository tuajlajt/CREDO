"""
SQLite database connection for CREDO demo.

Wraps the synthetic demo database at data/synthetic/credo_demo.db.
All 16 tables mirror src/data/schema/EHR.dbml exactly.

Usage:
    from src.data.db import get_connection, query_patient, list_patients

    # Raw SQL
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM patient_profile").fetchall()

    # Convenience helpers
    patient = query_patient("P005")
    worklist = list_patients()

Generate the database first:
    python scripts/seed_db.py
"""
from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import uuid
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "synthetic" / "credo_demo.db"


def _db_path() -> Path:
    env = os.environ.get("CREDO_DB_PATH")
    return Path(env) if env else _DEFAULT_DB_PATH


def get_connection(row_factory: bool = True) -> sqlite3.Connection:
    """
    Return a SQLite connection to the demo database.

    Args:
        row_factory: If True, rows are returned as sqlite3.Row objects
                     (accessible by column name). Set False for plain tuples.

    Returns:
        sqlite3.Connection with foreign_keys enabled.

    Raises:
        FileNotFoundError if the database file does not exist.
    """
    path = _db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Demo database not found at {path}. "
            "Run: python scripts/seed_db.py"
        )
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


# ── Convenience query helpers ──────────────────────────────────────────────────

def list_patients() -> List[dict]:
    """
    Return a summary list of all patients (worklist view).

    Returns list of dicts with: patient_id, given_names, family_name,
    date_of_birth, sex_at_birth, last_visit_date, condition_count, medication_count.
    """
    sql = """
        SELECT
            p.patient_id,
            p.given_names,
            p.family_name,
            p.date_of_birth,
            p.sex_at_birth,
            p.last_visit_date,
            COUNT(DISTINCT cc.condition_id)    AS condition_count,
            COUNT(DISTINCT rx.prescription_id) AS medication_count
        FROM patient_profile p
        LEFT JOIN chronic_condition cc ON cc.patient_id = p.patient_id
            AND cc.status = 'active'
        LEFT JOIN prescription rx ON rx.patient_id = p.patient_id
        GROUP BY p.patient_id
        ORDER BY p.family_name, p.given_names
    """
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def query_patient(patient_id: str) -> Optional[dict]:
    """
    Return the full EHR record for a patient as a nested dict.

    Returns None if patient not found.
    """
    with get_connection() as conn:
        profile = conn.execute(
            "SELECT * FROM patient_profile WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if not profile:
            return None

        conditions = conn.execute(
            "SELECT * FROM chronic_condition WHERE patient_id = ? ORDER BY onset_date DESC",
            (patient_id,)
        ).fetchall()

        medications = conn.execute(
            "SELECT * FROM prescription WHERE patient_id = ? ORDER BY prescribed_date DESC",
            (patient_id,)
        ).fetchall()

        allergies = conn.execute(
            "SELECT * FROM allergy WHERE patient_id = ?", (patient_id,)
        ).fetchall()

        vitals = conn.execute(
            "SELECT * FROM vitals WHERE patient_id = ? ORDER BY measured_at DESC LIMIT 10",
            (patient_id,)
        ).fetchall()

        visits = conn.execute(
            "SELECT * FROM visit WHERE patient_id = ? ORDER BY visit_date DESC",
            (patient_id,)
        ).fetchall()

        family_hx = conn.execute(
            "SELECT * FROM family_history WHERE patient_id = ?", (patient_id,)
        ).fetchall()

        lifestyle = conn.execute(
            "SELECT * FROM lifestyle WHERE patient_id = ?", (patient_id,)
        ).fetchone()

        lab_results = conn.execute(
            "SELECT * FROM lab_result WHERE patient_id = ? ORDER BY measured_at DESC LIMIT 20",
            (patient_id,)
        ).fetchall()

        imaging = conn.execute(
            "SELECT * FROM imaging_study WHERE patient_id = ? ORDER BY performed_at DESC",
            (patient_id,)
        ).fetchall()

    return {
        "profile":        dict(profile),
        "conditions":     [dict(r) for r in conditions],
        "medications":    [dict(r) for r in medications],
        "allergies":      [dict(r) for r in allergies],
        "vitals":         [dict(r) for r in vitals],
        "visits":         [dict(r) for r in visits],
        "family_history": [dict(r) for r in family_hx],
        "lifestyle":      dict(lifestyle) if lifestyle else {},
        "lab_results":    [dict(r) for r in lab_results],
        "imaging":        [dict(r) for r in imaging],
    }


def get_active_medications(patient_id: str) -> List[str]:
    """
    Return the list of active medication INNs for a patient.

    Useful for passing directly to the pharmacology agent DDI check.
    """
    sql = """
        SELECT DISTINCT inn FROM prescription
        WHERE patient_id = ?
        ORDER BY inn
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (patient_id,)).fetchall()
    return [r["inn"] for r in rows]


def get_visit_with_diagnoses(visit_id: str) -> Optional[dict]:
    """Return a visit record with its diagnoses."""
    with get_connection() as conn:
        visit = conn.execute(
            "SELECT * FROM visit WHERE visit_id = ?", (visit_id,)
        ).fetchone()
        if not visit:
            return None
        diagnoses = conn.execute(
            "SELECT * FROM visit_diagnosis WHERE visit_id = ?", (visit_id,)
        ).fetchall()
    return {
        "visit":     dict(visit),
        "diagnoses": [dict(d) for d in diagnoses],
    }


def get_gp_worklist(clinician_id: str) -> List[dict]:
    """
    Return the patient list for a GP's dashboard — matches the UI worklist table.

    Columns returned (per UI: Patient ID / Name / Age·Gender / Last Visit):
        patient_id, full_name, age (years, integer), sex_at_birth,
        last_visit_date, condition_count, medication_count

    Only includes patients who have had at least one visit with this clinician.
    Ordered alphabetically by family_name, given_names.
    """
    sql = """
        SELECT
            p.patient_id,
            p.given_names || ' ' || p.family_name          AS full_name,
            CAST(
                (julianday('now') - julianday(p.date_of_birth)) / 365.25
            AS INTEGER)                                     AS age,
            p.sex_at_birth,
            p.last_visit_date,
            COUNT(DISTINCT cc.condition_id)                 AS condition_count,
            COUNT(DISTINCT rx.prescription_id)              AS medication_count
        FROM patient_profile p
        JOIN visit v
            ON v.patient_id   = p.patient_id
            AND v.clinician_id = ?
        LEFT JOIN chronic_condition cc
            ON cc.patient_id = p.patient_id AND cc.status = 'active'
        LEFT JOIN prescription rx
            ON rx.patient_id = p.patient_id
        GROUP BY p.patient_id
        ORDER BY p.family_name, p.given_names
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (clinician_id,)).fetchall()
    return [dict(r) for r in rows]


def get_patient_profile(patient_id: str) -> Optional[dict]:
    """
    Return the patient header card data — profile + allergies + conditions.

    Matches the PatientEHR header card in the UI:
        name, patient_id, age, sex_at_birth, blood_type, phone, email
        allergies: [{substance, severity, type}]
        conditions: [{code, display, status, onset_date}]
    """
    with get_connection() as conn:
        profile = conn.execute(
            "SELECT * FROM patient_profile WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if not profile:
            return None

        age_row = conn.execute(
            """SELECT CAST(
                   (julianday('now') - julianday(date_of_birth)) / 365.25
               AS INTEGER) AS age
               FROM patient_profile WHERE patient_id = ?""",
            (patient_id,),
        ).fetchone()

        allergies = conn.execute(
            """SELECT substance, type, severity, exposure_route, certainty
               FROM allergy WHERE patient_id = ? ORDER BY substance""",
            (patient_id,),
        ).fetchall()

        conditions = conn.execute(
            """SELECT code_system, code, display, status, onset_date, certainty
               FROM chronic_condition
               WHERE patient_id = ? ORDER BY onset_date DESC""",
            (patient_id,),
        ).fetchall()

    return {
        **dict(profile),
        "age": age_row["age"] if age_row else None,
        "allergies": [dict(a) for a in allergies],
        "conditions": [dict(c) for c in conditions],
    }


def get_patient_visits(patient_id: str) -> List[dict]:
    """
    Return all visits for a patient, each enriched with its diagnoses and
    prescriptions — matches the Visit History tab in the UI.

    Each visit dict contains:
        visit_id, visit_date, visit_type, patient_reported_reason,
        clinician_notes, clinician_name (joined from clinician table)
        diagnoses: [{code, display, status}]
        prescriptions: [{medicine_name, dose, frequency, prescribed_date}]

    Ordered newest-first.
    """
    with get_connection() as conn:
        visits = conn.execute(
            """SELECT v.*, c.name AS clinician_name, c.specialty AS clinician_specialty
               FROM visit v
               LEFT JOIN clinician c ON c.clinician_id = v.clinician_id
               WHERE v.patient_id = ?
               ORDER BY v.visit_date DESC""",
            (patient_id,),
        ).fetchall()

        result = []
        for visit in visits:
            vid = visit["visit_id"]

            diagnoses = conn.execute(
                """SELECT code_system, code, display, status
                   FROM visit_diagnosis WHERE visit_id = ?""",
                (vid,),
            ).fetchall()

            prescriptions = conn.execute(
                """SELECT rx.medicine_name, rx.inn, rx.dose, rx.frequency,
                          rx.route, rx.prescribed_date, rx.therapy_type, rx.prn
                   FROM prescription rx
                   JOIN visit_prescription vp ON vp.prescription_id = rx.prescription_id
                   WHERE vp.visit_id = ?
                   ORDER BY rx.medicine_name""",
                (vid,),
            ).fetchall()

            result.append({
                **dict(visit),
                "diagnoses":     [dict(d) for d in diagnoses],
                "prescriptions": [dict(p) for p in prescriptions],
            })

    return result


def get_patient_medications(patient_id: str) -> List[dict]:
    """
    Return the full medication history for a patient — matches the Medications tab.

    Each row (per UI columns: Medication / Dosage / Frequency / Prescribed Date / Visit Ref):
        medicine_name, inn, atc, dose, frequency, route,
        therapy_type, prn, prescribed_date, ref_id (visit_id)

    Ordered newest prescription first.
    """
    sql = """
        SELECT
            rx.prescription_id,
            rx.medicine_name,
            rx.inn,
            rx.atc,
            rx.dose,
            rx.frequency,
            rx.route,
            rx.therapy_type,
            rx.prn,
            rx.prn_reason,
            rx.prescribed_date,
            rx.indication_code,
            rx.indication_display,
            rx.ref_id          AS visit_ref_id
        FROM prescription rx
        WHERE rx.patient_id = ?
        ORDER BY rx.prescribed_date DESC, rx.medicine_name
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (patient_id,)).fetchall()
    return [dict(r) for r in rows]


def get_patient_documents(patient_id: str) -> List[dict]:
    """
    Return all documents, lab results, and imaging studies for a patient —
    matches the Labs & Imaging tab in the UI.

    Returns a unified list of dicts, each with:
        source:   'document' | 'lab_result' | 'imaging_study'
        title:    display name / filename
        category: 'lab' | 'imaging' | 'document'
        date:     authored_date / measured_at / performed_at (as string)
        detail:   value+unit (lab), modality+body_site (imaging), filename (doc)
        ref_visit_id

    Ordered by date descending.
    """
    with get_connection() as conn:
        docs = conn.execute(
            """SELECT 'document' AS source, title, doc_type AS category,
                      authored_date AS date, filename AS detail, ref_visit_id
               FROM document WHERE patient_id = ?""",
            (patient_id,),
        ).fetchall()

        labs = conn.execute(
            """SELECT 'lab_result' AS source, test_display AS title,
                      'lab' AS category,
                      measured_at AS date,
                      value || ' ' || COALESCE(unit, '') AS detail,
                      ref_visit_id
               FROM lab_result
               WHERE patient_id = ?
                 AND test_code NOT IN ('8867-4', '59408-5', '8310-5')""",
            (patient_id,),
        ).fetchall()

        imaging = conn.execute(
            """SELECT 'imaging_study' AS source,
                      modality || COALESCE(' — ' || body_site, '') AS title,
                      'imaging' AS category,
                      performed_at AS date,
                      COALESCE(report_summary, '') AS detail,
                      ref_visit_id
               FROM imaging_study WHERE patient_id = ?""",
            (patient_id,),
        ).fetchall()

        pending_orders = conn.execute(
            """SELECT 'order' AS source,
                      test_display AS title,
                      category,
                      order_date AS date,
                      status AS detail,
                      ref_visit_id
               FROM order_entry WHERE patient_id = ?""",
            (patient_id,),
        ).fetchall()

    combined = (
        [dict(r) for r in docs]
        + [dict(r) for r in labs]
        + [dict(r) for r in imaging]
        + [dict(r) for r in pending_orders]
    )
    combined.sort(key=lambda r: r["date"] or "", reverse=True)
    return combined


def get_patient_vitals(patient_id: str) -> dict:
    """
    Return structured vitals history for a patient.

    All vital types are stored in the vitals table:
        weight_kg, systolic_mmhg/diastolic_mmhg, heart_rate_bpm, spo2_pct, temperature_c.

    temperature_c is visit-context only — callers must NOT show it in the summary bar.

    Returns:
        height_cm:           from patient_profile (needed for BMI calculation)
        weight_history:      [{vital_id, measured_at, weight_kg}] newest first
        bp_history:          [{vital_id, measured_at, systolic_mmhg, diastolic_mmhg}] newest first
        hr_history:          [{vital_id, measured_at, heart_rate_bpm}] newest first
        spo2_history:        [{vital_id, measured_at, spo2_pct}] newest first
        temperature_history: [{vital_id, measured_at, ref_visit_id, temperature_c}] newest first
    """
    with get_connection() as conn:
        height_row = conn.execute(
            "SELECT height_cm FROM patient_profile WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()

        weight_rows = conn.execute(
            """SELECT vital_id, measured_at, weight_kg
               FROM vitals
               WHERE patient_id = ? AND weight_kg IS NOT NULL
               ORDER BY measured_at DESC""",
            (patient_id,),
        ).fetchall()

        bp_rows = conn.execute(
            """SELECT vital_id, measured_at, systolic_mmhg, diastolic_mmhg
               FROM vitals
               WHERE patient_id = ? AND systolic_mmhg IS NOT NULL
               ORDER BY measured_at DESC""",
            (patient_id,),
        ).fetchall()

        hr_rows = conn.execute(
            """SELECT vital_id, measured_at, heart_rate_bpm
               FROM vitals
               WHERE patient_id = ? AND heart_rate_bpm IS NOT NULL
               ORDER BY measured_at DESC""",
            (patient_id,),
        ).fetchall()

        spo2_rows = conn.execute(
            """SELECT vital_id, measured_at, spo2_pct
               FROM vitals
               WHERE patient_id = ? AND spo2_pct IS NOT NULL
               ORDER BY measured_at DESC""",
            (patient_id,),
        ).fetchall()

        temp_rows = conn.execute(
            """SELECT vital_id, measured_at, ref_visit_id, temperature_c
               FROM vitals
               WHERE patient_id = ? AND temperature_c IS NOT NULL
               ORDER BY measured_at DESC""",
            (patient_id,),
        ).fetchall()

    return {
        "height_cm":           height_row["height_cm"] if height_row else None,
        "weight_history":      [dict(r) for r in weight_rows],
        "bp_history":          [dict(r) for r in bp_rows],
        "hr_history":          [dict(r) for r in hr_rows],
        "spo2_history":        [dict(r) for r in spo2_rows],
        "temperature_history": [dict(r) for r in temp_rows],
    }


def get_patient_background(patient_id: str) -> Optional[dict]:
    """
    Return lifestyle and family history for the Patient Background tab.

    Returns:
        lifestyle:      {smoking_status, diet_pattern, alcohol_units_per_week,
                         alcohol_units_per_month, activity_sessions_per_week}
        family_history: [{relation, code_system, code, display, age_of_onset}]
    """
    with get_connection() as conn:
        profile = conn.execute(
            "SELECT patient_id FROM patient_profile WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
        if not profile:
            return None

        ls_row = conn.execute(
            "SELECT * FROM lifestyle WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()

        fh_rows = conn.execute(
            """SELECT relation, code_system, code, display, age_of_onset
               FROM family_history WHERE patient_id = ?
               ORDER BY relation""",
            (patient_id,),
        ).fetchall()

    return {
        "lifestyle":      dict(ls_row) if ls_row else None,
        "family_history": [dict(r) for r in fh_rows],
    }


def search_patients(name: str) -> List[dict]:
    """
    Simple name search across given_names and family_name.

    Args:
        name: Partial name string (case-insensitive).

    Returns:
        List of patient profile dicts matching the name.
    """
    pattern = f"%{name}%"
    sql = """
        SELECT * FROM patient_profile
        WHERE given_names LIKE ? OR family_name LIKE ?
        ORDER BY family_name, given_names
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (pattern, pattern)).fetchall()
    return [dict(r) for r in rows]


def create_visit(
    patient_id: str,
    patient_reported_reason: str,
    clinician_notes: str,
    diagnoses: List[dict],
    prescriptions: List[dict],
    vitals: Optional[dict],
    orders: Optional[List[dict]] = None,
    clinician_id: str = "CLN001",
    visit_type: str = "outpatient",
) -> str:
    """
    Insert a new visit with diagnoses, prescriptions, and optional vitals.

    Args:
        patient_id:               Target patient.
        patient_reported_reason:  Chief complaint / reason for visit.
        clinician_notes:          Free-text SOAP / clinical notes.
        diagnoses:                List of {code, display, code_system, status}.
        prescriptions:            List of {medicine_name, inn, dose, frequency, route, therapy_type}.
        vitals:                   Optional {weight_kg, systolic_mmhg, diastolic_mmhg, measured_at}.
        clinician_id:             Defaults to demo clinician CLN001.
        visit_type:               Defaults to 'consultation'.

    Returns:
        The newly created visit_id string.
    """
    visit_id   = "V" + uuid.uuid4().hex[:8].upper()
    visit_date = datetime.date.today().isoformat()

    with get_connection() as conn:
        # ── visit ──────────────────────────────────────────────────────────────
        conn.execute(
            """INSERT INTO visit
               (visit_id, patient_id, clinician_id, visit_date, visit_type,
                patient_reported_reason, clinician_notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (visit_id, patient_id, clinician_id, visit_date, visit_type,
             patient_reported_reason or "", clinician_notes or ""),
        )

        # ── visit_diagnosis ────────────────────────────────────────────────────
        for diag in diagnoses:
            diag_id = "VD" + uuid.uuid4().hex[:8].upper()
            conn.execute(
                """INSERT INTO visit_diagnosis
                   (visit_diagnosis_id, visit_id, code_system, code, display, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    diag_id, visit_id,
                    diag.get("code_system", "ICD-10"),
                    diag.get("code", ""),
                    diag.get("display", ""),
                    diag.get("status", "provisional"),
                ),
            )

        # ── prescription + visit_prescription ──────────────────────────────────
        for rx in prescriptions:
            rx_id = "RX" + uuid.uuid4().hex[:8].upper()
            conn.execute(
                """INSERT INTO prescription
                   (prescription_id, patient_id, medicine_name, inn, dose,
                    frequency, route, therapy_type, prn, prescribed_date,
                    ref_type, ref_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rx_id, patient_id,
                    rx.get("medicine_name", ""),
                    rx.get("inn") or rx.get("medicine_name", ""),
                    rx.get("dose", ""),
                    rx.get("frequency") or "as_needed",
                    rx.get("route", "oral"),
                    rx.get("therapy_type", "acute"),
                    0,          # prn = False
                    visit_date,
                    "visit",    # ref_type
                    visit_id,   # ref_id
                ),
            )
            vp_id = "VP" + uuid.uuid4().hex[:8].upper()
            conn.execute(
                "INSERT INTO visit_prescription (id, visit_id, prescription_id) VALUES (?, ?, ?)",
                (vp_id, visit_id, rx_id),
            )

        # ── vitals (optional) ──────────────────────────────────────────────────
        # All four vital types go into the vitals table.
        if vitals:
            measured_at = (
                vitals.get("measured_at")
                or datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            has_any = any(
                vitals.get(k) is not None
                for k in ("weight_kg", "systolic_mmhg", "heart_rate_bpm", "spo2_pct",
                          "temperature_c")
            )
            if has_any:
                vital_id = "VIT" + uuid.uuid4().hex[:8].upper()
                conn.execute(
                    """INSERT INTO vitals
                       (vital_id, patient_id, measured_at, ref_visit_id,
                        weight_kg, systolic_mmhg, diastolic_mmhg,
                        heart_rate_bpm, spo2_pct, temperature_c)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        vital_id, patient_id, measured_at, visit_id,
                        vitals.get("weight_kg"),
                        vitals.get("systolic_mmhg"),
                        vitals.get("diastolic_mmhg"),
                        vitals.get("heart_rate_bpm"),
                        vitals.get("spo2_pct"),
                        vitals.get("temperature_c"),
                    ),
                )

        # ── order_entry ────────────────────────────────────────────────────────────
        for order in (orders or []):
            order_id = "ORD" + uuid.uuid4().hex[:8].upper()
            conn.execute(
                """INSERT INTO order_entry
                   (order_id, patient_id, order_date, ref_visit_id,
                    category, test_code_system, test_code, test_display, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, patient_id, visit_date, visit_id,
                    order.get("category", "lab"),
                    order.get("test_code_system", "LOINC"),
                    order.get("test_code", ""),
                    order.get("test_display", ""),
                    order.get("status", "requested"),
                ),
            )

        # ── update patient last_visit_date ─────────────────────────────────────
        conn.execute(
            """UPDATE patient_profile
               SET last_visit_date = ?, last_visit_id = ?
               WHERE patient_id = ?
                 AND (last_visit_date IS NULL OR last_visit_date <= ?)""",
            (visit_date, visit_id, patient_id, visit_date),
        )

    return visit_id
