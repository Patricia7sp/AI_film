ARG RUNPOD_COMFYUI_BASE_IMAGE=runpod/worker-comfyui:5.8.5-base
FROM ${RUNPOD_COMFYUI_BASE_IMAGE}

WORKDIR /comfyui

ARG AI_FILM_CHECKPOINT_NAME=ai-film-cinematic-realism.safetensors
ARG AI_FILM_CHECKPOINT_URL=https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/resolve/main/Realistic_Vision_V5.1_fp16-no-ema.safetensors

RUN mkdir -p models/checkpoints && \
    wget -q -O "models/checkpoints/${AI_FILM_CHECKPOINT_NAME}" "${AI_FILM_CHECKPOINT_URL}" && \
    ln -sf "${AI_FILM_CHECKPOINT_NAME}" models/checkpoints/v1-5-pruned-emaonly.safetensors
