"""Configuração mínima de LLM para o pipeline open3d."""

import os
from types import SimpleNamespace

import google.generativeai as genai

GEMINI_TEXT_MODEL = os.getenv(
    "GEMINI_TEXT_MODEL",
    os.getenv("GEMINI_MODEL", os.getenv("DEFAULT_LLM", "gemini-3.5-flash")),
)
GEMINI_IMAGE_FAST_MODEL = os.getenv(
    "GEMINI_IMAGE_FAST_MODEL",
    os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image"),
)
GEMINI_IMAGE_QUALITY_MODEL = os.getenv(
    "GEMINI_IMAGE_QUALITY_MODEL",
    "gemini-3-pro-image",
)


class _GeminiChat:
    def __init__(self, model_name: str):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name)

    def invoke(self, prompt: str):
        response = self._model.generate_content(prompt)
        return SimpleNamespace(content=response.text)


def get_llm(use_pro_model: bool = False):
    """Retorna um cliente com interface .invoke(prompt) -> objeto com .content"""
    model_name = GEMINI_TEXT_MODEL
    return _GeminiChat(model_name)


def generate_cinematic_prompt(story_text: str, use_pro_model: bool = False) -> str:
    """Resume o tom visual/cinematográfico da história para guiar a geração de imagens."""
    llm = get_llm(use_pro_model=use_pro_model)
    instruction = (
        "Resuma o tom visual e cinematográfico desta história em até 3 frases, "
        "sugerindo paleta de cores, iluminação e atmosfera para gerar imagens de cena:\n\n"
        f"{story_text[:4000]}"
    )
    response = llm.invoke(instruction)
    return response.content
