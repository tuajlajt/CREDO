/**
 * UI constants for the CREDO application.
 *
 * Centralises lab panel definitions, imaging modalities, CPT codes, and
 * visit types so they can be updated without touching component logic.
 *
 * LOINC codes: verified against NLM LOINC browser (loinc.org) as of 2025.
 * CPT codes: AMA CPT 2024 / standard radiology billing codes.
 */

// ── Lab panels — verified LOINC codes ──────────────────────────────────────────
export const LAB_PANEL_GROUPS = [
  {
    label: 'Baseline & General',
    tests: [
      { code: '58410-2', display: 'CBC'             },  // CBC panel - Blood by Automated count
      { code: '24323-8', display: 'CMP'             },  // Comprehensive metabolic 2000 panel
      { code: '51990-0', display: 'BMP'             },  // Basic metabolic panel - Blood
      { code: '24331-1', display: 'Lipid Panel'     },  // Lipid panel in Serum or Plasma
      { code: '4548-4',  display: 'HbA1c'           },  // Hemoglobin A1c/Hemoglobin.total in Blood
      { code: '1558-6',  display: 'Fasting Glucose' },  // Fasting glucose in Serum or Plasma
      { code: '11580-8', display: 'TSH'             },  // Thyrotropin in Serum or Plasma
      { code: '1988-5',  display: 'CRP'             },  // C reactive protein in Serum or Plasma
      { code: '30341-2', display: 'ESR'             },  // Erythrocyte sedimentation rate by Westergren
    ],
  },
  {
    label: 'Kidney & Urine',
    tests: [
      { code: '2160-0',  display: 'Serum Creatinine'                },  // Creatinine in Serum or Plasma
      { code: '62238-1', display: 'eGFR (CKD-EPI)'                 },  // GFR predicted by CKD-EPI
      { code: '24357-6', display: 'Urinalysis (UA)'                },  // UA macro+micro panel in Urine
      { code: '9318-7',  display: 'Urine Albumin-Creatinine Ratio' },  // Albumin/Creatinine in Urine
    ],
  },
  {
    label: 'Liver',
    tests: [
      { code: '1920-8',  display: 'AST'               },  // Aspartate aminotransferase in Serum
      { code: '1742-6',  display: 'ALT'               },  // Alanine aminotransferase in Serum
      { code: '6768-6',  display: 'ALP'               },  // Alkaline phosphatase in Serum
      { code: '1975-2',  display: 'Bilirubin (Total)' },  // Bilirubin.total in Serum
    ],
  },
  {
    label: 'Cardio & Metabolic',
    tests: [
      { code: '10839-9', display: 'Troponin I'   },  // Troponin I.cardiac in Serum
      { code: '33762-6', display: 'NT-proBNP'    },  // NT-proBNP in Serum or Plasma
      { code: '24326-1', display: 'Electrolytes' },  // Electrolytes panel in Serum or Plasma
    ],
  },
  {
    label: 'Endocrine & Nutrition',
    tests: [
      { code: '3024-7',  display: 'Free T4'           },  // Thyroxine free in Serum
      { code: '14635-7', display: 'Vitamin D (25-OH)' },  // 25-Hydroxyvitamin D3 in Serum
      { code: '2132-9',  display: 'Vitamin B12'       },  // Cobalamin in Serum
      { code: '2276-4',  display: 'Ferritin'          },  // Ferritin in Serum
      { code: '24336-0', display: 'Iron Studies'      },  // Iron binding capacity panel in Serum
    ],
  },
];

// ── Imaging order builder ───────────────────────────────────────────────────────
export const IMAGING_MODALITIES = [
  'X-Ray', 'CT', 'MRI', 'Ultrasound',
  'ECG / EKG', 'Echo', 'Cardiac Stress Test',
  'DEXA (Bone Density)', 'Mammography',
  'PET-CT', 'Fluoroscopy', 'Nuclear Medicine',
];

// Modalities that do not require a body part
export const NO_BODY_PART_MODALITIES = new Set([
  'ECG / EKG', 'Echo', 'Cardiac Stress Test',
  'DEXA (Bone Density)', 'Mammography',
]);

// Common body-part suggestions for the datalist
export const COMMON_BODY_PARTS = [
  'Brain', 'Chest', 'Abdomen', 'Pelvis', 'Abdomen & Pelvis',
  'Spine (Cervical)', 'Spine (Thoracic)', 'Spine (Lumbar)',
  'Hip', 'Knee', 'Shoulder', 'Ankle', 'Wrist', 'Hand', 'Foot',
  'Thyroid', 'Liver', 'Kidney', 'Full Body',
];

// CPT code lookup: key = "Modality_BodyPart" (no body part → "Modality_")
// Source: AMA CPT 2024 / standard radiology billing codes
export const IMAGING_CPT_LOOKUP = {
  'X-Ray_Chest':           '71046',  // Chest X-Ray 2 views (PA + lateral)
  'X-Ray_Spine (Lumbar)':  '72100',
  'X-Ray_Knee':            '73560',
  'X-Ray_Hip':             '73502',
  'X-Ray_Hand':            '73130',
  'X-Ray_Ankle':           '73600',
  'CT_Brain':              '70450',  // CT head/brain without contrast
  'CT_Chest':              '71250',  // CT chest without contrast
  'CT_Abdomen':            '74150',
  'CT_Pelvis':             '72192',
  'CT_Abdomen & Pelvis':   '74177',  // CT A+P with contrast (most ordered)
  'CT_Spine (Lumbar)':     '72131',
  'MRI_Brain':             '70551',  // MRI brain without contrast
  'MRI_Spine (Cervical)':  '72141',
  'MRI_Spine (Lumbar)':    '72148',
  'MRI_Knee':              '73721',
  'MRI_Shoulder':          '73221',
  'MRI_Hip':               '73721',
  'Ultrasound_Abdomen':    '76700',
  'Ultrasound_Pelvis':     '76856',
  'Ultrasound_Thyroid':    '76536',
  'Ultrasound_Kidney':     '76770',
  'ECG / EKG_':            '93000',
  'Echo_':                 '93306',  // Echo 2D complete with Doppler & color flow
  'Cardiac Stress Test_':  '93015',
  'DEXA (Bone Density)_':  '77080',
  'Mammography_':          '77067',  // Screening mammography bilateral
  'PET-CT_':               '78816',
};

export const VISIT_TYPES = [
  { value: 'outpatient',          label: 'Outpatient' },
  { value: 'inpatient',           label: 'Inpatient' },
  { value: 'er',                  label: 'Emergency Room' },
  { value: 'telehealth',          label: 'Telehealth' },
  { value: 'urgent_care',         label: 'Urgent Care' },
  { value: 'diagnostic_imaging',  label: 'Diagnostic Imaging' },
  { value: 'lab_visit',           label: 'Lab Visit' },
  { value: 'external_specialist', label: 'Specialist Referral' },
  { value: 'other',               label: 'Other' },
];
