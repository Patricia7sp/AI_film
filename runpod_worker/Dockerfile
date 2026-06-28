FROM runpod/worker-comfyui:5.8.6-base

WORKDIR /comfyui

RUN mkdir -p models/checkpoints && \
    wget -q -O models/checkpoints/v1-5-pruned-emaonly.safetensors \
    https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors
