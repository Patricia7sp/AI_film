"""Configuração mínima de LLM para o pipeline open3d."""

import json
import os
from types import SimpleNamespace
from typing import Any, Mapping

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


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


class _GeminiChat:
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._client: Any | None = None
        self._client_api_key = ""

    def _get_client(self) -> Any:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required")
        if self._client is not None and self._client_api_key == api_key:
            return self._client

        from google import genai
        from google.genai import types

        timeout_ms = (
            _bounded_int_env(
                "GEMINI_TEXT_TIMEOUT_SECONDS",
                default=90,
                minimum=15,
                maximum=300,
            )
            * 1000
        )
        retry_attempts = _bounded_int_env(
            "GEMINI_TEXT_RETRY_ATTEMPTS",
            default=2,
            minimum=1,
            maximum=3,
        )
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=timeout_ms,
                retry_options=types.HttpRetryOptions(
                    attempts=retry_attempts,
                    initial_delay=1.0,
                    max_delay=5.0,
                    exp_base=2.0,
                    jitter=0.25,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )
        self._client_api_key = api_key
        return self._client

    def invoke(self, prompt: str) -> SimpleNamespace:
        response = self._get_client().models.generate_content(
            model=self._model_name,
            contents=prompt,
        )
        return SimpleNamespace(content=str(response.text or ""))

    def invoke_json(
        self,
        prompt: str,
        response_json_schema: Mapping[str, object],
        *,
        max_output_tokens: int = 8192,
    ) -> SimpleNamespace:
        response = self._get_client().models.generate_content(
            model=self._model_name,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": dict(response_json_schema),
                "max_output_tokens": max_output_tokens,
                "temperature": 0.2,
            },
        )
        content = str(response.text or "")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("gemini_structured_output_invalid_json") from exc
        return SimpleNamespace(content=content, parsed=parsed)


def get_llm(use_pro_model: bool = False) -> _GeminiChat:
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
