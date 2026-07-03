import sys
import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    _audio_quality_gate,
    _build_image_prompt,
    _build_scene_contract,
    _elevenlabs_voice_id_for_scene,
    _hero_object_requirements,
    _premium_audio_direction,
    _premium_audio_narration,
)
from open3d_implementation import ui_server  # noqa: E402


def _names(scene):
    return [item["name"] for item in _hero_object_requirements(scene)]


def test_sugar_bowl_mouse_is_hero_object_without_negative_prompt_false_positives():
    scene = {
        "description": (
            "Na sala de jantar vitoriana, Ludovico revela o truque do "
            "açucareiro: um pequeno ratinho branco surge do açucareiro."
        ),
        "prompt": "no coin trick, no fake text/card",
        "must_include": [
            "fully visible sugar bowl with open lid",
            "small white mouse emerging from the sugar bowl",
        ],
        "must_not_include": ["coin trick", "letter", "card"],
    }

    assert _names(scene) == ["white mouse emerging from open sugar bowl"]

    contract = _build_scene_contract(scene)
    assert (
        contract["hero_objects"][0]["name"]
        == "white mouse emerging from open sugar bowl"
    )
    assert any("hero object legibility" in item for item in contract["required"])

    prompt = _build_image_prompt(scene, "cinematic_realism", {}, "")
    assert "Hero object mandate" in prompt
    assert "white mouse emerging from open sugar bowl" in prompt


def test_anthill_is_hero_object_but_substrings_do_not_trigger_ants():
    anthill_scene = {
        "description": "Alice se ajoelha para observar um pequeno formigueiro.",
        "must_include": ["small anthill in the grass"],
    }
    assert _names(anthill_scene) == ["small anthill"]

    false_positive_scene = {
        "description": "Alice ajusta as pantalonas perto das plantas.",
        "must_include": [],
    }
    assert _names(false_positive_scene) == []


def test_generic_small_objects_require_word_boundaries():
    scene = {
        "description": "Alice encontra uma chave pequena ao lado de uma carta.",
        "must_include": ["small key", "sealed letter"],
    }
    assert _names(scene) == ["key", "letter"]

    false_positive_scene = {
        "description": "The discard pile is watched from afar.",
        "must_include": [],
    }
    assert _names(false_positive_scene) == []


def test_premium_audio_narration_removes_debug_scene_label():
    scene = {
        "scene_id": 2,
        "description": (
            "Na sala de jantar vitoriana, Ludovico revela o truque do açucareiro: "
            "um pequeno ratinho branco surge do açucareiro."
        ),
        "must_include": ["small white mouse emerging from the sugar bowl"],
    }

    narration = _premium_audio_narration(scene)
    direction = _premium_audio_direction(scene)

    assert not narration.lower().startswith("cena 2:")
    assert "ratinho branco" in narration
    assert "suspense" in direction["tone"]


def test_audio_quality_gate_marks_non_premium_provider():
    metrics = {
        "valid": True,
        "duration_seconds": 7.2,
        "bit_rate": 128000,
        "quality_score": 96.0,
        "issues": [],
    }

    gated = _audio_quality_gate(metrics, "Alice observa o jardim.", "local_tts")

    assert gated["premium_audio"] is False
    assert "non_premium_voice_provider" in gated["issues"]
    assert gated["quality_score"] <= 72.0


def test_voice_id_can_route_future_character_dialogue(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "narrator-default")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_ALICE", "alice-premium")

    voice_id, role = _elevenlabs_voice_id_for_scene({"scene_id": 1, "speaker": "Alice"})

    assert role == "Alice"
    assert voice_id == "alice-premium"


def test_selective_audio_retry_is_premium_elevenlabs_only():
    source = inspect.getsource(ui_server._run_selective_audio_retry)

    assert "_generate_local_tts_audio" not in source
    assert "_enhance_premium_audio" in source
    assert '"audio_provider": "elevenlabs"' in source
