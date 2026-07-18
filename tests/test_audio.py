import os
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.integration
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"


def _api_key() -> str:
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        pytest.skip("ELEVENLABS_API_KEY is not configured")
    return api_key


def _headers() -> dict[str, str]:
    return {
        "xi-api-key": _api_key(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _voices() -> list[dict[str, object]]:
    response = requests.get(
        f"{ELEVENLABS_API_URL}/voices", headers=_headers(), timeout=30
    )
    response.raise_for_status()
    voices = response.json().get("voices", [])
    assert voices, "ElevenLabs returned no available voices"
    return voices


def test_elevenlabs_initialization() -> None:
    assert _voices()


def test_list_voices() -> None:
    voices = _voices()
    assert all(voice.get("voice_id") for voice in voices)


def test_generate_audio(tmp_path: Path) -> None:
    voice_id = str(_voices()[0]["voice_id"])
    response = requests.post(
        f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}",
        headers=_headers(),
        json={
            "text": "Este e um teste curto de integracao do sistema de audio.",
            "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        },
        timeout=120,
    )
    response.raise_for_status()

    audio_path = tmp_path / "elevenlabs-integration.mp3"
    audio_path.write_bytes(response.content)
    assert audio_path.stat().st_size > 0
