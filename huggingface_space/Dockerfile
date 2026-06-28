FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    git \
    python3.10 \
    python3-pip \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI

WORKDIR /app/ComfyUI
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 && \
    pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/ComfyUI/models/checkpoints && \
    wget -q -O /app/ComfyUI/models/checkpoints/v1-5-pruned-emaonly.safetensors \
    https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors

# Space privado: o gateway da Hugging Face já exige
# `Authorization: Bearer <HF_TOKEN>` em toda requisição antes de chegar aqui.
# Não há necessidade de autenticação extra dentro do container.

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:7860/system_stats || exit 1

CMD ["python3", "main.py", "--listen", "0.0.0.0", "--port", "7860"]
