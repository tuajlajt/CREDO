#!/usr/bin/env python3
"""
Seed the CREDO demo SQLite database.

Reads data/synthetic/patients/P001-P010.json and populates
data/synthetic/credo_demo.db with all 16 tables defined in
src/data/schema/EHR.dbml.

Usage:
    python scripts/seed_db.py              # create/reset DB
    python scripts/seed_db.py --check      # print row counts only

The .db file is committed to git so testers can run SQL queries
without running this script. Re-run it only if you modify the JSON files.
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sqlite3
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "synthetic" / "credo_demo.db"
PATIENTS_DIR = PROJECT_ROOT / "data" / "synthetic" / "patients"


# ── Schema (mirrors EHR.dbml exactly) ─────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clinician (
    clinician_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    specialty       TEXT,
    organization    TEXT
);

CREATE TABLE IF NOT EXISTS patient_profile (
    patient_id          TEXT PRIMARY KEY,
    given_names         TEXT NOT NULL,
    family_name         TEXT NOT NULL,
    date_of_birth       TEXT NOT NULL,
    sex_at_birth        TEXT NOT NULL,
    gender_identity     TEXT,
    blood_type          TEXT NOT NULL DEFAULT 'unknown',
    preferred_language  TEXT,
    phone               TEXT,
    email               TEXT,
    height_cm           REAL,
    last_visit_date     TEXT,
    last_visit_id       TEXT
);

CREATE TABLE IF NOT EXISTS lifestyle (
    patient_id                  TEXT PRIMARY KEY,
    smoking_status              TEXT NOT NULL DEFAULT 'unknown',
    diet_pattern                TEXT NOT NULL DEFAULT 'unknown',
    alcohol_units_per_week      REAL,
    alcohol_units_per_month     REAL,
    activity_sessions_per_week  INTEGER,
    FOREIGN KEY (patient_id) REFERENCES patient_profile(patient_id)
);

CREATE TABLE IF NOT EXISTS allergy (
    allergy_id      TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    substance       TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'allergy',
    severity        TEXT NOT NULL DEFAULT 'unknown',
    exposure_route  TEXT NOT NULL DEFAULT 'unknown',
    reactions       TEXT,
    certainty       TEXT NOT NULL DEFAULT 'confirmed',
    last_reviewed   TEXT,
    FOREIGN KEY (patient_id) REFERENCES patient_profile(patient_id)
);

CREATE TABLE IF NOT EXISTS chronic_condition (
    condition_id    TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    code_system     TEXT NOT NULL,
    code            TEXT NOT NULL,
    display         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    onset_date      TEXT,
    certainty       TEXT NOT NULL DEFAULT 'confirmed',
    FOREIGN KEY (patient_id) REFERENCES patient_profile(patient_id)
);

CREATE TABLE IF NOT EXISTS family_history (
    family_history_id   TEXT PRIMARY KEY,
    patient_id          TEXT NOT NULL,
    relation            TEXT NOT NULL,
    code_system         TEXT NOT NULL,
    code                TEXT NOT NULL,
    display             TEXT NOT NULL,
    age_of_onset        INTEGER,
    FOREIGN KEY (patient_id) REFERENCES patient_profile(patient_id)
);

CREATE TABLE IF NOT EXISTS visit (
    visit_id                TEXT PRIMARY KEY,
    clinician_id            TEXT NOT NULL,
    patient_id              TEXT NOT NULL,
    visit_date              TEXT NOT NULL,
    visit_type              TEXT NOT NULL,
    patient_reported_reason TEXT NOT NULL,
    clinician_notes         TEXT NOT NULL,
    FOREIGN KEY (clinician_id) REFERENCES clinician(clinician_id),
    FOREIGN KEY (patient_id)   REFERENCES patient_profile(patient_id)
);

CREATE TABLE IF NOT EXISTS visit_diagnosis (
    visit_diagnosis_id  TEXT PRIMARY KEY,
    visit_id            TEXT NOT NULL,
    code_system         TEXT NOT NULL,
    code                TEXT NOT NULL,
    display             TEXT NOT NULL,
    status              TEXT,
    FOREIGN KEY (visit_id) REFERENCES visit(visit_id)
);

CREATE TABLE IF NOT EXISTS prescription (
    prescription_id         TEXT PRIMARY KEY,
    patient_id              TEXT NOT NULL,
    prescribed_date         TEXT NOT NULL,
    medicine_name           TEXT NOT NULL,
    inn                     TEXT NOT NULL,
    atc                     TEXT,
    dose                    TEXT NOT NULL,
    frequency               TEXT NOT NULL,
    route                   TEXT,
    therapy_type            TEXT NOT NULL DEFAULT 'unknown',
    prn                     INTEGER NOT NULL DEFAULT 0,
    prn_reason              TEXT,
    max_per_day             REAL,
    indication_code_system  TEXT,
    indication_code         TEXT,
    indication_display      TEXT,
    quantity_amount         REAL,
    quantity_unit           TEXT,
    days_supply             INTEGER,
    expected_end_date       TEXT,
    ref_type                TEXT NOT NULL DEFAULT 'visit',
    ref_id                  TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patient_profile(patient_id)
);

CREATE TABLE IF NOT EXISTS visit_prescription (
    id              TEXT PRIMARY KEY,
    visit_id        TEXT NOT NULL,
    prescription_id TEXT NOT NULL,
    FOREIGN KEY (visit_id)        REFERENCES visit(visit_id),
    FOREIGN KEY (prescription_id) REFERENCES prescription(prescription_id)
);

CREATE TABLE IF NOT EXISTS vitals (
    vital_id        TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    measured_at     TEXT NOT NULL,
    ref_visit_id    TEXT,
    weight_kg       REAL,
    systolic_mmhg   REAL,
    diastolic_mmhg  REAL,
    heart_rate_bpm  REAL,
    spo2_pct        REAL,
    temperature_c   REAL,
    FOREIGN KEY (patient_id)    REFERENCES patient_profile(patient_id),
    FOREIGN KEY (ref_visit_id)  REFERENCES visit(visit_id)
);

CREATE TABLE IF NOT EXISTS order_entry (
    order_id        TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    order_date      TEXT NOT NULL,
    ref_visit_id    TEXT,
    category        TEXT NOT NULL,
    test_code_system TEXT NOT NULL,
    test_code       TEXT NOT NULL,
    test_display    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'completed',
    FOREIGN KEY (patient_id)   REFERENCES patient_profile(patient_id),
    FOREIGN KEY (ref_visit_id) REFERENCES visit(visit_id)
);

CREATE TABLE IF NOT EXISTS imaging_study (
    imaging_study_id    TEXT PRIMARY KEY,
    patient_id          TEXT NOT NULL,
    performed_at        TEXT NOT NULL,
    ref_visit_id        TEXT,
    order_id            TEXT,
    modality            TEXT NOT NULL,
    body_site           TEXT,
    report_summary      TEXT,
    FOREIGN KEY (patient_id)   REFERENCES patient_profile(patient_id),
    FOREIGN KEY (ref_visit_id) REFERENCES visit(visit_id)
);

CREATE TABLE IF NOT EXISTS lab_result (
    lab_result_id   TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    measured_at     TEXT NOT NULL,
    ref_visit_id    TEXT,
    order_id        TEXT,
    test_code_system TEXT NOT NULL,
    test_code       TEXT NOT NULL,
    test_display    TEXT NOT NULL,
    value           TEXT NOT NULL,
    unit            TEXT,
    reference_range TEXT,
    abnormal_flag   TEXT,
    FOREIGN KEY (patient_id)   REFERENCES patient_profile(patient_id),
    FOREIGN KEY (ref_visit_id) REFERENCES visit(visit_id)
);

CREATE TABLE IF NOT EXISTS procedure_entry (
    procedure_id    TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    performed_date  TEXT NOT NULL,
    ref_visit_id    TEXT,
    code_system     TEXT NOT NULL,
    code            TEXT NOT NULL,
    display         TEXT NOT NULL,
    outcome         TEXT,
    FOREIGN KEY (patient_id)   REFERENCES patient_profile(patient_id),
    FOREIGN KEY (ref_visit_id) REFERENCES visit(visit_id)
);

CREATE TABLE IF NOT EXISTS document (
    document_id     TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    authored_date   TEXT NOT NULL,
    ref_visit_id    TEXT,
    doc_type        TEXT NOT NULL,
    title           TEXT NOT NULL,
    filename        TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'application/pdf',
    storage_ref     TEXT NOT NULL,
    sha256          TEXT,
    FOREIGN KEY (patient_id)   REFERENCES patient_profile(patient_id),
    FOREIGN KEY (ref_visit_id) REFERENCES visit(visit_id)
);
"""


# ── Seeding helpers ────────────────────────────────────────────────────────────

def _therapy_type(raw: str) -> str:
    """Map JSON therapy_duration values to DBML therapy_type enum."""
    mapping = {
        "long_term": "chronic",
        "chronic": "chronic",
        "short_term": "acute",
        "acute": "acute",
    }
    return mapping.get(raw, "unknown")


def seed_clinicians(conn: sqlite3.Connection) -> None:
    rows = [
        ("CLN001", "Dr. Tara Knowles",    "General Practice",    "City Medical Centre"),
        ("CLN002", "Dr. Michael Okafor",   "Emergency Medicine",  "Royal General Hospital"),
        ("CLN003", "Dr. Priya Nair",       "Cardiology",          "Royal General Hospital"),
        ("CLN004", "Dr. James Whitfield",  "Respiratory Medicine","Chest & Allergy Clinic"),
        ("CLN005", "Dr. Amara Diallo",     "Endocrinology",       "Diabetes & Metabolic Unit"),
        ("CLN006", "Dr. Lena Bergstrom",   "Psychiatry",          "Mental Health Services"),
        ("CLN007", "Dr. Felix Osei",       "Nephrology",          "Renal Unit"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO clinician (clinician_id, name, specialty, organization) VALUES (?,?,?,?)",
        rows,
    )


def seed_patient(conn: sqlite3.Connection, data: dict) -> None:
    pid = data["patient_profile"]["patient_id"]
    demo = data["patient_profile"]["demographics"]
    admin = data["patient_profile"].get("administrative", {})
    static = data["patient_profile"].get("static_measurements", {})
    last_visit = data["patient_profile"].get("last_visit", {})
    cs = data.get("clinical_summary", {})

    # ── patient_profile ───────────────────────────────────────────────────────
    name = demo.get("name", {})
    given = " ".join(filter(None, [
        name.get("first_name", ""), name.get("middle_name", "")
    ])).strip() or "Unknown"
    family = name.get("last_name", "Unknown")

    conn.execute(
        """INSERT OR REPLACE INTO patient_profile
           (patient_id, given_names, family_name, date_of_birth, sex_at_birth,
            blood_type, height_cm, last_visit_date, last_visit_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            pid, given, family,
            demo.get("date_of_birth", ""),
            demo.get("sex_at_birth", "unknown"),
            demo.get("blood_type", "unknown"),
            static.get("height_cm"),
            last_visit.get("date"),
            last_visit.get("visit_id"),
        ),
    )

    # ── lifestyle ─────────────────────────────────────────────────────────────
    ls = data.get("lifestyle", {})
    if ls:
        alc = ls.get("alcohol", {})
        act = ls.get("physical_activity", {})
        conn.execute(
            """INSERT OR REPLACE INTO lifestyle
               (patient_id, smoking_status, diet_pattern,
                alcohol_units_per_week, activity_sessions_per_week)
               VALUES (?,?,?,?,?)""",
            (
                pid,
                ls.get("smoking_status", "unknown"),
                ls.get("diet_pattern", "unknown"),
                alc.get("units_per_week"),
                act.get("moderate_to_high_sessions_per_week"),
            ),
        )

    # ── allergies ─────────────────────────────────────────────────────────────
    for idx, alg in enumerate(cs.get("allergies", []), start=1):
        alg_id = alg.get("allergy_id") or f"ALG{pid}_{idx:02d}"
        reactions = alg.get("reactions")
        if isinstance(reactions, list):
            reactions = ", ".join(reactions)
        conn.execute(
            """INSERT OR IGNORE INTO allergy
               (allergy_id, patient_id, substance, type, severity,
                exposure_route, reactions, certainty, last_reviewed)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                alg_id, pid,
                alg.get("substance", "unknown"),
                alg.get("type", "allergy"),
                alg.get("severity", "unknown"),
                alg.get("exposure_route", "unknown"),
                reactions,
                alg.get("certainty", "confirmed"),
                alg.get("last_reviewed"),
            ),
        )

    # ── chronic_conditions ────────────────────────────────────────────────────
    for idx, cond in enumerate(cs.get("chronic_conditions", []), start=1):
        cond_id = cond.get("condition_id") or f"CC{pid}_{idx:02d}"
        conn.execute(
            """INSERT OR IGNORE INTO chronic_condition
               (condition_id, patient_id, code_system, code, display,
                status, onset_date, certainty)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                cond_id, pid,
                cond.get("code_system", "ICD-10"),
                cond.get("code", ""),
                cond.get("display", ""),
                cond.get("status", "active"),
                cond.get("onset_date"),
                cond.get("certainty", "confirmed"),
            ),
        )

    # ── family_history ────────────────────────────────────────────────────────
    for idx, fh in enumerate(data.get("family_history", []), start=1):
        fh_id = fh.get("family_history_id") or f"FH{pid}_{idx:02d}"
        cond = fh.get("condition", {})
        conn.execute(
            """INSERT OR IGNORE INTO family_history
               (family_history_id, patient_id, relation,
                code_system, code, display, age_of_onset)
               VALUES (?,?,?,?,?,?,?)""",
            (
                fh_id, pid,
                fh.get("relation", "unknown"),
                cond.get("code_system", "ICD-10"),
                cond.get("code", ""),
                cond.get("display", ""),
                fh.get("age_of_onset"),
            ),
        )

    # ── visits + visit_diagnoses ──────────────────────────────────────────────
    for visit in data.get("visits", []):
        vid = visit["visit_id"]
        clinician_id = visit.get("clinician_id", "CLN001")
        conn.execute(
            """INSERT OR IGNORE INTO visit
               (visit_id, clinician_id, patient_id, visit_date,
                visit_type, patient_reported_reason, clinician_notes)
               VALUES (?,?,?,?,?,?,?)""",
            (
                vid, clinician_id, pid,
                visit.get("visit_date", ""),
                visit.get("type", "outpatient"),
                visit.get("patient_reported_reason", ""),
                visit.get("clinician_notes", ""),
            ),
        )
        for didx, diag in enumerate(visit.get("diagnoses", []), start=1):
            vd_id = f"VD{vid}_{didx:02d}"
            conn.execute(
                """INSERT OR IGNORE INTO visit_diagnosis
                   (visit_diagnosis_id, visit_id, code_system, code, display, status)
                   VALUES (?,?,?,?,?,?)""",
                (
                    vd_id, vid,
                    diag.get("code_system", "ICD-10"),
                    diag.get("code", ""),
                    diag.get("display", ""),
                    diag.get("status"),
                ),
            )

    # ── prescriptions + visit_prescriptions ──────────────────────────────────
    for rx in data.get("prescriptions", []):
        rx_id = rx["prescription_id"]
        ind = rx.get("indication", {})
        medicine_name = rx.get("medicine_name") or rx.get("inn", "unknown")
        conn.execute(
            """INSERT OR IGNORE INTO prescription
               (prescription_id, patient_id, prescribed_date,
                medicine_name, inn, atc, dose, frequency, route,
                therapy_type, prn, prn_reason,
                indication_code_system, indication_code, indication_display,
                ref_type, ref_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rx_id, pid,
                rx.get("prescribed_date", ""),
                medicine_name,
                rx.get("inn", ""),
                rx.get("atc"),
                rx.get("dose", ""),
                rx.get("frequency", ""),
                rx.get("route"),
                _therapy_type(rx.get("therapy_duration", rx.get("therapy_type", ""))),
                1 if rx.get("prn") else 0,
                rx.get("prn_condition") or rx.get("prn_reason"),
                ind.get("code_system"),
                ind.get("code"),
                ind.get("display"),
                rx.get("ref", {}).get("type", "visit"),
                rx.get("ref", {}).get("id", ""),
            ),
        )
        # Link to visit via visit_prescription junction
        ref_visit = rx.get("ref", {})
        if ref_visit.get("type") == "visit" and ref_visit.get("id"):
            vp_id = f"VP{rx_id}"
            conn.execute(
                """INSERT OR IGNORE INTO visit_prescription
                   (id, visit_id, prescription_id) VALUES (?,?,?)""",
                (vp_id, ref_visit["id"], rx_id),
            )

    # ── vitals ────────────────────────────────────────────────────────────────
    # All clinical vitals go into the vitals table.
    # Types: blood_pressure → systolic/diastolic; weight → weight_kg;
    #        heart_rate → heart_rate_bpm; spo2 → spo2_pct;
    #        temperature → temperature_c (visit-context only, never in summary bar)
    # Other types (blood_glucose) go to lab_result.
    lab_result_counter = 1
    for vital in data.get("vitals_history", []):
        vtype = vital.get("type", "")
        vid_ref = vital.get("ref_visit_id")
        measured_at = vital.get("measured_at", "")
        vital_id = vital.get("vital_id") or f"VT{pid}_{vtype}"

        if vtype == "blood_pressure":
            conn.execute(
                """INSERT OR IGNORE INTO vitals
                   (vital_id, patient_id, measured_at, ref_visit_id,
                    systolic_mmhg, diastolic_mmhg)
                   VALUES (?,?,?,?,?,?)""",
                (
                    vital_id, pid, measured_at, vid_ref,
                    vital.get("systolic_mmHg") or vital.get("systolic_mmhg"),
                    vital.get("diastolic_mmHg") or vital.get("diastolic_mmhg"),
                ),
            )
        elif vtype == "weight":
            conn.execute(
                """INSERT OR IGNORE INTO vitals
                   (vital_id, patient_id, measured_at, ref_visit_id, weight_kg)
                   VALUES (?,?,?,?,?)""",
                (vital_id, pid, measured_at, vid_ref, vital.get("value")),
            )
        elif vtype == "heart_rate":
            conn.execute(
                """INSERT OR IGNORE INTO vitals
                   (vital_id, patient_id, measured_at, ref_visit_id, heart_rate_bpm)
                   VALUES (?,?,?,?,?)""",
                (vital_id, pid, measured_at, vid_ref, vital.get("value")),
            )
        elif vtype == "spo2":
            conn.execute(
                """INSERT OR IGNORE INTO vitals
                   (vital_id, patient_id, measured_at, ref_visit_id, spo2_pct)
                   VALUES (?,?,?,?,?)""",
                (vital_id, pid, measured_at, vid_ref, vital.get("value")),
            )
        elif vtype == "temperature":
            conn.execute(
                """INSERT OR IGNORE INTO vitals
                   (vital_id, patient_id, measured_at, ref_visit_id, temperature_c)
                   VALUES (?,?,?,?,?)""",
                (vital_id, pid, measured_at, vid_ref, vital.get("value")),
            )
        else:
            # blood_glucose and any other measurement types → lab_result
            loinc = {
                "blood_glucose": ("2339-0",  "Glucose [Mass/volume] in Blood"),
            }.get(vtype)
            if loinc:
                lr_id = f"LR{pid}_{lab_result_counter:03d}"
                lab_result_counter += 1
                value = vital.get("value", "")
                unit = vital.get("unit", "")
                conn.execute(
                    """INSERT OR IGNORE INTO lab_result
                       (lab_result_id, patient_id, measured_at, ref_visit_id,
                        test_code_system, test_code, test_display,
                        value, unit)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (lr_id, pid, measured_at, vid_ref,
                     "LOINC", loinc[0], loinc[1],
                     str(value), unit),
                )

    # ── imaging_studies ───────────────────────────────────────────────────────
    for img in data.get("imaging_studies", []):
        conn.execute(
            """INSERT OR IGNORE INTO imaging_study
               (imaging_study_id, patient_id, performed_at, ref_visit_id,
                order_id, modality, body_site, report_summary)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                img.get("imaging_study_id", ""),
                pid,
                img.get("performed_at", img.get("date", "")),
                img.get("ref_visit_id"),
                img.get("order_id"),
                img.get("modality", ""),
                img.get("body_site"),
                img.get("report_summary") or img.get("report"),
            ),
        )

    # ── orders ────────────────────────────────────────────────────────────────
    for order in data.get("orders", []):
        conn.execute(
            """INSERT OR IGNORE INTO order_entry
               (order_id, patient_id, order_date, ref_visit_id,
                category, test_code_system, test_code, test_display, status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                order.get("order_id", ""),
                pid,
                order.get("order_date", ""),
                order.get("ref_visit_id"),
                order.get("category", "lab"),
                order.get("test_code_system", "LOINC"),
                order.get("test_code", ""),
                order.get("test_display", ""),
                order.get("status", "completed"),
            ),
        )

    # ── procedures ────────────────────────────────────────────────────────────
    for proc in data.get("procedures", []):
        conn.execute(
            """INSERT OR IGNORE INTO procedure_entry
               (procedure_id, patient_id, performed_date, ref_visit_id,
                code_system, code, display, outcome)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                proc.get("procedure_id", ""),
                pid,
                proc.get("performed_date", ""),
                proc.get("ref_visit_id"),
                proc.get("code_system", "CPT"),
                proc.get("code", ""),
                proc.get("display", ""),
                proc.get("outcome"),
            ),
        )

    # ── documents ─────────────────────────────────────────────────────────────
    for doc in data.get("documents", []):
        conn.execute(
            """INSERT OR IGNORE INTO document
               (document_id, patient_id, authored_date, ref_visit_id,
                doc_type, title, filename, content_type, storage_ref, sha256)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                doc.get("document_id", ""),
                pid,
                doc.get("authored_date", ""),
                doc.get("ref_visit_id"),
                doc.get("doc_type", "other"),
                doc.get("title", ""),
                doc.get("filename", ""),
                doc.get("content_type", "application/pdf"),
                doc.get("storage_ref", ""),
                doc.get("sha256"),
            ),
        )


# ── Row count check ────────────────────────────────────────────────────────────

def print_counts(conn: sqlite3.Connection) -> None:
    tables = [
        "clinician", "patient_profile", "lifestyle", "allergy",
        "chronic_condition", "family_history", "visit", "visit_diagnosis",
        "prescription", "visit_prescription", "vitals", "order_entry",
        "imaging_study", "lab_result", "procedure_entry", "document",
    ]
    print(f"\n{'Table':<25}  {'Rows':>6}")
    print("-" * 35)
    total = 0
    for t in tables:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        total += n
        print(f"  {t:<23}  {n:>6}")
    print("-" * 35)
    print(f"  {'TOTAL':<23}  {total:>6}\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CREDO demo SQLite DB")
    parser.add_argument("--check",  action="store_true", help="Print row counts only")
    parser.add_argument("--append", action="store_true",
                        help="Add new data to existing DB without deleting it first "
                             "(uses INSERT OR IGNORE — safe to run while server is live)")
    args = parser.parse_args()

    if args.check:
        if not DB_PATH.exists():
            print(f"DB not found at {DB_PATH}. Run without --check to create it.")
            sys.exit(1)
        conn = sqlite3.connect(DB_PATH)
        print_counts(conn)
        conn.close()
        return

    # Reset and recreate (unless --append)
    if not args.append:
        if DB_PATH.exists():
            DB_PATH.unlink()
            log.info("Removed existing %s", DB_PATH.name)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    log.info("Schema created")

    seed_clinicians(conn)
    log.info("Clinicians seeded")

    patient_files = sorted(PATIENTS_DIR.glob("P*.json"))
    if not patient_files:
        log.error("No patient JSON files found in %s", PATIENTS_DIR)
        sys.exit(1)

    for path in patient_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        pid = data["patient_profile"]["patient_id"]
        seed_patient(conn, data)
        log.info("Seeded %s", pid)

    # Assign all patient visits to CLN001 (Dr. Sarah Knowles, GP)
    # so that the GP worklist query returns all 10 patients.
    conn.execute("UPDATE visit SET clinician_id = 'CLN001'")
    log.info("All visits reassigned to CLN001 (GP)")

    # Add multi-point weight history so the weight-trend arrow is demonstrable.
    # Three scenarios covering all three arrow colours:
    #   P005 (172 cm): gaining weight, both measurements overweight → RED arrow
    #   P010 (155 cm): losing weight, obese → overweight            → GREEN arrow
    #   P006 (168 cm): gaining weight, both measurements normal BMI → GRAY arrow
    # Dates are within the 6-month trend window (2025-08-24 to 2026-02-24).
    conn.executemany(
        """INSERT OR IGNORE INTO vitals
           (vital_id, patient_id, measured_at, weight_kg)
           VALUES (?, ?, ?, ?)""",
        [
            # P005: 76 kg → 84 kg (+10.5 %), BMI 25.7 → 28.4 (overweight → more overweight) → RED
            ("DEMO_P005_W1", "P005", "2025-09-10T09:00:00Z", 76.0),
            ("DEMO_P005_W2", "P005", "2026-01-20T09:00:00Z", 84.0),
            # P010: 79 kg → 71 kg (−10.1 %), BMI 32.9 → 29.5 (obese → overweight) → GREEN
            ("DEMO_P010_W1", "P010", "2025-09-01T09:00:00Z", 79.0),
            ("DEMO_P010_W2", "P010", "2026-01-15T09:00:00Z", 71.0),
            # P006: 55 kg → 62 kg (+12.7 %), BMI 19.5 → 22.0 (both normal range) → GRAY
            ("DEMO_P006_W1", "P006", "2025-09-05T09:00:00Z", 55.0),
            ("DEMO_P006_W2", "P006", "2026-01-10T09:00:00Z", 62.0),
        ],
    )
    log.info("Weight-trend demo measurements added (P005/P010/P006)")

    conn.commit()
    conn.close()

    log.info("Database written to %s", DB_PATH)

    # Verify
    conn = sqlite3.connect(DB_PATH)
    print_counts(conn)
    conn.close()


if __name__ == "__main__":
    main()
