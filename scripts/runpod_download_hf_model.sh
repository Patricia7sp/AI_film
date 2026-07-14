#!/usr/bin/env bash
set -euo pipefail

MODEL_REF="${1:-comic-sdxl}"
MODEL_FILENAME="${2:-ai-film-comic-storybook-xl.safetensors}"
RELATIVE_PATH="${3:-models/checkpoints}"
MIN_SIZE_GB="1.0"

case "$MODEL_REF" in
  semantic-sdxl|juggernaut-xl-v9)
    MODEL_URL="https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
    ;;
  animation-sdxl|dreamshaper-xl-turbo-sfw)
    MODEL_URL="https://huggingface.co/Lykon/dreamshaper-xl-v2-turbo/resolve/main/DreamShaperXL_Turbo_V2-SFW.safetensors"
    ;;
  comic-sdxl|animagine-xl-4-opt)
    MODEL_URL="https://huggingface.co/cagliostrolab/animagine-xl-4.0/resolve/main/animagine-xl-4.0-opt.safetensors"
    ;;
  comic-sdxl-full|animagine-xl-4)
    MODEL_URL="https://huggingface.co/cagliostrolab/animagine-xl-4.0/resolve/main/animagine-xl-4.0.safetensors"
    ;;
  controlnet-sdxl-canny)
    MODEL_URL="https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors"
    RELATIVE_PATH="${3:-models/controlnet}"
    MODEL_FILENAME="${2:-controlnet-canny-sdxl-1.0.safetensors}"
    ;;
  controlnet-sdxl-depth)
    MODEL_URL="https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors"
    RELATIVE_PATH="${3:-models/controlnet}"
    MODEL_FILENAME="${2:-controlnet-depth-sdxl-1.0.safetensors}"
    ;;
  ipadapter-plus-sdxl)
    MODEL_URL="https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"
    RELATIVE_PATH="${3:-models/ipadapter}"
    MODEL_FILENAME="${2:-ip-adapter-plus_sdxl_vit-h.safetensors}"
    MIN_SIZE_GB="0.5"
    ;;
  clip-vision-vit-h)
    MODEL_URL="https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors"
    RELATIVE_PATH="${3:-models/clip_vision}"
    MODEL_FILENAME="${2:-CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors}"
    MIN_SIZE_GB="1.0"
    ;;
  flux2-klein-base-4b)
    MODEL_URL="https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors"
    RELATIVE_PATH="${3:-models/diffusion_models}"
    MODEL_FILENAME="${2:-flux-2-klein-base-4b.safetensors}"
    MIN_SIZE_GB="6.0"
    ;;
  flux2-qwen-3-4b)
    MODEL_URL="https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors"
    RELATIVE_PATH="${3:-models/text_encoders}"
    MODEL_FILENAME="${2:-qwen_3_4b.safetensors}"
    MIN_SIZE_GB="7.0"
    ;;
  flux2-vae)
    MODEL_URL="https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors"
    RELATIVE_PATH="${3:-models/vae}"
    MODEL_FILENAME="${2:-flux2-vae.safetensors}"
    MIN_SIZE_GB="0.1"
    ;;
  http://*|https://*)
    MODEL_URL="$MODEL_REF"
    ;;
  *)
    echo "Unknown model ref: ${MODEL_REF}" >&2
    echo "Usage: $0 [semantic-sdxl|animation-sdxl|comic-sdxl|comic-sdxl-full|controlnet-sdxl-canny|controlnet-sdxl-depth|ipadapter-plus-sdxl|clip-vision-vit-h|flux2-klein-base-4b|flux2-qwen-3-4b|flux2-vae|huggingface-model-url] [filename] [relative-path]" >&2
    echo "Visual-control and FLUX.2 aliases download directly into the RunPod Network Volume." >&2
    exit 2
    ;;
esac

if [[ -z "$MODEL_URL" ]]; then
  echo "Usage: $0 [semantic-sdxl|animation-sdxl|comic-sdxl|comic-sdxl-full|controlnet-sdxl-canny|controlnet-sdxl-depth|huggingface-model-url] [filename] [relative-path]" >&2
  exit 2
fi

if [[ -d "/runpod-volume" ]]; then
  VOLUME_ROOT="/runpod-volume"
elif [[ -d "/workspace" ]]; then
  VOLUME_ROOT="/workspace"
else
  echo "Could not find /runpod-volume or /workspace. Attach a RunPod Network Volume first." >&2
  exit 1
fi

TARGET_DIR="${VOLUME_ROOT}/${RELATIVE_PATH}"
TARGET_PATH="${TARGET_DIR}/${MODEL_FILENAME}"
PARTIAL_PATH="${TARGET_PATH}.partial"

mkdir -p "$TARGET_DIR"

AUTH_HEADER=()
if [[ -n "${HF_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${HF_TOKEN}")
fi

echo "Downloading model into ${TARGET_PATH}"
curl -fL --retry 5 --retry-delay 5 --continue-at - "${AUTH_HEADER[@]}" \
  -o "$PARTIAL_PATH" "$MODEL_URL"
mv "$PARTIAL_PATH" "$TARGET_PATH"

python3 - <<'PY' "$TARGET_PATH" "$MIN_SIZE_GB"
from pathlib import Path
import sys

path = Path(sys.argv[1])
minimum_gb = float(sys.argv[2])
size_gb = path.stat().st_size / 1024 / 1024 / 1024
if size_gb < minimum_gb:
    raise SystemExit(
        f"Downloaded model is too small: {size_gb:.3f} GB (minimum {minimum_gb:.3f} GB)"
    )
print(f"Model ready: {path} ({size_gb:.2f} GB)")
PY
