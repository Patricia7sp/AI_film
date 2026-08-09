from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open3d_implementation.core import langgraph_adapter  # noqa: E402
from open3d_implementation.core.dialogue_contract import (  # noqa: E402
    build_speaker_motion_prompt,
    enrich_scene_performance,
    production_dialogue_gate,
    validate_scene_performance,
)


def _dialogue_scene() -> dict[str, object]:
    return {
        "scene_id": 2,
        "description": "Alice e Ludovico observam um ratinho sair do açucareiro.",
        "prompt": "Alice and Ludovico at a Victorian tea table with a white mouse.",
        "must_include": ["Alice", "Ludovico", "ratinho branco", "açucareiro"],
        "must_not_include": ["texto", "legenda"],
    }


def test_canonical_scene_becomes_dialogue_driven_without_narrator() -> None:
    scene = enrich_scene_performance(_dialogue_scene())
    gate = validate_scene_performance(scene)

    assert gate["passed"] is True
    assert gate["narration_absent"] is True
    assert scene["language"] == "pt-BR"
    assert scene["narration_allowed"] is False
    assert [turn["speaker_id"] for turn in scene["dialogue"]] == [
        "ludovico",
        "alice",
    ]
    assert all(turn["lip_sync_required"] for turn in scene["dialogue"])


def test_narrator_and_english_dialogue_are_blocking() -> None:
    scene = enrich_scene_performance(_dialogue_scene())
    scene["characters_present"] = ["Narrador"]
    scene["dialogue"] = [
        {
            "turn_id": "turn_1",
            "speaker_id": "narrador",
            "speaker_name": "Narrador",
            "text_pt_br": "Look at the mouse and see what it is doing.",
            "emotion": "neutro",
            "delivery": "locução",
            "action": "narra a ação",
            "addressee_id": None,
            "mode": "dialogue",
            "lip_sync_required": True,
        }
    ]

    gate = validate_scene_performance(scene)

    assert gate["passed"] is False
    assert "turn_1_narrator_forbidden" in gate["blockers"]
    assert "turn_1_language_not_pt_br" in gate["blockers"]


def test_internal_thought_keeps_every_mouth_closed() -> None:
    scene = enrich_scene_performance(
        {
            "scene_id": 1,
            "description": "Alice observa um formigueiro no jardim.",
            "prompt": "Alice beside an anthill in the garden.",
            "must_include": ["Alice", "formigueiro"],
        }
    )
    turn = scene["dialogue"][0]

    prompt = build_speaker_motion_prompt(scene, turn)

    assert turn["mode"] == "internal_thought"
    assert turn["lip_sync_required"] is False
    assert "mouth fully closed" in prompt
    assert "No character speaks on camera" in prompt


def test_legacy_english_scene_fields_are_migrated_to_portuguese() -> None:
    scene = enrich_scene_performance(
        {
            "scene_id": 8,
            "description": "Alice waits near a window with plum pies.",
            "main_action": "Alice stands near a window holding a basket of plum pies, looking out at the warm afternoon light, excited for tomorrow's boat trip.",
            "required_visual_elements": [
                "Alice approximately 10 years old",
                "ivory-white day dress",
                "wicker basket",
                "plum pies",
                "window",
            ],
        }
    )

    gate = validate_scene_performance(scene)

    assert gate["passed"] is True
    assert scene["main_action"].startswith("Alice está perto da janela")
    assert scene["required_visual_elements"] == [
        "Alice com cerca de 10 anos",
        "vestido diurno em marfim",
        "cesta de vime",
        "tortas de ameixa",
        "janela",
    ]


def test_dialogue_video_gate_requires_one_segment_per_turn() -> None:
    scene = enrich_scene_performance(_dialogue_scene())
    rendered_turns = [
        {**turn, "voice_id": f"voice-{index}", "voice_role": turn["speaker_name"]}
        for index, turn in enumerate(scene["dialogue"], 1)
    ]
    audio = [
        {
            "scene_id": 2,
            "audio_path": "scene.mp3",
            "dialogue_turns": rendered_turns,
        }
    ]
    incomplete_video = [
        {
            "scene_id": 2,
            "video_path": "scene.mp4",
            "dialogue_segments": [{"turn_id": "turn_1"}],
        }
    ]

    blocked = production_dialogue_gate([scene], audio, incomplete_video)

    assert blocked["passed"] is False
    assert any(
        "dialogue_video_segment_count_mismatch" in item for item in blocked["blockers"]
    )


def test_dialogue_gate_rejects_narrator_audio_even_with_valid_script() -> None:
    scene = enrich_scene_performance(_dialogue_scene())
    rendered_turns = [
        {
            **turn,
            "voice_id": "legacy-narrator",
            "voice_role": "narrator",
        }
        for turn in scene["dialogue"]
    ]

    gate = production_dialogue_gate(
        [scene],
        [{"scene_id": 2, "dialogue_turns": rendered_turns}],
        [],
    )

    assert gate["passed"] is False
    assert any("narrator_audio_forbidden" in item for item in gate["blockers"])


def test_scene_audio_uses_distinct_character_voices(
    monkeypatch, tmp_path: Path
) -> None:
    scene = enrich_scene_performance(_dialogue_scene())
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_LUDOVICO", "voice-ludovico")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_ALICE", "voice-alice")
    called_urls: list[str] = []

    def fake_post(url: str, **_kwargs: object) -> SimpleNamespace:
        called_urls.append(url)
        return SimpleNamespace(status_code=200, content=b"valid-audio")

    monkeypatch.setattr(langgraph_adapter.requests, "post", fake_post)
    monkeypatch.setattr(
        langgraph_adapter,
        "_enhance_premium_audio",
        lambda _raw, output, _scene: {
            "path": output,
            "valid": True,
            "duration_seconds": 3.0,
            "bit_rate": 128000,
            "quality_score": 96.0,
            "issues": [],
            "loudness": {"input_i_lufs": -14.0, "target_i_lufs": -14.0},
        },
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_assemble_dialogue_audio",
        lambda _scene_id, turns, output: {
            "path": output,
            "valid": True,
            "duration_seconds": 6.35,
            "bit_rate": 160000,
            "quality_score": 96.0,
            "premium_audio": True,
            "dialogue_turns": turns,
            "issues": [],
        },
    )

    audio, _metric, voices, _cost, _remaining = (
        langgraph_adapter._generate_scene_dialogue_audio(
            scene,
            "test-key",
            1000,
            output_dir=tmp_path,
        )
    )

    assert called_urls == [
        "https://api.elevenlabs.io/v1/text-to-speech/voice-ludovico",
        "https://api.elevenlabs.io/v1/text-to-speech/voice-alice",
    ]
    assert [turn["voice_id"] for turn in audio["dialogue_turns"]] == [
        "voice-ludovico",
        "voice-alice",
    ]
    assert [item["speaker_id"] for item in voices] == ["ludovico", "alice"]


def test_scene_audio_blocks_shared_voice_between_characters(
    monkeypatch, tmp_path: Path
) -> None:
    scene = enrich_scene_performance(_dialogue_scene())
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_LUDOVICO", "shared-voice")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_ALICE", "shared-voice")
    monkeypatch.setattr(
        langgraph_adapter.requests,
        "post",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200, content=b"valid-audio"
        ),
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_enhance_premium_audio",
        lambda _raw, output, _scene: {
            "path": output,
            "valid": True,
            "duration_seconds": 3.0,
            "bit_rate": 128000,
            "quality_score": 96.0,
            "issues": [],
            "loudness": {"input_i_lufs": -14.0, "target_i_lufs": -14.0},
        },
    )

    try:
        langgraph_adapter._generate_scene_dialogue_audio(
            scene,
            "test-key",
            1000,
            output_dir=tmp_path,
        )
    except ValueError as exc:
        assert "character_voice_not_unique" in str(exc)
    else:
        raise AssertionError("shared character voice must block dialogue generation")


def test_accented_character_name_maps_to_ascii_voice_env_key() -> None:
    assert langgraph_adapter._voice_env_key("Lóri") == "ELEVENLABS_VOICE_ID_LORI"


def test_legacy_chess_scene_migrates_to_two_character_dialogue() -> None:
    scene = enrich_scene_performance(
        {
            "scene_id": 7,
            "description": (
                "Alice e Ludovico jogam uma partida animada de xadrez "
                "sobre uma mesa de madeira."
            ),
            "must_include": ["Alice", "Ludovico", "tabuleiro de xadrez"],
        }
    )

    assert [turn["speaker_id"] for turn in scene["dialogue"]] == [
        "ludovico",
        "alice",
    ]
    assert validate_scene_performance(scene)["passed"] is True


def test_scene_contract_blocks_english_dramatic_metadata() -> None:
    scene = enrich_scene_performance(_dialogue_scene())
    scene["main_action"] = (
        "Alice and Ludovico are sitting at the tea table with the sugar bowl."
    )

    gate = validate_scene_performance(scene)

    assert gate["passed"] is False
    assert "scene_main_action_language_not_pt_br" in gate["blockers"]
