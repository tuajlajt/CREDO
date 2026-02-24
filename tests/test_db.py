"""
Database query tests — mirrors the four UI views in src/drafts/ui/app.jsx.

Four query groups tested:
  1. GP worklist     — dashboard patient table (Patient ID, Name, Age/Gender, Last Visit)
  2. Patient profile — header card (demographics + allergies + conditions)
  3. Visit history   — Visit History tab (visits + diagnoses + prescriptions per visit)
  4. Medications     — Medications tab (full prescription history, separate query)
  5. Labs & Imaging  — Labs & Imaging tab (documents + lab_results + imaging_studies, unified)

All queries run against data/synthetic/credo_demo.db.
Run: python scripts/seed_db.py   if the database does not exist yet.
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GP WORKLIST
#    UI: Patient Directory table — Patient ID / Name / Age·Gender / Last Visit
# ═══════════════════════════════════════════════════════════════════════════════

class TestGPWorklist:
    """
    Query: get_gp_worklist(clinician_id)

    All 10 synthetic patients were assigned to CLN001 (Dr. Sarah Knowles, GP)
    by the seed script, so the worklist should return all 10.
    """

    @pytest.fixture(autouse=True)
    def worklist(self, db_conn):
        from src.data.db import get_gp_worklist
        self.rows = get_gp_worklist("CLN001")

    def test_returns_all_ten_patients(self):
        assert len(self.rows) == 10

    def test_each_row_has_required_ui_fields(self):
        """Every row must have the four fields the UI table columns display."""
        for row in self.rows:
            assert "patient_id"      in row, f"missing patient_id in {row}"
            assert "full_name"       in row, f"missing full_name in {row}"
            assert "age"             in row, f"missing age in {row}"
            assert "sex_at_birth"    in row, f"missing sex_at_birth in {row}"
            assert "last_visit_date" in row, f"missing last_visit_date in {row}"

    def test_full_name_is_non_empty_string(self):
        for row in self.rows:
            assert isinstance(row["full_name"], str)
            assert len(row["full_name"].strip()) > 0

    def test_age_is_positive_integer(self):
        for row in self.rows:
            assert isinstance(row["age"], int), f"age is not int for {row['patient_id']}"
            assert row["age"] > 0, f"age <= 0 for {row['patient_id']}"
            assert row["age"] < 130, f"age implausible for {row['patient_id']}"

    def test_sex_at_birth_is_valid_enum(self):
        valid = {"female", "male", "intersex", "unknown"}
        for row in self.rows:
            assert row["sex_at_birth"] in valid, (
                f"{row['patient_id']} has unexpected sex_at_birth: {row['sex_at_birth']}"
            )

    def test_last_visit_date_is_populated(self):
        for row in self.rows:
            assert row["last_visit_date"] is not None, (
                f"{row['patient_id']} has null last_visit_date"
            )
            # Should look like a date string YYYY-MM-DD
            assert len(row["last_visit_date"]) == 10

    def test_ordered_alphabetically_by_family_name(self):
        """Worklist is sorted by family_name then given_names (as displayed in table)."""
        family_names = [r["full_name"].split()[-1] for r in self.rows]
        assert family_names == sorted(family_names)

    def test_specific_patients_are_present(self):
        """Spot-check that known patients appear with correct data."""
        by_id = {r["patient_id"]: r for r in self.rows}

        # Ana Barros — PE patient, 1 condition, 1 medication
        assert "P001" in by_id
        assert by_id["P001"]["full_name"] == "Ana Barros"
        assert by_id["P001"]["sex_at_birth"] == "female"
        assert by_id["P001"]["condition_count"] == 1
        assert by_id["P001"]["medication_count"] == 1

        # Harold George Patterson — polypharmacy (6 meds, 4 conditions)
        assert "P005" in by_id
        assert "Patterson" in by_id["P005"]["full_name"]
        assert by_id["P005"]["sex_at_birth"] == "male"
        assert by_id["P005"]["condition_count"] == 4
        assert by_id["P005"]["medication_count"] == 6

        # Margaret Anne O'Brien — most complex: 5 conditions, 6 meds
        assert "P010" in by_id
        assert "O'Brien" in by_id["P010"]["full_name"]
        assert by_id["P010"]["condition_count"] == 5
        assert by_id["P010"]["medication_count"] == 6

    def test_no_duplicate_patient_ids(self):
        ids = [r["patient_id"] for r in self.rows]
        assert len(ids) == len(set(ids)), "Duplicate patient_ids in worklist"

    def test_unknown_clinician_returns_empty(self):
        from src.data.db import get_gp_worklist
        result = get_gp_worklist("CLN_NONEXISTENT")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PATIENT PROFILE
#    UI: PatientEHR header card — name, age, gender, blood type, allergies, conditions
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatientProfile:
    """
    Query: get_patient_profile(patient_id)

    Tests the header card data — demographics + allergies + conditions.
    """

    def test_profile_has_all_header_card_fields(self, db_conn):
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P001")
        assert profile is not None

        # Fields shown in the UI header card
        for field in ("patient_id", "given_names", "family_name",
                      "date_of_birth", "sex_at_birth", "blood_type",
                      "age", "allergies", "conditions"):
            assert field in profile, f"missing field: {field}"

    def test_age_calculated_from_dob(self, db_conn):
        """Age is computed from date_of_birth — should be a reasonable integer."""
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P001")  # Ana Barros, DOB 1970-06-15
        assert isinstance(profile["age"], int)
        assert 50 <= profile["age"] <= 65  # range that covers 1970 DOB in 2024-2026

    def test_patient_with_allergy_penicillin(self, db_conn):
        """P004 Sophie Williams has a documented penicillin allergy."""
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P004")
        assert profile is not None

        substances = [a["substance"] for a in profile["allergies"]]
        assert "penicillin" in substances

        # allergy record has required fields
        allergy = profile["allergies"][0]
        for field in ("substance", "type", "severity", "certainty"):
            assert field in allergy

    def test_patient_with_allergy_codeine(self, db_conn):
        """P010 Margaret O'Brien has a documented codeine allergy."""
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P010")
        substances = [a["substance"] for a in profile["allergies"]]
        assert "codeine" in substances

    def test_patient_with_no_allergies(self, db_conn):
        """P005 Harold Patterson has no documented allergies."""
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P005")
        assert profile["allergies"] == []

    def test_complex_patient_conditions(self, db_conn):
        """P005 has 4 active chronic conditions — HF, AF, T2DM, Hypertension."""
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P005")

        assert len(profile["conditions"]) == 4
        codes = {c["code"] for c in profile["conditions"]}
        assert "I50.9" in codes   # Heart failure
        assert "I48.91" in codes  # Atrial fibrillation
        assert "E11.9" in codes   # Type 2 DM
        assert "I10" in codes     # Hypertension

        # Each condition record has required fields
        for cond in profile["conditions"]:
            for field in ("code_system", "code", "display", "status"):
                assert field in cond

    def test_most_complex_patient_p010(self, db_conn):
        """P010 has 5 conditions (most in the dataset) and a codeine allergy."""
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P010")

        assert len(profile["conditions"]) == 5
        assert len(profile["allergies"]) == 1
        assert profile["allergies"][0]["substance"] == "codeine"

        # Check blood type is populated
        assert profile["blood_type"] not in (None, "")

    def test_nonexistent_patient_returns_none(self, db_conn):
        from src.data.db import get_patient_profile
        assert get_patient_profile("P999") is None

    def test_conditions_ordered_newest_first(self, db_conn):
        """Conditions are returned newest onset_date first."""
        from src.data.db import get_patient_profile
        profile = get_patient_profile("P003")  # 3 conditions with onset dates
        dates = [c["onset_date"] for c in profile["conditions"] if c["onset_date"]]
        assert dates == sorted(dates, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. VISIT HISTORY
#    UI: Visit History tab — timeline of visits with diagnoses and prescriptions
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatientVisits:
    """
    Query: get_patient_visits(patient_id)

    Tests the Visit History tab — each visit with nested diagnoses and prescriptions.
    """

    def test_single_visit_patient(self, db_conn):
        """P001 Ana Barros had one ER visit (PE presentation)."""
        from src.data.db import get_patient_visits
        visits = get_patient_visits("P001")

        assert len(visits) == 1
        visit = visits[0]

        assert visit["visit_id"] == "V001_001"
        assert visit["visit_type"] == "er"
        assert visit["visit_date"] == "2024-10-15"
        assert "shortness of breath" in visit["patient_reported_reason"].lower()

    def test_multi_visit_patient_ordered_newest_first(self, db_conn):
        """P003 Robert Chen has 2 visits — must be returned newest first."""
        from src.data.db import get_patient_visits
        visits = get_patient_visits("P003")

        assert len(visits) == 2
        assert visits[0]["visit_date"] > visits[1]["visit_date"]

        # Most recent visit (Feb 2025 follow-up)
        assert visits[0]["visit_id"] == "V003_002"
        assert visits[0]["visit_date"] == "2025-02-03"

        # Older visit (Aug 2024 initial presentation)
        assert visits[1]["visit_id"] == "V003_001"
        assert visits[1]["visit_date"] == "2024-08-15"

    def test_visit_has_all_ui_fields(self, db_conn):
        """Every visit must have the fields the UI Visit History tab renders."""
        from src.data.db import get_patient_visits
        visits = get_patient_visits("P002")

        assert len(visits) >= 1
        visit = visits[0]

        for field in ("visit_id", "visit_date", "visit_type",
                      "patient_reported_reason", "clinician_notes",
                      "diagnoses", "prescriptions"):
            assert field in visit, f"missing field: {field}"

    def test_visit_diagnoses_are_nested(self, db_conn):
        """Each visit has a 'diagnoses' list with code + display."""
        from src.data.db import get_patient_visits
        # P001's ER visit has 2 diagnoses (PE + DVT)
        visits = get_patient_visits("P001")
        diags = visits[0]["diagnoses"]

        assert len(diags) == 2
        codes = {d["code"] for d in diags}
        assert "I26.9"  in codes   # Pulmonary embolism
        assert "I80.21" in codes   # Phlebitis right popliteal vein

        for diag in diags:
            for field in ("code_system", "code", "display"):
                assert field in diag

    def test_visit_prescriptions_are_nested(self, db_conn):
        """Each visit links to its prescriptions via visit_prescription junction."""
        from src.data.db import get_patient_visits
        # P003's first visit (V003_001) has 4 prescriptions
        visits = get_patient_visits("P003")
        first_visit = visits[-1]  # oldest = V003_001

        assert first_visit["visit_id"] == "V003_001"
        assert len(first_visit["prescriptions"]) == 4

        # Each prescription has the fields the UI Medications-within-visit section shows
        for rx in first_visit["prescriptions"]:
            for field in ("medicine_name", "dose", "frequency"):
                assert field in rx

    def test_visit_includes_clinician_name(self, db_conn):
        """Visit is joined to clinician table — clinician_name field is populated."""
        from src.data.db import get_patient_visits
        visits = get_patient_visits("P001")
        assert visits[0]["clinician_name"] is not None
        assert len(visits[0]["clinician_name"]) > 0

    def test_polypharmacy_patient_visits(self, db_conn):
        """P005 Harold Patterson has 2 visits."""
        from src.data.db import get_patient_visits
        visits = get_patient_visits("P005")
        assert len(visits) == 2

    def test_clinician_notes_are_detailed(self, db_conn):
        """Clinical notes are the full SOAP text — must be substantial."""
        from src.data.db import get_patient_visits
        visits = get_patient_visits("P001")
        notes = visits[0]["clinician_notes"]
        assert len(notes) > 100  # full SOAP note, not a stub

    def test_no_visits_patient_returns_empty(self, db_conn):
        """A non-existent patient returns an empty list, not an error."""
        from src.data.db import get_patient_visits
        assert get_patient_visits("P999") == []


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MEDICATIONS HISTORY
#    UI: Medications tab — Medication / Dosage / Frequency / Prescribed Date / Visit Ref
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatientMedications:
    """
    Query: get_patient_medications(patient_id)

    Separate query — not nested inside visits — matching the Medications tab which
    shows a flat table of ALL prescriptions across all visits for this patient.
    """

    def test_single_medication_patient(self, db_conn):
        """P001 Ana Barros is on one medication: rivaroxaban (Xarelto)."""
        from src.data.db import get_patient_medications
        meds = get_patient_medications("P001")

        assert len(meds) == 1
        assert meds[0]["inn"] == "rivaroxaban"
        assert meds[0]["medicine_name"] == "Xarelto"

    def test_polypharmacy_patient_six_meds(self, db_conn):
        """P010 Margaret O'Brien is on 6 medications."""
        from src.data.db import get_patient_medications
        meds = get_patient_medications("P010")

        assert len(meds) == 6

        inns = {m["inn"] for m in meds}
        assert "amlodipine"   in inns   # Norvasc
        assert "ramipril"     in inns
        assert "furosemide"   in inns
        assert "simvastatin"  in inns
        assert "aspirin"      in inns
        assert "omeprazole"   in inns

    def test_each_row_has_ui_table_columns(self, db_conn):
        """Every medication row has the columns the UI Medications tab renders."""
        from src.data.db import get_patient_medications
        meds = get_patient_medications("P005")
        assert len(meds) > 0

        for med in meds:
            assert "medicine_name"  in med
            assert "dose"           in med
            assert "frequency"      in med
            assert "prescribed_date" in med
            assert "visit_ref_id"   in med   # the "Visit Ref" column

    def test_medications_ordered_newest_first(self, db_conn):
        """Medications are ordered by prescribed_date DESC."""
        from src.data.db import get_patient_medications
        meds = get_patient_medications("P003")
        dates = [m["prescribed_date"] for m in meds]
        assert dates == sorted(dates, reverse=True)

    def test_harold_patterson_warfarin_on_aspirin(self, db_conn):
        """P005 has warfarin + aspirin — a clinically significant combination."""
        from src.data.db import get_patient_medications
        meds = get_patient_medications("P005")
        inns = {m["inn"] for m in meds}
        assert "warfarin" in inns
        assert "aspirin"  in inns

    def test_prn_field_is_present(self, db_conn):
        """PRN flag is included so the UI can mark as-needed medications."""
        from src.data.db import get_patient_medications
        meds = get_patient_medications("P004")  # Ventolin is PRN
        assert len(meds) > 0
        for med in meds:
            assert "prn" in med

    def test_nonexistent_patient_returns_empty(self, db_conn):
        from src.data.db import get_patient_medications
        assert get_patient_medications("P999") == []


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LABS & IMAGING
#    UI: Labs & Imaging tab — document/lab/imaging cards (filename, category, date)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatientDocuments:
    """
    Query: get_patient_documents(patient_id)

    Separate query unifying three tables: document, lab_result, imaging_study.
    Matches the Labs & Imaging tab which shows a card grid with file type icon,
    category badge (lab/imaging), and date.
    """

    def test_patient_with_imaging_and_lab(self, db_conn):
        """P007 David Kowalski (COPD): 1 chest X-ray imaging study + 1 SpO2 lab result."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P007")

        assert len(items) == 2

        sources = {i["source"] for i in items}
        assert "imaging_study" in sources
        assert "lab_result"    in sources

    def test_imaging_item_fields(self, db_conn):
        """Imaging items have the fields the UI card renders."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P007")

        imaging = [i for i in items if i["source"] == "imaging_study"]
        assert len(imaging) == 1

        img = imaging[0]
        assert img["category"] == "imaging"
        assert "X" in img["title"] or "MRI" in img["title"] or "CT" in img["title"] or img["title"]  # has a title
        assert img["date"] is not None

    def test_lab_result_item_fields(self, db_conn):
        """Lab result items have source='lab_result', category='lab', value in detail."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P007")

        lab = [i for i in items if i["source"] == "lab_result"][0]
        assert lab["category"] == "lab"
        assert lab["title"] is not None         # test display name
        assert lab["detail"] is not None        # "91 %"
        assert "91" in lab["detail"]            # SpO2 value for P007

    def test_document_item_fields(self, db_conn):
        """Document items (PDF lab reports) have correct fields."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P010")  # 2 renal function documents

        docs = [i for i in items if i["source"] == "document"]
        assert len(docs) == 2

        for doc in docs:
            assert "title"  in doc
            assert "date"   in doc
            assert "detail" in doc  # filename

    def test_ordered_newest_date_first(self, db_conn):
        """Combined results are sorted by date descending."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P003")  # 2 documents + 1 lab result
        dates = [i["date"] for i in items if i["date"]]
        assert dates == sorted(dates, reverse=True)

    def test_patient_with_multiple_document_types(self, db_conn):
        """P003 has 2 documents + 1 lab_result (glucose) = 3 items total."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P003")
        assert len(items) == 3

        sources = [i["source"] for i in items]
        assert sources.count("document")    == 2
        assert sources.count("lab_result")  == 1

    def test_patient_with_no_attachments(self, db_conn):
        """P008 Natasha Petrov has only weight vitals — no documents, labs, or imaging."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P008")
        assert items == []

    def test_lab_result_has_value_in_detail(self, db_conn):
        """Lab result 'detail' field contains the measured value and unit."""
        from src.data.db import get_patient_documents
        # P001 Ana Barros: SpO2 89%
        items = get_patient_documents("P001")
        labs = [i for i in items if i["source"] == "lab_result"]
        assert len(labs) == 1
        assert "89" in labs[0]["detail"]

    def test_glucose_lab_result_for_diabetic_patient(self, db_conn):
        """P003 Robert Chen (T2DM): blood glucose 8.2 mmol/L recorded as lab result."""
        from src.data.db import get_patient_documents
        items = get_patient_documents("P003")
        labs = [i for i in items if i["source"] == "lab_result"]
        assert len(labs) == 1
        assert "Glucose" in labs[0]["title"]
        assert "8.2" in labs[0]["detail"]

    def test_nonexistent_patient_returns_empty(self, db_conn):
        from src.data.db import get_patient_documents
        assert get_patient_documents("P999") == []
