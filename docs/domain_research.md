# Domain Research

Medical domain knowledge, clinical guidelines, and literature notes for the MedGemma Medical AI project.

---

## Table of Contents

1. [Radiology](#radiology)
2. [Dermatology](#dermatology)
3. [Pathology](#pathology)
4. [Clinical NLP](#clinical-nlp)
5. [Pharmacology](#pharmacology)
6. [Audio / Transcription](#audio--transcription)
7. [Regulatory & Standards](#regulatory--standards)

---

## Radiology

### Chest X-Ray (CXR)
<!-- Add: pathology classes, ACR guidelines, reading protocols, critical finding definitions -->

### CT
<!-- Add: HU windowing conventions by anatomy, slice thickness standards, resampling protocols -->

### MRI
<!-- Add: sequence types, anatomy-specific protocols -->

---

## Dermatology

### ABCDE Assessment
<!-- Add: Asymmetry, Border, Colour, Diameter, Evolution criteria -->

### Dermoscopy Standards
<!-- Add: International Dermoscopy Society guidelines, ISIC dataset notes -->

---

## Pathology

### H&E Slide Staining
<!-- Add: Tissue preparation, stain variation, fixation artefacts -->

### Patch-Based Analysis
<!-- Add: Magnification levels, tile size conventions (224px, 512px), tissue detection thresholds -->

---

## Clinical NLP

### SOAP Note Structure
<!-- Add: Subjective / Objective / Assessment / Plan field conventions -->

### Radiology Report Structure
<!-- Add: Clinical indication / Technique / Findings / Impression conventions -->

### Discharge Summary Structure
<!-- Add: Standard section headings, ICD-10 coding conventions -->

---

## Pharmacology

### Drug Interaction Severity Levels
<!-- Add: Major / Moderate / Minor definitions and clinical thresholds -->

### RxNorm API
<!-- Add: API endpoints, normalization patterns, TTY codes -->

### TxGemma SMILES Inputs
<!-- Add: Canonical SMILES format, RDKit validation, BBB/toxicity property definitions -->

---

## Audio / Transcription

### MedASR
<!-- Add: Google Cloud Speech-to-Text MedASR documentation notes, supported audio formats -->

### Clinical Audio Quality Standards
<!-- Add: Sample rate (16 kHz), silence threshold, minimum duration requirements -->

---

## Regulatory & Standards

### HIPAA
<!-- Add: PHI categories, minimum necessary standard, Business Associate Agreement requirements -->

### HL7/FHIR R4
<!-- Add: Resource types used (Observation, MedicationRequest, Condition), FHIR server endpoints -->

### FDA AI/ML SaMD Guidance
<!-- Add: Predetermined Change Control Plan, performance monitoring requirements -->

### DICOM Standards
<!-- Add: PHI tags to strip (list in src/data/dicom_loader.py), transfer syntaxes supported -->
