"""Exercise the production dialogue gate without a media provider."""

import pytest

from open3d_implementation.core.dialogue_contract import production_dialogue_gate


@pytest.mark.parametrize(
    ("speaker_id", "speaker_name", "expected_blockers"),
    [
        pytest.param("lia", "Lia", [], id="declared-speaker"),
        pytest.param(
            "tom",
            "Tom",
            ["scene_1:turn_1_speaker_not_in_scene:tom"],
            id="speaker-outside-cast",
        ),
    ],
)
def test_production_dialogue_gate_checks_the_scene_cast(
    speaker_id: str, speaker_name: str, expected_blockers: list[str]
) -> None:
    scene = {
        "scene_id": "1",
        "description": f"{speaker_name} olha pela janela.",
        "characters_present": ["Lia"],
        "required_visual_elements": ["Lia", "janela"],
        "dialogue": [
            {
                "speaker_id": speaker_id,
                "speaker_name": speaker_name,
                "text_pt_br": "Cheguei cedo.",
                "action": f"{speaker_name} olha pela janela.",
                "mode": "dialogue",
                "lip_sync_required": True,
            },
        ],
    }
    audio = {
        "scene_id": "1",
        "dialogue_turns": [{"speaker_id": speaker_id, "voice_id": "fixture-voice"}],
    }
    video = {"scene_id": "1", "dialogue_segments": [{"turn_id": "turn-1"}]}

    result = production_dialogue_gate([scene], [audio], [video])

    assert result["blockers"] == expected_blockers
    assert result["passed"] is (not expected_blockers)
    assert result["scenes"][0]["turn_count"] == 1
