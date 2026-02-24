# ML Research

Model architecture notes, benchmark results, fine-tuning strategies, and experiment findings.

---

## Table of Contents

1. [HAI-DEF Model Suite](#hai-def-model-suite)
2. [MedGemma](#medgemma)
3. [Foundation Model Embeddings](#foundation-model-embeddings)
4. [TxGemma](#txgemma)
5. [Fine-Tuning Strategy](#fine-tuning-strategy)
6. [Evaluation Metrics](#evaluation-metrics)
7. [Benchmarks & Baselines](#benchmarks--baselines)

---

## HAI-DEF Model Suite

Google Health AI Developer Foundations — overview of all models used in this project.

| Model | Size | Modality | HuggingFace ID |
|---|---|---|---|
| MedGemma | 4B / 27B | Vision + Text | `google/medgemma-4b-it` |
| CXR Foundation | — | CXR embeddings | `google/cxr-foundation` |
| Derm Foundation | — | Skin embeddings | `google/derm-foundation` |
| Path Foundation | — | Histopathology | `google/path-foundation` |
| MedSigLIP | 400M | Multimodal | `google/medsiglip-so400m-patch14-384` |
| HeAR | — | Health audio | `google/hear` |
| CT Foundation | — | 3D CT | `google/ct-foundation` |
| TxGemma | 2B / 27B | Drug prediction | `google/txgemma-2b-predict` |
| MedASR | — | Medical ASR | Google Cloud API |

---

## MedGemma

### Architecture
<!-- Add: Gemma backbone, SigLIP vision encoder, token budget, context window -->

### Prompt Engineering
<!-- Add: System prompt templates, few-shot examples, chain-of-thought patterns for medical reasoning -->

### Known Limitations
<!-- Add: Hallucination patterns, modality-specific failure modes, confidence calibration issues -->

---

## Foundation Model Embeddings

### CXR Foundation
<!-- Add: Embedding dimension, training dataset (CheXpert, MIMIC), downstream task performance -->

### Derm Foundation
<!-- Add: ISIC training data, embedding dimension, retrieval benchmark results -->

### Path Foundation
<!-- Add: TCGA training data, magnification conventions, patch-level vs. slide-level aggregation -->

### MedSigLIP
<!-- Add: Training data, zero-shot classification benchmarks, text-image alignment -->

### HeAR
<!-- Add: Audio embedding dimension, training corpus, downstream health audio tasks -->

### CT Foundation
<!-- Add: 3D volumetric embedding approach, HU normalization, training dataset -->

---

## TxGemma

### SMILES Representations
<!-- Add: RDKit SMILES canonicalization, validity filtering approach -->

### Prediction Tasks
<!-- Add: BBB penetration, Tox21 endpoint definitions, ADMET property coverage -->

---

## Fine-Tuning Strategy

### LoRA Configuration
<!-- Add: r, lora_alpha, lora_dropout, target_modules for MedGemma -->

### Data Requirements
<!-- Add: Minimum dataset sizes per modality, train/val/test split conventions -->

### Training Infrastructure
<!-- Add: GPU requirements, batch size, gradient accumulation, mixed precision -->

---

## Evaluation Metrics

| Task | Primary Metric | Secondary Metrics |
|---|---|---|
| CXR classification | AUC-ROC | Sensitivity, Specificity, F1 |
| Radiology report generation | BLEU-4, ROUGE-L | CheXbert F1 |
| Derm classification | AUC-ROC | Accuracy, Sensitivity |
| Path segmentation | Dice coefficient | IoU |
| Drug interaction | Precision, Recall | F1 |
| ASR | WER | MER, BLEU |

---

## Benchmarks & Baselines

<!-- Add: Published benchmark results for each HAI-DEF model, comparison with clinical baselines -->
