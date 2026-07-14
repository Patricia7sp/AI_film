ARG RUNPOD_COMFYUI_BASE_IMAGE=runpod/worker-comfyui:5.8.6-base
FROM ${RUNPOD_COMFYUI_BASE_IMAGE}

WORKDIR /comfyui

ARG COMFYUI_IPADAPTER_COMMIT=b188a6cb39b512a9c6da7235b880af42c78ccd0d
RUN git clone https://github.com/comfyorg/comfyui-ipadapter.git \
      custom_nodes/comfyui-ipadapter && \
    cd custom_nodes/comfyui-ipadapter && \
    git checkout "${COMFYUI_IPADAPTER_COMMIT}"

ARG AI_FILM_CHECKPOINT_NAME=ai-film-comic-storybook-xl.safetensors
ARG AI_FILM_CHECKPOINT_URL=https://huggingface.co/cagliostrolab/animagine-xl-4.0/resolve/main/animagine-xl-4.0-opt.safetensors
ARG AI_FILM_EMBED_CHECKPOINT=false

RUN mkdir -p models/checkpoints && \
    if [ "${AI_FILM_EMBED_CHECKPOINT}" = "true" ]; then \
      wget -q -O "models/checkpoints/${AI_FILM_CHECKPOINT_NAME}" "${AI_FILM_CHECKPOINT_URL}" && \
      ln -sf "${AI_FILM_CHECKPOINT_NAME}" models/checkpoints/v1-5-pruned-emaonly.safetensors; \
    fi

COPY start_ai_film.sh /start_ai_film.sh
RUN chmod +x /start_ai_film.sh

CMD ["/start_ai_film.sh"]
