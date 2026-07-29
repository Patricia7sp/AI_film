from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open3d_implementation.core import langgraph_adapter  # noqa: E402
from open3d_implementation.core.fal_provider import FalJobResult  # noqa: E402


class FakeFalClient:
    def __init__(self, results: list[FalJobResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(
        self,
        model_id: str,
        inputs: dict[str, object],
        **_kwargs: object,
    ) -> FalJobResult:
        self.calls.append((model_id, inputs))
        return self.results.pop(0)

    def download(
        self,
        url: str,
        destination: str,
        **_kwargs: object,
    ) -> int:
        del url
        Path(destination).write_bytes(b"x" * 4096)
        return 4096


def _result(
    *,
    request_id: str,
    model_id: str,
    data: dict[str, object],
) -> FalJobResult:
    return FalJobResult(
        request_id=request_id,
        model_id=model_id,
        data=data,
        elapsed_seconds=3.0,
        queue_seconds=1.0,
        execution_seconds=2.0,
        status_history=("IN_QUEUE", "IN_PROGRESS", "COMPLETED"),
    )


def test_schnell_attempt_uses_supported_contract_and_skips_reference(
    monkeypatch,
    tmp_path: Path,
):
    image_path = tmp_path / "scene.png"
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(b"reference" * 256)
    client = FakeFalClient(
        [
            _result(
                request_id="flux-request",
                model_id="fal-ai/flux/schnell",
                data={"images": [{"url": "https://fal.media/files/test/scene.png"}]},
            )
        ]
    )
    monkeypatch.setenv("FAL_FLUX_MODEL_ID", "fal-ai/flux/schnell")
    monkeypatch.setenv("FAL_FLUX_INFERENCE_STEPS", "4")
    monkeypatch.setenv("FAL_FLUX_ACCELERATION", "none")
    monkeypatch.setattr(
        langgraph_adapter.FalQueueClient,
        "from_environment",
        lambda: client,
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_probe_image_quality",
        lambda *_args, **_kwargs: {"valid": True, "quality_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_evaluate_image_semantics",
        lambda *_args, **_kwargs: {"accepted": True, "semantic_score": 96},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_combine_image_quality",
        lambda technical, semantic: {
            **technical,
            **semantic,
            "semantic_accepted": True,
            "issues": [],
        },
    )
    scene = {
        "scene_id": 1,
        "prompt": "Alice finds the tiny sugar mouse.",
        "duration": 5,
    }

    job, image, metric = langgraph_adapter._run_fal_flux_image_attempt(
        scene=scene,
        image_path=str(image_path),
        directed_prompt="premium comic story frame",
        image_style="comic_storybook",
        style_label="Comic storybook",
        quality_preset_key="high",
        quality_preset={"width": 768, "height": 1024, "steps": 28},
        scene_seed=123,
        visual_bible={"characters": []},
        attempt=1,
        reference_image_path=str(reference_path),
    )

    assert job["status"] == "COMPLETED"
    assert image and image["generation_method"] == "fal_flux1_schnell"
    assert metric and metric["semantic_accepted"] is True
    assert client.calls[0][0] == "fal-ai/flux/schnell"
    assert client.calls[0][1]["num_inference_steps"] == 4
    assert client.calls[0][1]["acceleration"] == "none"
    assert "reference_image_url" not in client.calls[0][1]
    assert "loras" not in client.calls[0][1]
    assert job["identity_conditioning"] == "prompt_seed_only"
    assert job["reference_image_applied"] is False
    assert job["lora_count"] == 0


def test_nano_banana_edit_uses_multiple_canonical_references(
    monkeypatch,
    tmp_path: Path,
):
    image_path = tmp_path / "scene.png"
    front_path = tmp_path / "alice_front.png"
    full_body_path = tmp_path / "alice_full_body.png"
    front_path.write_bytes(b"front-reference" * 256)
    full_body_path.write_bytes(b"full-body-reference" * 256)
    client = FakeFalClient(
        [
            _result(
                request_id="nano-banana-request",
                model_id="fal-ai/nano-banana/edit",
                data={"images": [{"url": "https://fal.media/files/test/scene.png"}]},
            )
        ]
    )
    monkeypatch.setattr(
        langgraph_adapter.FalQueueClient,
        "from_environment",
        lambda: client,
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_probe_image_quality",
        lambda *_args, **_kwargs: {"valid": True, "quality_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_evaluate_image_semantics",
        lambda *_args, **_kwargs: {"accepted": True, "semantic_score": 96},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_combine_image_quality",
        lambda technical, semantic: {
            **technical,
            **semantic,
            "semantic_accepted": True,
            "issues": [],
        },
    )

    job, image, metric = langgraph_adapter._run_fal_reference_edit_attempt(
        scene={
            "scene_id": 1,
            "prompt": "Alice discovers a tiny mouse under an oak tree.",
            "duration": 5,
        },
        image_path=str(image_path),
        directed_prompt="Premium cartoon story frame in a sunlit garden.",
        image_style="comic_storybook",
        style_label="Comic storybook",
        quality_preset_key="high",
        quality_preset={"width": 832, "height": 1216},
        scene_seed=123,
        visual_bible={"cast_bible": {"characters": []}},
        attempt=1,
        reference_image_paths=[str(front_path), str(full_body_path)],
    )

    assert job["status"] == "COMPLETED"
    assert job["identity_conditioning"] == "canonical_multi_reference_edit"
    assert job["reference_image_count"] == 2
    assert job["estimated_cost_usd"] == 0.039
    assert image and image["generation_method"] == "fal_nano_banana_edit"
    assert metric and metric["semantic_accepted"] is True
    assert client.calls[0][0] == "fal-ai/nano-banana/edit"
    assert len(client.calls[0][1]["image_urls"]) == 2
    assert all(
        str(value).startswith("data:image/png;base64,")
        for value in client.calls[0][1]["image_urls"]
    )
    assert client.calls[0][1]["aspect_ratio"] == "2:3"
    assert client.calls[0][1]["limit_generations"] is True
    assert "CANONICAL REFERENCE LOCK" in str(client.calls[0][1]["prompt"])


def test_fal_cast_reference_separates_identity_from_pose_guide(
    monkeypatch,
    tmp_path: Path,
):
    image_path = tmp_path / "edith_three_quarter.png"
    anchor_path = tmp_path / "edith_character_reference_front.png"
    pose_path = tmp_path / "edith_three_quarter_pose_guide.png"
    anchor_path.write_bytes(b"anchor" * 1024)
    pose_path.write_bytes(b"pose" * 1024)
    client = FakeFalClient(
        [
            _result(
                request_id="pose-guided-request",
                model_id="fal-ai/nano-banana/edit",
                data={"images": [{"url": "https://fal.media/files/test/edith.png"}]},
            )
        ]
    )
    monkeypatch.setattr(
        langgraph_adapter.FalQueueClient,
        "from_environment",
        lambda: client,
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_probe_image_quality",
        lambda *_args, **_kwargs: {"valid": True, "quality_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_evaluate_image_semantics",
        lambda *_args, **_kwargs: {"accepted": True, "semantic_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_combine_image_quality",
        lambda technical, semantic: {
            **technical,
            **semantic,
            "semantic_accepted": True,
            "issues": [],
        },
    )

    job, _image, _metric = langgraph_adapter._run_fal_reference_edit_attempt(
        scene={
            "scene_id": "edith_reference",
            "scene_role": "character_reference",
            "prompt": "Edith three-quarter reference.",
            "duration": 0,
        },
        image_path=str(image_path),
        directed_prompt="Strict three-quarter Cast Bible reference.",
        image_style="comic_storybook",
        style_label="Comic storybook",
        quality_preset_key="high",
        quality_preset={"width": 896, "height": 1152},
        scene_seed=456,
        visual_bible={"cast_bible": {"characters": []}},
        attempt=1,
        reference_image_paths=[str(anchor_path), str(pose_path)],
    )

    prompt = str(client.calls[0][1]["prompt"])
    assert job["status"] == "COMPLETED"
    assert "POSE GUIDE CONTRACT" in prompt
    assert "edith_three_quarter_pose_guide" in prompt
    assert "control pose and framing only" in prompt
    assert "Never copy their colors, line art, anatomy or identity" in prompt


def test_fal_three_quarter_uses_front_profile_pose_bracket(
    monkeypatch,
    tmp_path: Path,
):
    image_path = tmp_path / "edith_three_quarter.png"
    front_path = tmp_path / "edith_character_reference_front.png"
    profile_path = tmp_path / "edith_character_reference_profile.png"
    front_path.write_bytes(b"front" * 1024)
    profile_path.write_bytes(b"profile" * 1024)
    client = FakeFalClient(
        [
            _result(
                request_id="pose-bracket-request",
                model_id="fal-ai/nano-banana/edit",
                data={"images": [{"url": "https://fal.media/files/test/edith.png"}]},
            )
        ]
    )
    monkeypatch.setattr(
        langgraph_adapter.FalQueueClient,
        "from_environment",
        lambda: client,
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_probe_image_quality",
        lambda *_args, **_kwargs: {"valid": True, "quality_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_evaluate_image_semantics",
        lambda *_args, **_kwargs: {"accepted": True, "semantic_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_combine_image_quality",
        lambda technical, semantic: {
            **technical,
            **semantic,
            "semantic_accepted": True,
            "issues": [],
        },
    )

    job, _image, _metric = langgraph_adapter._run_fal_reference_edit_attempt(
        scene={
            "scene_id": "edith_reference",
            "scene_role": "character_reference",
            "reference_view_id": "three_quarter",
            "prompt": "Edith three-quarter reference.",
            "duration": 0,
        },
        image_path=str(image_path),
        directed_prompt="Strict three-quarter Cast Bible reference.",
        image_style="comic_storybook",
        style_label="Comic storybook",
        quality_preset_key="high",
        quality_preset={"width": 896, "height": 1152},
        scene_seed=789,
        visual_bible={"cast_bible": {"characters": []}},
        attempt=1,
        reference_image_paths=[str(front_path), str(profile_path)],
    )

    prompt = str(client.calls[0][1]["prompt"])
    assert job["status"] == "COMPLETED"
    assert "THREE-QUARTER POSE BRACKET" in prompt
    assert "exact halfway head orientation" in prompt
    assert "one cheek narrower" in prompt
    assert "POSE GUIDE CONTRACT" not in prompt


def test_scene_reference_selection_uses_approved_identity_wardrobe_and_body_views(
    monkeypatch,
    tmp_path: Path,
):
    paths = {}
    for view_id in ("three_quarter", "full_body", "front"):
        path = tmp_path / f"alice_{view_id}.png"
        path.write_bytes(view_id.encode("utf-8") * 1024)
        paths[view_id] = str(path)
    monkeypatch.setenv("FAL_REFERENCE_MAX_IMAGES", "3")
    views = {
        view_id: {
            "approved": True,
            "human_approved": True,
            "checksum": f"checksum-{view_id}",
            "path": path,
        }
        for view_id, path in paths.items()
    }
    visual_bible = {
        "cast_bible": {
            "characters": [
                {
                    "id": "alice",
                    "name": "Alice",
                    "role": "protagonist",
                    "aliases": ["Alice"],
                    "reference": {
                        "approved": True,
                        "human_approved": True,
                        "checksum": "pack-checksum",
                        "path": paths["three_quarter"],
                        "required_views": list(views),
                        "views": views,
                    },
                }
            ]
        }
    }

    selected = langgraph_adapter._scene_reference_image_paths(
        {"scene_id": 1, "prompt": "Alice opens the red book."},
        visual_bible,
    )

    assert selected == [
        paths["three_quarter"],
        paths["full_body"],
        paths["front"],
    ]


def test_instant_character_attempt_applies_reference_image(
    monkeypatch,
    tmp_path: Path,
):
    image_path = tmp_path / "derived.png"
    reference_path = tmp_path / "front.png"
    reference_path.write_bytes(b"reference" * 256)
    client = FakeFalClient(
        [
            _result(
                request_id="identity-request",
                model_id="fal-ai/instant-character",
                data={"images": [{"url": "https://fal.media/files/test/derived.png"}]},
            )
        ]
    )
    monkeypatch.setattr(
        langgraph_adapter.FalQueueClient,
        "from_environment",
        lambda: client,
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_probe_image_quality",
        lambda *_args, **_kwargs: {"valid": True, "quality_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_evaluate_image_semantics",
        lambda *_args, **_kwargs: {"accepted": True, "semantic_score": 96},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_combine_image_quality",
        lambda technical, semantic: {
            **technical,
            **semantic,
            "semantic_accepted": True,
            "issues": [],
        },
    )

    job, image, metric = langgraph_adapter._run_fal_instant_character_attempt(
        scene={
            "scene_id": "alice_reference_profile",
            "prompt": "Strict profile reference of Alice.",
            "duration": 5,
        },
        image_path=str(image_path),
        directed_prompt="Strict profile reference of the same Alice.",
        image_style="comic_storybook",
        style_label="Comic storybook",
        quality_preset_key="cast_reference",
        quality_preset={"width": 768, "height": 1024},
        scene_seed=456,
        visual_bible={"characters": []},
        attempt=1,
        reference_image_path=str(reference_path),
    )

    assert job["status"] == "COMPLETED"
    assert job["identity_conditioning"] == "instant_character_reference"
    assert job["reference_image_applied"] is True
    assert image and image["generation_method"] == "fal_instant_character"
    assert image["controlled_workflow"] is True
    assert metric and metric["semantic_accepted"] is True
    assert client.calls[0][0] == "fal-ai/instant-character"
    assert str(client.calls[0][1]["image_url"]).startswith("data:image/png;base64,")


def test_flux_pulid_attempt_applies_human_identity_reference(
    monkeypatch,
    tmp_path: Path,
):
    from PIL import Image

    image_path = tmp_path / "derived.png"
    reference_path = tmp_path / "front.png"
    Image.new("RGB", (64, 64), "white").save(reference_path, format="PNG")

    class ValidImageFalClient(FakeFalClient):
        def download(
            self,
            url: str,
            destination: str,
            **_kwargs: object,
        ) -> int:
            del url
            Image.effect_noise((512, 512), 32).convert("RGB").save(
                destination,
                format="JPEG",
            )
            return Path(destination).stat().st_size

    client = ValidImageFalClient(
        [
            _result(
                request_id="pulid-request",
                model_id="fal-ai/flux-pulid",
                data={"images": [{"url": "https://fal.media/files/test/derived.jpg"}]},
            )
        ]
    )
    monkeypatch.setattr(
        langgraph_adapter.FalQueueClient,
        "from_environment",
        lambda: client,
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_probe_image_quality",
        lambda *_args, **_kwargs: {"valid": True, "quality_score": 100},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_evaluate_image_semantics",
        lambda *_args, **_kwargs: {"accepted": True, "semantic_score": 96},
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_combine_image_quality",
        lambda technical, semantic: {
            **technical,
            **semantic,
            "semantic_accepted": True,
            "issues": [],
        },
    )

    job, image, metric = langgraph_adapter._run_fal_flux_pulid_attempt(
        scene={
            "scene_id": "alice_reference_profile",
            "prompt": "Strict profile reference of Alice.",
            "duration": 5,
        },
        image_path=str(image_path),
        directed_prompt="Strict profile reference of the same Alice.",
        image_style="comic_storybook",
        style_label="Comic storybook",
        quality_preset_key="cast_reference",
        quality_preset={"width": 768, "height": 1024},
        scene_seed=456,
        visual_bible={"characters": []},
        attempt=1,
        reference_image_path=str(reference_path),
    )

    assert job["status"] == "COMPLETED"
    assert job["identity_conditioning"] == "flux_pulid_reference"
    assert job["reference_image_applied"] is True
    assert image and image["generation_method"] == "fal_flux_pulid"
    assert image["controlled_workflow"] is True
    assert metric and metric["semantic_accepted"] is True
    assert client.calls[0][0] == "fal-ai/flux-pulid"
    assert str(client.calls[0][1]["reference_image_url"]).startswith(
        "data:image/png;base64,"
    )
    assert client.calls[0][1]["num_inference_steps"] == 20
    assert client.calls[0][1]["id_weight"] == 1.0
    with Image.open(image_path) as normalized_image:
        assert normalized_image.format == "PNG"


def test_cast_reference_strategy_uses_schnell_only_without_anchor():
    assert (
        langgraph_adapter._fal_cast_reference_strategy(
            character_kind="human",
            derived_reference_view=False,
            has_anchor=False,
        )
        == "flux_schnell"
    )
    assert (
        langgraph_adapter._fal_cast_reference_strategy(
            character_kind="human",
            derived_reference_view=True,
            has_anchor=True,
        )
        == "nano_banana_edit"
    )
    assert (
        langgraph_adapter._fal_cast_reference_strategy(
            character_kind="animal",
            derived_reference_view=True,
            has_anchor=True,
        )
        == "nano_banana_edit"
    )


def test_kling_runs_image_to_video_then_audio_to_video(
    monkeypatch,
    tmp_path: Path,
):
    image_path = tmp_path / "scene.png"
    audio_path = tmp_path / "scene.mp3"
    clip_path = tmp_path / "scene.mp4"
    image_path.write_bytes(b"image" * 1024)
    audio_path.write_bytes(b"audio" * 1024)
    client = FakeFalClient(
        [
            _result(
                request_id="animation-request",
                model_id="fal-ai/kling-video/v3/standard/image-to-video",
                data={"video": {"url": "https://fal.media/files/test/animation.mp4"}},
            ),
            _result(
                request_id="lipsync-request",
                model_id="fal-ai/kling-video/lipsync/audio-to-video",
                data={"video": {"url": "https://fal.media/files/test/lipsync.mp4"}},
            ),
        ]
    )
    monkeypatch.setenv("FAL_KLING_LIPSYNC_ENABLED", "true")
    monkeypatch.setattr(
        langgraph_adapter.FalQueueClient,
        "from_environment",
        lambda: client,
    )
    monkeypatch.setattr(
        langgraph_adapter,
        "_probe_media_quality",
        lambda _path, media_type: {
            "valid": True,
            "quality_score": 98,
            "duration_seconds": 5.0,
            "issues": [],
            "media_type": media_type,
        },
    )

    job, ok = langgraph_adapter._generate_fal_kling_clip(
        {
            "scene_id": 1,
            "image_path": str(image_path),
            "prompt": "Alice speaks beside the old tree.",
            "camera_motion": "slow push-in",
        },
        str(clip_path),
        5.0,
        audio_path=str(audio_path),
        visual_bible={"characters": []},
    )

    assert ok is True
    assert job["job_id"] == "lipsync-request"
    assert job["animation_job_id"] == "animation-request"
    assert job["lipsync_status"] == "COMPLETED"
    assert len(client.calls) == 2
    assert client.calls[0][1]["generate_audio"] is False
    assert client.calls[1][1]["video_url"] == (
        "https://fal.media/files/test/animation.mp4"
    )
    assert str(client.calls[1][1]["audio_url"]).startswith("data:audio/mpeg;base64,")


def test_provider_aliases_are_normalized(monkeypatch):
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "fal_flux1")
    monkeypatch.setenv("VIDEO_GENERATION_PROVIDER", "kling3")

    assert langgraph_adapter._image_generation_provider() == "fal"
    assert langgraph_adapter._video_generation_provider() == "fal_kling"


def test_default_fal_image_model_is_schnell(monkeypatch):
    monkeypatch.delenv("FAL_FLUX_MODEL_ID", raising=False)

    assert langgraph_adapter._fal_flux_model() == "fal-ai/flux/schnell"


def test_default_fal_reference_model_is_nano_banana(monkeypatch):
    monkeypatch.delenv("FAL_REFERENCE_EDIT_MODEL_ID", raising=False)

    assert langgraph_adapter._fal_reference_edit_model() == "fal-ai/nano-banana/edit"
