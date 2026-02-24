#!/bin/bash
# Download HAI-DEF model weights from HuggingFace.
# Run once on the host machine before starting Docker containers.
# Weights are then mounted read-only into containers via docker-compose.yml.
#
# Prerequisites:
#   1. pip install huggingface_hub
#   2. Accept Google's usage terms for each model on HuggingFace
#      (visit each model page, click "Agree and access repository")
#   3. Set HUGGINGFACE_TOKEN:
#        export HUGGINGFACE_TOKEN=hf_xxx
#      Or copy .env.example → .env and source it: source .env
#
# Usage:
#   # Download everything (WARNING: up to ~200 GB total for all large models)
#   bash scripts/download_models.sh
#
#   # Download a specific tier only
#   TIER=core bash scripts/download_models.sh
#   TIER=imaging bash scripts/download_models.sh
#   TIER=audio bash scripts/download_models.sh
#   TIER=drug bash scripts/download_models.sh
#
# TIER options:
#   core    — MedGemma 1.5 4B (multimodal, vision+text, ~8 GB)
#   imaging — CXR, Derm, Path Foundation + MedSigLIP + CT Foundation (~10 GB total)
#   audio   — HeAR health acoustic model (~1 GB)
#   drug    — TxGemma 2B + 9B predict (~22 GB)
#   all     — Everything above (default if TIER not set)
#
# Model sizes (approximate):
#   MedGemma 1.5 4B    ~8 GB
#   MedGemma 27B       ~54 GB   (commented out — enable only if you have the storage)
#   CXR Foundation     ~1-3 GB
#   Derm Foundation    ~1-3 GB
#   Path Foundation    ~1-3 GB
#   MedSigLIP 400M     ~2 GB
#   CT Foundation      ~1-3 GB
#   HeAR               ~1 GB
#   TxGemma 2B         ~4 GB
#   TxGemma 9B         ~18 GB
#   TxGemma 27B        ~54 GB   (commented out — enable only if you have the storage)
#
# MedASR: accessed via Google Cloud Speech-to-Text API — no download required.
#         Set GCP_PROJECT and GOOGLE_APPLICATION_CREDENTIALS in .env instead.

set -e

# ── Validate prerequisites ─────────────────────────────────────────────────────
if [ -z "${HUGGINGFACE_TOKEN}" ]; then
    echo "ERROR: HUGGINGFACE_TOKEN environment variable not set."
    echo "Get a token at: https://huggingface.co/settings/tokens"
    echo "Then run: export HUGGINGFACE_TOKEN=hf_xxx"
    exit 1
fi

OUTPUT_DIR="${MODEL_WEIGHTS_PATH:-./models}"
TIER="${TIER:-all}"

mkdir -p "${OUTPUT_DIR}"

echo "=================================================="
echo " HAI-DEF Model Downloader"
echo "=================================================="
echo " Output directory : ${OUTPUT_DIR}"
echo " Tier             : ${TIER}"
echo ""
echo " NOTE: Accept usage terms on HuggingFace for each"
echo " model before running this script:"
echo "   https://huggingface.co/collections/google/health-ai-developer-foundations-hai-def"
echo "   https://huggingface.co/collections/google/medgemma-release"
echo "   https://huggingface.co/collections/google/txgemma-release"
echo ""
echo " This may take a very long time on slow connections."
echo "=================================================="
echo ""

PYTHON="${PYTHON:-python}"
"$PYTHON" - <<EOF
from huggingface_hub import snapshot_download
import os
import sys

token = os.environ["HUGGINGFACE_TOKEN"]
output_dir = "${OUTPUT_DIR}"
tier = "${TIER}".lower()

# ── Model registry ─────────────────────────────────────────────────────────────
# Each entry: (hf_repo_id, tier_tag, description, approx_size_gb)
MODELS = [

    # ── Core: MedGemma 1.5 (vision+text, multimodal) ──────────────────────────
    # MedGemma 1.5 is the Jan 2026 update with improved medical reasoning,
    # medical records interpretation, and high-dim imaging (CT, MRI, WSI).
    # Instruction-tuned — ready for inference out of the box.
    (
        "google/medgemma-1.5-4b-it",
        "core",
        "MedGemma 1.5 4B — multimodal vision+text instruction-tuned (latest)",
        8,
    ),
    # Original MedGemma 4B — kept for backwards compatibility / comparison
    # (
    #     "google/medgemma-4b-it",
    #     "core",
    #     "MedGemma 4B original — multimodal vision+text instruction-tuned",
    #     8,
    # ),
    # Pre-trained (not instruction-tuned) — use for fine-tuning only
    # (
    #     "google/medgemma-4b-pt",
    #     "core",
    #     "MedGemma 4B pre-trained — base model for fine-tuning",
    #     8,
    # ),
    # 27B text-only — requires ~54 GB storage and A100-class GPU
    # (
    #     "google/medgemma-27b-text-it",
    #     "core",
    #     "MedGemma 27B text-only instruction-tuned (~54 GB)",
    #     54,
    # ),

    # ── Imaging foundation models ──────────────────────────────────────────────
    (
        "google/cxr-foundation",
        "imaging",
        "CXR Foundation — chest X-ray embedding model (EfficientNet-L2)",
        3,
    ),
    (
        "google/derm-foundation",
        "imaging",
        "Derm Foundation — dermatology skin image embedding model",
        3,
    ),
    (
        "google/path-foundation",
        "imaging",
        "Path Foundation — histopathology patch embedding model",
        3,
    ),
    (
        "google/medsiglip-448",
        "imaging",
        "MedSigLIP — multimodal image+text embedding, zero-shot classification (448px)",
        2,
    ),
    # CT Foundation: not available on HuggingFace as of Feb 2026.
    # It is only accessible via Google Cloud Healthcare API / Vertex AI.
    # See: https://developers.google.com/health-ai-developer-foundations

    # ── Audio ──────────────────────────────────────────────────────────────────
    # Two variants: TF SavedModel (google/hear) and PyTorch (google/hear-pytorch)
    # Use hear-pytorch for easier integration with the rest of the PyTorch stack.
    (
        "google/hear-pytorch",
        "audio",
        "HeAR PyTorch — health acoustic embeddings (cough, breath, spirometry)",
        1,
    ),
    (
        "google/medasr",
        "audio",
        "MedASR — medical speech recognition model (also accessible via Cloud API)",
        1,
    ),

    # ── Drug / therapeutic (TxGemma) ──────────────────────────────────────────
    # predict variants: structured property prediction (SMILES → property score)
    # chat variants: conversational, explains reasoning — useful for QA workflows
    (
        "google/txgemma-2b-predict",
        "drug",
        "TxGemma 2B predict — fast drug property prediction (BBB, tox, ADMET)",
        4,
    ),
    (
        "google/txgemma-9b-predict",
        "drug",
        "TxGemma 9B predict — balanced accuracy/speed for drug prediction",
        18,
    ),
    # 27B variants — requires ~54 GB storage
    # (
    #     "google/txgemma-27b-predict",
    #     "drug",
    #     "TxGemma 27B predict — highest accuracy drug prediction (~54 GB)",
    #     54,
    # ),
    # (
    #     "google/txgemma-27b-chat",
    #     "drug",
    #     "TxGemma 27B chat — conversational drug prediction with explanations (~54 GB)",
    #     54,
    # ),

]

# ── Filter by tier ─────────────────────────────────────────────────────────────
if tier == "all":
    selected = MODELS
else:
    selected = [(m, t, d, s) for m, t, d, s in MODELS if t == tier]
    if not selected:
        print(f"ERROR: Unknown tier '{tier}'. Choose: core, imaging, audio, drug, all")
        sys.exit(1)

total_gb = sum(s for _, _, _, s in selected)
print(f"Downloading {len(selected)} model(s) (~{total_gb} GB estimated)")
print()

# ── Download ───────────────────────────────────────────────────────────────────
failed = []
for model_id, model_tier, description, size_gb in selected:
    local_dir = os.path.join(output_dir, model_id.replace("/", "--"))
    print(f"[{model_tier.upper()}] {model_id}")
    print(f"  {description}")
    print(f"  Estimated size : ~{size_gb} GB")
    print(f"  Local path     : {local_dir}")
    try:
        snapshot_download(
            repo_id=model_id,
            token=token,
            local_dir=local_dir,
            ignore_patterns=["*.msgpack", "flax_model*", "tf_model*", "rust_model*"],
        )
        print(f"  Status         : OK")
    except Exception as e:
        print(f"  Status         : FAILED — {e}")
        failed.append((model_id, str(e)))
    print()

# ── Summary ────────────────────────────────────────────────────────────────────
print("=" * 50)
if failed:
    print(f"DONE with {len(failed)} failure(s):")
    for model_id, err in failed:
        print(f"  FAILED: {model_id} — {err}")
    print()
    print("Common causes:")
    print("  - Did not accept model terms on HuggingFace (visit each model page)")
    print("  - HUGGINGFACE_TOKEN expired or lacks read access")
    print("  - Insufficient disk space")
else:
    print(f"All {len(selected)} model(s) downloaded successfully.")
print()
print(f"Model weights saved to: {output_dir}")
print()
print("Next steps:")
print(f"  1. Set MODEL_WEIGHTS_PATH={output_dir} in your .env file")
print("  2. Run: docker-compose up")
print("  3. For MedASR: set GCP_PROJECT and GOOGLE_APPLICATION_CREDENTIALS in .env")
EOF
