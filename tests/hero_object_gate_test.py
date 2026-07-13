import base64
import inspect
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open3d_implementation import ui_server  # noqa: E402
from open3d_implementation.core import langgraph_adapter  # noqa: E402
from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    DEFAULT_IMAGE_STYLE,
    _audio_quality_gate,
    _build_comfyui_workflow,
    _build_image_prompt,
    _build_scene_contract,
    _combine_image_quality,
    _comfyui_control_image_mode,
    _comfyui_controlnet_model,
    _comfyui_refiner_enabled,
    _elevenlabs_voice_id_for_scene,
    _encode_comfyui_control_image,
    _hero_object_requirements,
    _image_generation_provider,
    _premium_audio_direction,
    _premium_audio_narration,
    _probe_image_quality,
    _resolve_comfyui_checkpoint,
    _resolve_quality_preset,
    _scene_negative_prompt,
)
from scripts import smoke_comfyui_controlnet_retry as controlnet_smoke  # noqa: E402


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
    assert "Controlled hero-object composition" in prompt
    assert "The mouse is a small natural animal" in prompt
    assert "Alice is a 10-year-old Victorian child" in prompt
    assert "no cup handle" in prompt

    negative_prompt = _scene_negative_prompt(scene)
    assert "anthropomorphic mouse" in negative_prompt
    assert "mouse as main character" in negative_prompt
    assert "black mouse" in negative_prompt
    assert "solid black mouse head" in negative_prompt
    assert "teacup" in negative_prompt
    assert "cup handle" in negative_prompt
    assert "saucer" in negative_prompt
    assert negative_prompt.index("teacup") < negative_prompt.index("low quality")
    assert negative_prompt.index("cup handle") < negative_prompt.index("low quality")
    assert len(negative_prompt) <= 1200


def test_turbo_quality_preset_is_available_for_sdxl_turbo_models():
    preset = _resolve_quality_preset("turbo")

    assert preset["steps"] == 8
    assert preset["cfg"] == 2.0


def test_high_quality_preset_matches_juggernaut_xl_recommendation():
    preset = _resolve_quality_preset("high")

    assert preset["steps"] == 35
    assert preset["cfg"] == 5.0
    assert preset["sampler_name"] == "dpmpp_2m"
    assert preset["scheduler"] == "karras"


def test_anthropomorphic_hero_object_failure_requires_controlled_workflow():
    metrics = _combine_image_quality(
        {
            "valid": True,
            "quality_score": 78.0,
            "issues": [],
        },
        {
            "semantic_score": 42,
            "accepted": False,
            "issues": ["anthropomorphic_mouse", "hero_object_legibility_failed"],
            "critical_failures": ["hero_object_missing"],
            "hero_objects": [{"name": "white mouse emerging from open sugar bowl"}],
            "hero_object_legibility": False,
            "hero_object_notes": "mouse became a clothed character",
            "retry_prompt": "Make the mouse natural and tiny.",
        },
    )

    assert metrics["control_workflow_required"] is True
    assert metrics["recommended_generation_strategy"] == "controlled_inpaint"
    assert "control_workflow_required" in metrics["issues"]
    assert "plain txt2img retry" in metrics["operator_next_action"]


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


def test_image_generation_defaults_to_comfyui_comic_storybook(monkeypatch):
    monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("COMFYUI_DEFAULT_CHECKPOINT", raising=False)
    monkeypatch.delenv("COMFYUI_CHECKPOINT_COMIC_STORYBOOK", raising=False)

    assert DEFAULT_IMAGE_STYLE == "comic_storybook"
    assert _image_generation_provider() == "comfyui"
    assert _resolve_comfyui_checkpoint("comic_storybook") == (
        "ai-film-semantic-juggernaut-xl.safetensors"
    )


def test_selective_visual_retry_has_comfyui_path_not_hidden_gemini_default():
    source = inspect.getsource(ui_server._run_selective_visual_retry)

    assert "_run_comfyui_image_attempt" in source
    assert 'os.getenv("IMAGE_GENERATION_PROVIDER", "comfyui")' in source
    assert "comfyui_retry_missing_runpod_credentials" in source
    assert "controlled_workflow=controlled_workflow" in source
    assert "control_image_path=" in source


def test_controlnet_workflow_injects_controlnet_nodes():
    workflow = _build_comfyui_workflow(
        directed_prompt="story frame",
        checkpoint_name="ai-film-semantic-juggernaut-xl.safetensors",
        quality_preset=_resolve_quality_preset("turbo"),
        scene_seed=123,
        scene_id=2,
        controlled_workflow=True,
        controlnet_name="controlnet-canny-sdxl-1.0.safetensors",
        control_image_name="reference_edges.png",
    )

    assert workflow["8"]["class_type"] == "LoadImage"
    assert workflow["8"]["inputs"]["image"] == "reference_edges.png"
    assert workflow["9"]["class_type"] == "ControlNetLoader"
    assert workflow["9"]["inputs"]["control_net_name"] == (
        "controlnet-canny-sdxl-1.0.safetensors"
    )
    assert workflow["10"]["class_type"] == "ControlNetApply"
    assert workflow["3"]["inputs"]["positive"] == ["10", 0]


def test_ipadapter_reference_conditions_model_without_replacing_scene_prompt():
    workflow = _build_comfyui_workflow(
        directed_prompt="Alice examines a small sugar bowl",
        checkpoint_name="ai-film-semantic-juggernaut-xl.safetensors",
        quality_preset=_resolve_quality_preset("high"),
        scene_seed=123,
        scene_id=2,
        reference_image_name="alice_reference.png",
        ipadapter_enabled=True,
        ipadapter_weight=0.72,
    )

    assert workflow["20"]["class_type"] == "LoadImage"
    assert workflow["20"]["inputs"]["image"] == "alice_reference.png"
    assert workflow["21"]["class_type"] == "IPAdapterUnifiedLoader"
    assert workflow["21"]["inputs"]["preset"] == "PLUS (high strength)"
    assert workflow["22"]["class_type"] == "IPAdapterAdvanced"
    assert workflow["22"]["inputs"]["image"] == ["20", 0]
    assert workflow["22"]["inputs"]["weight"] == 0.72
    assert workflow["22"]["inputs"]["end_at"] == 0.75
    assert workflow["3"]["inputs"]["model"] == ["22", 0]
    assert workflow["1"]["inputs"]["text"] == ("Alice examines a small sugar bowl")


def test_optional_style_lora_is_applied_before_ipadapter():
    workflow = _build_comfyui_workflow(
        directed_prompt="original comic storybook frame",
        checkpoint_name="ai-film-semantic-juggernaut-xl.safetensors",
        quality_preset=_resolve_quality_preset("high"),
        scene_seed=321,
        scene_id=1,
        style_lora_name="ai-film-original-storybook.safetensors",
        style_lora_strength=0.65,
        reference_image_name="alice_reference.png",
        ipadapter_enabled=True,
    )

    assert workflow["23"]["class_type"] == "LoraLoader"
    assert workflow["23"]["inputs"]["lora_name"] == (
        "ai-film-original-storybook.safetensors"
    )
    assert workflow["1"]["inputs"]["clip"] == ["23", 1]
    assert workflow["21"]["inputs"]["model"] == ["23", 0]
    assert workflow["22"]["inputs"]["model"] == ["21", 0]


def test_controlled_workflow_inpaints_hero_region_then_refines(monkeypatch):
    monkeypatch.delenv("COMFYUI_REFINER_SCALE", raising=False)
    monkeypatch.delenv("COMFYUI_REFINER_DENOISE", raising=False)
    monkeypatch.delenv("COMFYUI_CONTROLNET_STRENGTH", raising=False)
    workflow = _build_comfyui_workflow(
        directed_prompt="story frame",
        checkpoint_name="ai-film-semantic-juggernaut-xl.safetensors",
        quality_preset=_resolve_quality_preset("high"),
        scene_seed=123,
        scene_id=2,
        controlled_workflow=True,
        controlnet_name="controlnet-canny-sdxl-1.0.safetensors",
        control_image_name="hero_structure.png",
        inpaint_image_name="approved_base_with_mask.png",
        refiner_enabled=True,
        refiner_checkpoint_name="ai-film-dreamshaper-xl-turbo-sfw.safetensors",
        diagnostic_intermediate=True,
    )

    assert workflow["11"]["class_type"] == "LoadImage"
    assert workflow["11"]["inputs"]["image"] == "approved_base_with_mask.png"
    assert workflow["12"]["class_type"] == "VAEEncodeForInpaint"
    assert workflow["3"]["inputs"]["latent_image"] == ["12", 0]
    assert 0.80 <= workflow["3"]["inputs"]["denoise"] < 1
    assert workflow["13"]["class_type"] == "LatentUpscaleBy"
    assert workflow["13"]["inputs"]["scale_by"] == 1.25
    assert workflow["14"]["class_type"] == "KSampler"
    assert workflow["14"]["inputs"]["denoise"] < workflow["3"]["inputs"]["denoise"]
    assert workflow["14"]["inputs"]["steps"] == 6
    assert workflow["14"]["inputs"]["cfg"] == 2.0
    assert workflow["14"]["inputs"]["denoise"] == 0.18
    assert workflow["14"]["inputs"]["model"] == ["15", 0]
    assert workflow["14"]["inputs"]["positive"] == ["10", 0]
    assert workflow["14"]["inputs"]["negative"] == ["17", 0]
    assert workflow["10"]["inputs"]["strength"] == 0.78
    assert "16" not in workflow
    assert workflow["15"]["inputs"]["ckpt_name"] == (
        "ai-film-dreamshaper-xl-turbo-sfw.safetensors"
    )
    assert workflow["6"]["inputs"]["samples"] == ["14", 0]
    assert workflow["18"]["class_type"] == "VAEDecode"
    assert workflow["18"]["inputs"]["samples"] == ["3", 0]
    assert workflow["19"]["class_type"] == "SaveImage"
    assert workflow["19"]["inputs"]["filename_prefix"].endswith("_base_inpaint")


def test_controlnet_smoke_uses_production_prompt_contract():
    assert hasattr(controlnet_smoke, "_build_smoke_workflow")

    workflow, _scene = controlnet_smoke._build_smoke_workflow()
    positive = workflow["1"]["inputs"]["text"]
    negative = workflow["2"]["inputs"]["text"]

    assert "no cup handle" in positive
    assert "teacup" in negative
    assert "cup handle" in negative
    assert "saucer" in negative
    assert workflow["9"]["inputs"]["control_net_name"] == (
        "controlnet-depth-sdxl-1.0.safetensors"
    )
    assert "13" not in workflow
    assert "14" not in workflow
    assert "15" not in workflow


def test_controlnet_smoke_saves_intermediate_and_final_outputs(tmp_path):
    assert hasattr(controlnet_smoke, "_save_workflow_images")
    intermediate_bytes = b"base-inpaint" * 120
    final_bytes = b"final-image" * 120
    payload = {
        "output": {
            "images": [
                {
                    "filename": "scene_smoke_base_inpaint_00001_.png",
                    "data": base64.b64encode(intermediate_bytes).decode("ascii"),
                },
                {
                    "filename": "scene_smoke_00001_.png",
                    "data": base64.b64encode(final_bytes).decode("ascii"),
                },
            ]
        }
    }
    final_path = tmp_path / "result.png"

    saved = controlnet_smoke._save_workflow_images(payload, final_path)

    assert final_path.read_bytes() == final_bytes
    intermediate_path = Path(saved["intermediate_path"])
    assert intermediate_path.read_bytes() == intermediate_bytes
    assert intermediate_path.name == "result_base_inpaint.png"


def test_inpaint_reference_masks_only_the_small_hero_object_region(tmp_path):
    from PIL import Image

    assert hasattr(langgraph_adapter, "_encode_comfyui_inpaint_image")
    source = tmp_path / "approved.png"
    Image.new("RGB", (320, 480), "#d6c7a8").save(source)
    scene = {
        "description": "Um ratinho branco surge do acucareiro aberto.",
        "must_include": ["white mouse emerging from open sugar bowl"],
    }

    encoded = langgraph_adapter._encode_comfyui_inpaint_image(
        str(source),
        image_name="inpaint.png",
        width=320,
        height=480,
        scene=scene,
    )
    image_bytes = base64.b64decode(encoded["image"].split(",", 1)[1])
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")

    assert image.getpixel((10, 10))[3] == 255
    assert image.getpixel((160, 290))[3] == 0


def test_semantic_hero_control_image_draws_story_structure(monkeypatch, tmp_path):
    from PIL import Image

    monkeypatch.setenv("COMFYUI_CONTROL_IMAGE_MODE", "semantic_hero")
    source = tmp_path / "source.png"
    Image.new("RGB", (64, 64), "black").save(source)
    scene = {
        "description": (
            "Na sala de jantar vitoriana, um pequeno ratinho branco surge do "
            "açucareiro aberto sobre a mesa."
        ),
        "must_include": [
            "open porcelain sugar bowl",
            "tiny natural white mouse peeking from the sugar bowl",
        ],
    }

    encoded = _encode_comfyui_control_image(
        str(source),
        image_name="control.png",
        width=320,
        height=480,
        scene=scene,
    )
    image_bytes = base64.b64decode(encoded["image"].split(",", 1)[1])
    control = Image.open(BytesIO(image_bytes)).convert("L")
    bright_pixels = sum(1 for value in control.getdata() if value > 180)

    assert encoded["name"] == "control.png"
    assert bright_pixels > 1500


def test_semantic_depth_control_image_uses_filled_volume_not_visible_line_art(
    monkeypatch,
    tmp_path,
):
    from PIL import Image

    monkeypatch.setenv("COMFYUI_CONTROL_IMAGE_MODE", "semantic_depth")
    source = tmp_path / "source.png"
    Image.new("RGB", (64, 64), "black").save(source)
    scene = {
        "description": "Um ratinho branco surge do acucareiro aberto.",
        "must_include": ["white mouse emerging from open sugar bowl"],
    }

    encoded = _encode_comfyui_control_image(
        str(source),
        image_name="depth.png",
        width=320,
        height=480,
        scene=scene,
    )
    image_bytes = base64.b64decode(encoded["image"].split(",", 1)[1])
    depth = Image.open(BytesIO(image_bytes)).convert("L")

    assert depth.getpixel((160, 305)) >= 180
    assert depth.getpixel((20, 20)) <= 40
    assert len(set(depth.getdata())) >= 4


def test_depth_controlnet_and_single_pass_are_controlled_retry_defaults(monkeypatch):
    monkeypatch.delenv("COMFYUI_CONTROL_IMAGE_MODE", raising=False)
    monkeypatch.delenv("COMFYUI_CONTROLNET_DEPTH_MODEL", raising=False)
    monkeypatch.delenv("COMFYUI_REFINER_ENABLED", raising=False)

    assert _comfyui_control_image_mode() == "semantic_depth"
    assert _comfyui_controlnet_model() == "controlnet-depth-sdxl-1.0.safetensors"
    assert _comfyui_refiner_enabled() is False


def test_blurry_image_fails_technical_quality_gate(tmp_path):
    from PIL import Image, ImageFilter

    source = tmp_path / "blurred.png"
    image = Image.new("RGB", (512, 512), "#bca98e")
    image = image.filter(ImageFilter.GaussianBlur(radius=8))
    image.save(source)

    technical = _probe_image_quality(str(source))
    combined = _combine_image_quality(
        technical,
        {
            "semantic_score": 96,
            "accepted": True,
            "issues": [],
            "critical_failures": [],
            "hero_objects": [],
        },
    )

    assert "blurry_image" in technical["issues"]
    assert "technical_quality_below_threshold" in combined["issues"]
    assert combined["technical_accepted"] is False
    assert combined["semantic_accepted"] is False


def test_hero_object_sharpness_uses_focal_region_not_cinematic_background(tmp_path):
    from PIL import Image, ImageDraw, ImageFilter

    source = tmp_path / "focused_hero.png"
    background = Image.new("RGB", (512, 512), "#bca98e").filter(
        ImageFilter.GaussianBlur(radius=8)
    )
    draw = ImageDraw.Draw(background)
    for offset in range(150, 365, 12):
        draw.line((offset, 210, offset, 380), fill="#171717", width=4)
    background.save(source)
    scene = {
        "description": "Um ratinho branco surge do acucareiro aberto.",
        "must_include": ["white mouse emerging from open sugar bowl"],
    }

    technical = _probe_image_quality(str(source), scene=scene)

    assert technical["sharpness_gate_scope"] == "hero_object"
    assert technical["focal_edge_sharpness"] >= 24
    assert "blurry_image" not in technical["issues"]


def test_visual_retry_blocks_when_controlled_workflow_is_required_but_unavailable(
    monkeypatch,
):
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "comfyui")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_ENDPOINT_ID", raising=False)
    summary = {
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 2,
                    "control_workflow_required": True,
                    "recommended_generation_strategy": "controlled_inpaint",
                    "operator_next_action": "Use inpaint before retrying.",
                    "issues": ["control_workflow_required"],
                }
            ]
        }
    }

    blocker = ui_server._controlled_retry_blocker(summary, "2", "image_video")

    assert blocker is not None
    assert blocker["error"] == "controlled_workflow_unavailable"
    assert blocker["recommended_generation_strategy"] == "controlled_inpaint"
    assert ui_server._controlled_retry_blocker(summary, "2", "audio") is None


def test_visual_retry_allows_controlled_workflow_when_runpod_controlnet_is_ready(
    monkeypatch,
):
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "comfyui")
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key")
    monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "test-endpoint")
    monkeypatch.setenv(
        "COMFYUI_CONTROLNET_CANNY_MODEL",
        "controlnet-canny-sdxl-1.0.safetensors",
    )
    summary = {
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 2,
                    "control_workflow_required": True,
                    "recommended_generation_strategy": "controlled_inpaint",
                }
            ]
        }
    }

    assert ui_server._controlled_retry_blocker(summary, "2", "image_video") is None


def test_cost_quota_blocks_publish_when_run_cost_exceeds_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_FILM_COST_LIMIT_USD", "0.50")
    video = tmp_path / "output" / "final_video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video-v1")
    summary = {
        "video_path": str(video),
        "video_exists": True,
        "scene_images": [{"scene_id": 1, "image_path": "scene.png"}],
        "scene_videos": [{"scene_id": 1, "video_path": "scene.mp4"}],
        "audio_files": [{"scene_id": 1, "audio_path": "scene.mp3"}],
        "quality_metrics": {
            "voices": [{"scene_id": 1, "premium_audio": True, "text_characters": 200}]
        },
        "cost_estimate": {"total_usd": 0.75, "elevenlabs_usd": 0.1},
        "curation": {
            "scenes": {
                "1": {
                    "status": "approved",
                    "active_attempt_id": "attempt_1",
                    "attempts": [],
                }
            },
            "final_review": {"status": "final_approved", "video_viewed": True},
        },
    }

    result = ui_server._apply_curation_summary(summary, tmp_path)

    assert result["cost_quota"]["status"] == "blocked"
    assert result["production_status"]["status"] == "blocked"
    assert result["curation"]["can_publish"] is False


def test_published_status_is_stale_when_current_video_hash_changes(tmp_path):
    video = tmp_path / "output" / "final_video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video-v1")
    summary = {
        "video_path": str(video),
        "video_exists": True,
        "scene_images": [{"scene_id": 1, "image_path": "scene.png"}],
        "scene_videos": [{"scene_id": 1, "video_path": "scene.mp4"}],
        "audio_files": [{"scene_id": 1, "audio_path": "scene.mp3"}],
        "quality_metrics": {},
        "cost_estimate": {"total_usd": 0.1},
        "curation": {
            "scenes": {
                "1": {
                    "status": "approved",
                    "active_attempt_id": "attempt_1",
                    "attempts": [],
                }
            },
            "final_review": {"status": "draft", "video_viewed": False},
        },
    }
    first = ui_server._apply_curation_summary(summary, tmp_path)
    artifact = first["production_status"]["current_artifact"]
    video.write_bytes(b"video-v2")
    first["publication"] = {
        "status": "published",
        "artifact": artifact,
        "url": "https://youtu.be/example",
    }

    result = ui_server._apply_curation_summary(first, tmp_path)

    assert result["production_status"]["status"] == "published_stale"
    assert result["production_status"]["published_current"] is False
    assert result["curation"]["can_publish"] is False
