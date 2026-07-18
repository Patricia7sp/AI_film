#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

MODEL_DIRS=(checkpoints controlnet diffusion_models loras text_encoders vae clip_vision ipadapter upscale_models)

for model_dir in "${MODEL_DIRS[@]}"; do
    target_dir="/comfyui/models/${model_dir}"
    mkdir -p "${target_dir}"
    for source_dir in "/runpod-volume/models/${model_dir}" "/workspace/models/${model_dir}"; do
        if [[ -d "${source_dir}" ]]; then
            files=("${source_dir}"/*)
            if (( ${#files[@]} > 0 )); then
                ln -sf "${files[@]}" "${target_dir}/"
            fi
        fi
    done
done

echo "AI_FILM_CHECKPOINTS"
ls -lh /comfyui/models/checkpoints /runpod-volume/models/checkpoints /workspace/models/checkpoints 2>/dev/null || true

echo "AI_FILM_CONTROLNET"
ls -lh /comfyui/models/controlnet /runpod-volume/models/controlnet /workspace/models/controlnet 2>/dev/null || true

echo "AI_FILM_IPADAPTER"
ls -lh /comfyui/models/ipadapter /comfyui/models/clip_vision 2>/dev/null || true

exec /start.sh
