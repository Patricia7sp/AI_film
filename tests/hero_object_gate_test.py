import base64
import inspect
import json
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open3d_implementation import ui_server  # noqa: E402
from open3d_implementation.core import langgraph_adapter  # noqa: E402
from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    DEFAULT_IMAGE_STYLE,
    _apply_runpod_execution_telemetry,
    _audio_quality_gate,
    _build_comfyui_workflow,
    _build_flux2_image_prompt,
    _build_flux2_klein_workflow,
    _build_image_prompt,
    _build_qwen_image_edit_2511_workflow,
    _build_qwen_semantic_edit_prompt,
    _build_scene_contract,
    _character_reference_accepted,
    _combine_image_quality,
    _comfyui_control_image_mode,
    _comfyui_controlnet_model,
    _comfyui_model_family,
    _comfyui_refiner_enabled,
    _elevenlabs_voice_id_for_scene,
    _encode_comfyui_control_image,
    _encode_comfyui_reference_image,
    _evaluate_image_semantics,
    _evaluate_semantic_qa_with_local_vlm,
    _evaluate_semantic_qa_with_openai,
    _extract_response_text,
    _hero_object_focus_boxes,
    _hero_object_requirements,
    _image_generation_max_attempts,
    _image_generation_provider,
    _non_retryable_comfyui_job_error,
    _parse_semantic_qa_response,
    _premium_audio_direction,
    _premium_audio_narration,
    _probe_image_quality,
    _qwen_semantic_retry_enabled,
    _resolve_comfyui_checkpoint,
    _resolve_ipadapter_reference,
    _resolve_quality_preset,
    _scene_negative_prompt,
    _select_comfyui_retry_route,
    _semantic_retry_instruction,
    _submit_runpod_job,
)
from runpod_worker.validate_custom_nodes import (  # noqa: E402
    validate_ipadapter_nodes,
)
from scripts import smoke_comfyui_controlnet_retry as controlnet_smoke  # noqa: E402
from scripts import smoke_comfyui_ipadapter_sequence as ipadapter_smoke  # noqa: E402
from scripts import smoke_comfyui_staged_repair as staged_smoke  # noqa: E402
from scripts.runpod_endpoint_control import (  # noqa: E402
    redact_sensitive_values,
    update_endpoint_template_runtime,
    update_stopped_endpoint_gpu_types,
)


def _names(scene):
    return [item["name"] for item in _hero_object_requirements(scene)]


def test_qwen_semantic_retry_is_bounded_and_requires_a_rejected_flux_source(
    monkeypatch,
):
    monkeypatch.delenv("IMAGE_GENERATION_MAX_ATTEMPTS", raising=False)
    monkeypatch.setenv("COMFYUI_SEMANTIC_REPAIR_BACKEND", "qwen_image_edit_2511")

    assert _image_generation_max_attempts() == 4
    assert _qwen_semantic_retry_enabled("flux2_klein", "rejected.png") is True
    assert _qwen_semantic_retry_enabled("flux2_klein", None) is False
    assert _qwen_semantic_retry_enabled("sdxl", "rejected.png") is False

    monkeypatch.setenv("IMAGE_GENERATION_MAX_ATTEMPTS", "99")
    assert _image_generation_max_attempts() == 4


def test_semantic_retry_instruction_falls_back_to_scene_contract():
    scene = {
        "description": (
            "Alice, uma criança de 10 anos, observa Ludovico revelar um pequeno "
            "ratinho branco em um açucareiro aberto."
        ),
        "must_include": ["one small handleless sugar bowl", "one white mouse"],
        "must_not_include": ["serving bowl", "handles"],
    }

    instruction = _semantic_retry_instruction(
        scene,
        {
            "semantic_score": 82,
            "semantic_retry_prompt": "",
            "hero_object_notes": "Mouse visible, but physical scale is ambiguous.",
        },
    )

    assert "one normal tabletop handleless sugar bowl" in instruction
    assert "10-year-old Victorian child" in instruction
    assert "physical scale is ambiguous" in instruction
    assert "oversized serving bowl or tureen" in instruction


def test_qwen_semantic_edit_treats_rejected_source_as_untrusted():
    scene = {
        "description": (
            "Alice and professor Ludovico watch a tiny white mouse emerge from "
            "an open porcelain sugar bowl on a Victorian tea table."
        ),
        "must_include": ["one 10-year-old Alice", "one adult male Ludovico"],
        "must_not_include": ["second Alice", "handles", "oversized bowl"],
    }

    prompt = _build_qwen_semantic_edit_prompt(
        scene,
        "Replace the duplicate protagonist and correct the hero object.",
    )

    assert "rejected draft, not an approved identity reference" in prompt
    assert "do not crop, zoom or turn it square" in prompt
    assert "no more than 18 percent of the frame width" in prompt
    assert "show only its head and front paws" in prompt
    assert "Image 3" in prompt
    assert "never preserve a duplicate person" in prompt
    assert "one adult male mathematics professor" in prompt
    assert "handles on the sugar bowl" in prompt


def test_qwen_masked_semantic_edit_is_concise_and_uses_prop_as_image2():
    scene = {
        "description": (
            "Alice and professor Ludovico watch a tiny white mouse emerge from "
            "an open porcelain sugar bowl on a Victorian tea table."
        ),
        "must_include": ["one compact handleless sugar bowl", "one tiny white mouse"],
        "must_not_include": ["serving bowl", "handles", "oversized mouse"],
    }

    prompt = _build_qwen_semantic_edit_prompt(
        scene,
        "Replace only the rejected tabletop prop.",
        masked_edit=True,
        prop_reference_slot=2,
    )

    assert "Image 2" in prompt
    assert "Preserve every unmasked pixel exactly" in prompt
    assert "exact object design and physical proportions" in prompt
    assert len(prompt) <= 1200


def test_prop_reference_contract_does_not_inject_story_characters():
    scene = {
        "scene_id": "prop_reference",
        "scene_role": "prop_reference",
        "description": (
            "Isolated handleless sugar bowl, separate lid, teaspoon and tiny "
            "white mouse on a neutral background."
        ),
        "must_include": [
            "one compact handleless sugar bowl",
            "one teaspoon",
            "one tiny white mouse",
        ],
        "must_not_include": ["Alice", "Ludovico", "human", "hand"],
    }

    contract = _build_scene_contract(scene)
    prompt = _build_flux2_image_prompt(
        scene,
        "comic_storybook",
        {"style_label": "Comic storybook", "style_prompt": "clean comic linework"},
    )

    assert not any("Alice and Ludovico" in item for item in contract["required"])
    assert not any("Victorian tea table props" in item for item in contract["required"])
    assert "No person, face, hand, body" in prompt
    assert "Alice and Ludovico visible together" not in prompt


def test_qwen_reference_encoding_preserves_portrait_canvas(tmp_path):
    from PIL import Image

    source_path = tmp_path / "portrait.png"
    Image.new("RGB", (832, 1216), (80, 40, 20)).save(source_path)

    payload = _encode_comfyui_reference_image(
        str(source_path),
        image_name="scene.png",
        target_size=(832, 1216),
    )
    encoded = payload["image"].split(",", 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as encoded_image:
        assert encoded_image.size == (832, 1216)


def test_endpoint_details_redacts_nested_credentials():
    payload = {
        "id": "endpoint",
        "workers": [
            {
                "env": {
                    "RUNPOD_AI_API_KEY": "sensitive",
                    "RUNPOD_ENDPOINT_SECRET": "sensitive",
                    "RUNPOD_ENDPOINT_ID": "safe-id",
                }
            }
        ],
    }

    redacted = redact_sensitive_values(payload)

    worker_env = redacted["workers"][0]["env"]
    assert worker_env["RUNPOD_AI_API_KEY"] == "[REDACTED]"
    assert worker_env["RUNPOD_ENDPOINT_SECRET"] == "[REDACTED]"
    assert worker_env["RUNPOD_ENDPOINT_ID"] == "safe-id"


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
    assert "teaspoon" in contract["hero_objects"][0]["placement"]
    assert any("handles on the sugar bowl" == item for item in contract["forbidden"])
    assert any("oversized serving bowl" in item for item in contract["forbidden"])

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


def test_repeated_hero_object_scale_failure_requires_masked_inpaint():
    metrics = _combine_image_quality(
        {"valid": True, "quality_score": 98.8, "issues": []},
        {
            "semantic_score": 58,
            "accepted": False,
            "issues": ["oversized_props"],
            "critical_failures": ["mouse_filling_most_of_sugar_bowl"],
            "hero_objects": [{"name": "white mouse emerging from open sugar bowl"}],
            "hero_object_legibility": True,
            "retry_prompt": "Make the mouse tiny.",
        },
    )

    assert metrics["control_workflow_required"] is True
    assert metrics["recommended_generation_strategy"] == "masked_inpaint"
    assert "control_workflow_required" in metrics["issues"]
    assert "without ControlNet" in metrics["operator_next_action"]


def test_character_age_failure_takes_priority_over_isolated_prop_repair():
    metrics = _combine_image_quality(
        {"valid": True, "quality_score": 100.0, "issues": []},
        {
            "semantic_score": 58,
            "accepted": False,
            "issues": ["bowl_has_handle", "protagonist_too_old"],
            "critical_failures": ["character_age_inconsistency"],
            "hero_objects": [{"name": "white mouse emerging from open sugar bowl"}],
            "hero_object_legibility": True,
            "retry_prompt": "Make Alice a child and remove the handle.",
        },
    )

    assert metrics["control_workflow_required"] is True
    assert metrics["recommended_generation_strategy"] == "controlled_inpaint"
    assert "approved character reference" in metrics["operator_next_action"]


def test_flux2_retry_escalates_from_qwen_to_sdxl_control(monkeypatch):
    monkeypatch.setenv("COMFYUI_SEMANTIC_REPAIR_BACKEND", "qwen_image_edit_2511")

    second = _select_comfyui_retry_route(
        model_family="flux2_klein",
        attempt=2,
        repair_source_path="rejected.png",
        previous_metric={"recommended_generation_strategy": "txt2img_retry"},
    )
    third = _select_comfyui_retry_route(
        model_family="flux2_klein",
        attempt=3,
        repair_source_path="qwen-rejected.png",
        previous_metric={"recommended_generation_strategy": "controlled_inpaint"},
    )
    fourth = _select_comfyui_retry_route(
        model_family="flux2_klein",
        attempt=4,
        repair_source_path="sdxl-rejected.png",
        previous_metric={"recommended_generation_strategy": "masked_inpaint"},
    )

    assert second == (True, "qwen_image_edit_2511", "controlled_inpaint")
    assert third == (True, "sdxl", "controlled_inpaint")
    assert fourth == (True, "sdxl", "masked_inpaint")


def test_comfyui_pipeline_requires_an_approved_character_anchor():
    source = inspect.getsource(langgraph_adapter.create_open3d_workflow)

    assert 'image_provider == "comfyui"' in source
    assert "_build_character_reference_scene" in source
    assert "_character_reference_accepted(image_metric)" in source
    assert 'visual_bible["character_reference_image_path"]' in source
    assert "reference_image_path = reference_path" in source


def test_character_anchor_requires_explicit_semantic_acceptance():
    assert (
        _character_reference_accepted(
            {
                "quality_score": 92,
                "technical_accepted": True,
                "semantic_accepted": False,
                "semantic_score": 80,
                "semantic_critical_failures": [],
            }
        )
        is False
    )
    assert (
        _character_reference_accepted(
            {
                "quality_score": 94,
                "technical_accepted": True,
                "semantic_accepted": True,
                "semantic_score": 90,
                "semantic_critical_failures": [],
            }
        )
        is True
    )


def test_flux2_controlled_retry_uses_sdxl_inpaint_instead_of_dropping_control():
    source = inspect.getsource(langgraph_adapter._run_comfyui_image_attempt)

    assert "flux2_requested and not controlled_workflow" in source
    assert "effective_controlled_workflow = controlled_workflow" in source
    assert '"sdxl_controlnet_inpaint"' in source
    assert '"controlled_backend_fallback"' in source


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


def test_comfyui_model_family_is_explicit_and_safe_by_default(monkeypatch):
    monkeypatch.delenv("COMFYUI_MODEL_FAMILY", raising=False)
    assert _comfyui_model_family() == "sdxl"

    monkeypatch.setenv("COMFYUI_MODEL_FAMILY", "flux2_klein")
    assert _comfyui_model_family() == "flux2_klein"

    monkeypatch.setenv("COMFYUI_MODEL_FAMILY", "unknown")
    assert _comfyui_model_family() == "sdxl"


def test_flux2_klein_workflow_matches_official_comfyui_graph(monkeypatch):
    monkeypatch.delenv("COMFYUI_FLUX2_STEPS", raising=False)
    monkeypatch.delenv("COMFYUI_FLUX2_CFG", raising=False)
    workflow = _build_flux2_klein_workflow(
        directed_prompt="one child Alice reading beneath an oak tree",
        quality_preset=_resolve_quality_preset("high"),
        scene_seed=20260713,
        scene_id=1,
    )

    assert workflow["1"]["class_type"] == "UNETLoader"
    assert workflow["1"]["inputs"]["unet_name"] == ("flux-2-klein-base-4b.safetensors")
    assert workflow["2"]["class_type"] == "CLIPLoader"
    assert workflow["2"]["inputs"]["type"] == "flux2"
    assert workflow["3"]["class_type"] == "VAELoader"
    assert workflow["7"]["class_type"] == "CFGGuider"
    assert workflow["7"]["inputs"]["cfg"] == 5.0
    assert workflow["9"]["class_type"] == "Flux2Scheduler"
    assert workflow["9"]["inputs"]["steps"] == 20
    assert workflow["10"]["class_type"] == "EmptyFlux2LatentImage"
    assert workflow["11"]["class_type"] == "SamplerCustomAdvanced"
    assert workflow["13"]["class_type"] == "SaveImage"
    assert workflow["4"]["inputs"]["text"] == (
        "one child Alice reading beneath an oak tree"
    )


def test_flux2_klein_workflow_rejects_unsafe_dimensions():
    with pytest.raises(ValueError, match="flux2_invalid_width"):
        _build_flux2_klein_workflow(
            directed_prompt="story frame",
            quality_preset={"width": 833, "height": 1216},
            scene_seed=1,
            scene_id=1,
        )


def test_qwen_image_edit_2511_workflow_matches_native_comfyui_graph(monkeypatch):
    monkeypatch.delenv("COMFYUI_QWEN_EDIT_STEPS", raising=False)
    workflow = _build_qwen_image_edit_2511_workflow(
        edit_prompt="Replace only the cup with a small open sugar bowl and mouse.",
        input_image_name="rejected_scene.png",
        scene_seed=20260716,
        scene_id=2,
        negative_prompt="teacup, cup handle, giant mouse",
    )

    assert workflow["1"]["inputs"]["image"] == "rejected_scene.png"
    assert workflow["2"]["class_type"] == "FluxKontextImageScale"
    assert workflow["3"]["inputs"]["unet_name"] == (
        "qwen_image_edit_2511_fp8mixed.safetensors"
    )
    assert workflow["4"]["inputs"]["type"] == "qwen_image"
    assert workflow["6"]["class_type"] == "TextEncodeQwenImageEditPlus"
    assert workflow["6"]["inputs"]["image1"] == ["2", 0]
    assert "image2" not in workflow["6"]["inputs"]
    assert workflow["7"]["inputs"]["prompt"] == ""
    assert workflow["8"]["inputs"]["reference_latents_method"] == (
        "index_timestep_zero"
    )
    assert workflow["10"]["inputs"]["shift"] == 3.1
    assert workflow["12"]["inputs"]["steps"] == 40
    assert workflow["12"]["inputs"]["cfg"] == 3.0
    assert workflow["12"]["inputs"]["scheduler"] == "simple"
    assert workflow["14"]["class_type"] == "SaveImage"


def test_qwen_image_edit_can_use_approved_character_reference(monkeypatch):
    monkeypatch.setenv(
        "COMFYUI_QWEN_EDIT_DIFFUSION_MODEL",
        "qwen_image_edit_2511_fp8mixed.safetensors",
    )
    workflow = _build_qwen_image_edit_2511_workflow(
        edit_prompt="Use image 2 only for Alice identity and age.",
        input_image_name="rejected_scene.png",
        reference_image_name="approved_alice.png",
        scene_seed=7,
        scene_id=2,
        negative_prompt="adult Alice",
    )

    assert workflow["15"]["inputs"]["image"] == "approved_alice.png"
    assert workflow["16"]["class_type"] == "FluxKontextImageScale"
    assert workflow["6"]["inputs"]["image2"] == ["16", 0]
    assert workflow["7"]["inputs"]["image2"] == ["16", 0]


def test_qwen_image_edit_can_limit_changes_to_an_inpaint_mask(monkeypatch):
    monkeypatch.setenv("COMFYUI_QWEN_INPAINT_DENOISE", "1.0")
    workflow = _build_qwen_image_edit_2511_workflow(
        edit_prompt="Shrink only the sugar bowl and mouse.",
        input_image_name="approved_scene.png",
        reference_image_name="approved_alice.png",
        prop_reference_image_name="approved_props.png",
        inpaint_image_name="hero_objects_mask.png",
        scene_seed=8,
        scene_id=2,
        negative_prompt="serving bowl, oversized mouse",
    )

    assert workflow["17"]["inputs"]["image"] == "hero_objects_mask.png"
    assert workflow["18"]["class_type"] == "VAEEncode"
    assert workflow["19"]["class_type"] == "SetLatentNoiseMask"
    assert workflow["19"]["inputs"]["mask"] == ["17", 1]
    assert workflow["12"]["inputs"]["latent_image"] == ["19", 0]
    assert workflow["12"]["inputs"]["denoise"] == 1.0
    assert workflow["20"]["inputs"]["image"] == "approved_props.png"
    assert workflow["6"]["inputs"]["image3"] == ["21", 0]
    assert workflow["7"]["inputs"]["image3"] == ["21", 0]


def test_qwen_masked_prop_reference_uses_image2_without_character_reference():
    workflow = _build_qwen_image_edit_2511_workflow(
        edit_prompt="Replace only the masked prop using image 2 as geometry reference.",
        input_image_name="approved_scene.png",
        prop_reference_image_name="approved_props.png",
        inpaint_image_name="hero_objects_mask.png",
        scene_seed=9,
        scene_id=2,
        negative_prompt="this must not reach the native negative encoder",
    )

    assert workflow["6"]["inputs"]["image1"] == ["2", 0]
    assert workflow["6"]["inputs"]["image2"] == ["21", 0]
    assert "image3" not in workflow["6"]["inputs"]
    assert workflow["7"]["inputs"]["prompt"] == ""
    assert workflow["12"]["inputs"]["denoise"] == 1.0


def test_qwen_staged_inpaint_accepts_bounded_low_denoise():
    workflow = _build_qwen_image_edit_2511_workflow(
        edit_prompt="Harmonize the already staged approved prop.",
        input_image_name="staged_scene.png",
        prop_reference_image_name="approved_props.png",
        inpaint_image_name="hero_objects_mask.png",
        inpaint_denoise=0.35,
        negative_prompt="",
        scene_seed=10,
        scene_id=2,
    )

    assert workflow["12"]["inputs"]["denoise"] == 0.35


def test_runpod_submission_retries_once_while_capacity_propagates(monkeypatch):
    responses = [
        SimpleNamespace(status_code=409, text='{"error":"ENDPOINT_PAUSED"}'),
        SimpleNamespace(status_code=200, text='{"id":"job-1"}'),
    ]
    sleeps = []
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(langgraph_adapter.requests, "post", fake_post)
    monkeypatch.setattr(langgraph_adapter.time, "sleep", sleeps.append)
    monkeypatch.setenv("RUNPOD_ENDPOINT_PROPAGATION_RETRY_SECONDS", "2")

    response, attempts = _submit_runpod_job(
        run_url="https://api.runpod.ai/v2/test/run",
        request_payload={"input": {"workflow": {}}},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert len(calls) == 2
    assert sleeps == [2]
    assert attempts == [
        {"attempt": 1, "http_status": 409, "retry_after_seconds": 2},
        {"attempt": 2, "http_status": 200},
    ]


def test_runpod_cost_excludes_queue_time():
    monitor = {"estimated_cost_usd": None}

    _apply_runpod_execution_telemetry(
        monitor,
        {"status": "IN_QUEUE", "delayTime": 600_000},
        0.000386,
    )

    assert monitor["queue_seconds"] == 600.0
    assert monitor["execution_seconds"] == 0.0
    assert monitor["estimated_cost_usd"] == 0.0
    assert monitor["cost_estimate_status"] == "not_started"


def test_runpod_cost_uses_provider_execution_time():
    monitor = {"estimated_cost_usd": None}

    _apply_runpod_execution_telemetry(
        monitor,
        {
            "status": "COMPLETED",
            "delayTime": 120_000,
            "executionTime": 20_000,
        },
        0.000386,
    )

    assert monitor["queue_seconds"] == 120.0
    assert monitor["execution_seconds"] == 20.0
    assert monitor["estimated_cost_usd"] == 0.00772
    assert monitor["cost_estimate_status"] == "provider_execution_time_configured_rate"


def test_staged_report_distinguishes_capacity_timeout_from_semantic_failure():
    assert (
        staged_smoke._stage_report_status(
            False,
            {
                "status": "LOCAL_TIMEOUT",
                "last_remote_status": "IN_QUEUE",
                "exists": False,
                "technical_score": None,
            },
        )
        == "blocked_infrastructure_capacity"
    )
    assert (
        staged_smoke._stage_report_status(
            False,
            {
                "status": "COMPLETED",
                "last_remote_status": "COMPLETED",
                "exists": True,
                "technical_score": 100,
            },
        )
        == "blocked_semantic_gate"
    )


def test_deterministic_prop_stage_preserves_canvas_and_limits_edit(tmp_path):
    from PIL import Image, ImageDraw

    scene_path = tmp_path / "scene.png"
    prop_path = tmp_path / "prop.png"
    output_path = tmp_path / "staged.png"
    Image.new("RGB", (200, 300), "navy").save(scene_path)
    prop = Image.new("RGB", (200, 300), "beige")
    draw = ImageDraw.Draw(prop)
    draw.ellipse((45, 120, 115, 205), fill="white", outline="blue", width=5)
    prop.save(prop_path)

    placement = staged_smoke._stage_approved_prop_on_scene(
        scene_path=scene_path,
        prop_reference_path=prop_path,
        output_path=output_path,
    )

    with Image.open(output_path) as staged:
        assert staged.size == (200, 300)
        assert staged.getpixel((5, 5)) == (0, 0, 128)
        assert staged.getpixel((150, 225)) != (0, 0, 128)
        corner = staged.getpixel((127, 193))
        assert (
            sum(abs(value - expected) for value, expected in zip(corner, (0, 0, 128)))
            <= 50
        )
    assert placement["target_box"] == (126, 192, 174, 237)


def test_gpu_fallback_update_requires_stopped_endpoint(monkeypatch):
    monkeypatch.setattr(
        "scripts.runpod_endpoint_control.request_json",
        lambda *args, **kwargs: {"workersMin": 0, "workersMax": 1},
    )

    with pytest.raises(RuntimeError, match="Stop the endpoint"):
        update_stopped_endpoint_gpu_types(
            api_key="test",
            endpoint_id="endpoint",
            gpu_type_ids=["NVIDIA A100 80GB PCIe", "NVIDIA H100 80GB HBM3"],
        )


def test_runtime_image_update_requires_stopped_endpoint(monkeypatch):
    monkeypatch.setattr(
        "scripts.runpod_endpoint_control.request_json",
        lambda *args, **kwargs: {
            "templateId": "template",
            "workersMin": 0,
            "workersMax": 1,
        },
    )

    with pytest.raises(RuntimeError, match="Stop the endpoint"):
        update_endpoint_template_runtime(
            api_key="test",
            endpoint_id="endpoint",
            image_name="registry.example/worker:immutable",
            start_command="/start_ai_film.sh",
        )


def test_runtime_image_update_disables_flashboot(monkeypatch):
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if kwargs.get("method") == "PATCH":
            return {"id": "endpoint", "flashboot": False}
        if "/templates/" in url:
            return {"id": "template", "imageName": kwargs["payload"]["imageName"]}
        return {
            "templateId": "template",
            "workersMin": 0,
            "workersMax": 0,
        }

    monkeypatch.setattr(
        "scripts.runpod_endpoint_control.request_json",
        fake_request,
    )

    result = update_endpoint_template_runtime(
        api_key="test",
        endpoint_id="endpoint",
        image_name="registry.example/worker:immutable",
        start_command="/start_ai_film.sh",
    )

    assert result["template"]["imageName"] == "registry.example/worker:immutable"
    assert result["endpoint"]["flashboot"] is False
    assert calls[1][1]["method"] == "PATCH"
    assert calls[1][1]["payload"] == {"flashboot": False}
    assert "/templates/" in calls[2][0]


def test_gpu_fallback_update_rejects_low_memory_gpu():
    with pytest.raises(ValueError, match="at least 80 GB"):
        update_stopped_endpoint_gpu_types(
            api_key="test",
            endpoint_id="endpoint",
            gpu_type_ids=["NVIDIA L40S"],
        )


def test_semantic_qa_prefers_sdk_parsed_json():
    expected = {"semantic_score": 91, "accepted": True}

    assert _parse_semantic_qa_response(SimpleNamespace(parsed=expected)) == expected


def test_semantic_qa_falls_back_to_text_when_sdk_parsed_property_raises():
    class ResponseWithBrokenParsed:
        text = '{"semantic_score": 89, "accepted": true}'

        @property
        def parsed(self):
            raise ValueError("parsed response unavailable")

    parsed = _parse_semantic_qa_response(ResponseWithBrokenParsed())

    assert parsed == {"semantic_score": 89, "accepted": True}


def test_openai_semantic_qa_uses_structured_vision_payload(monkeypatch, tmp_path):
    captured = {}

    class FakeAPIError(RuntimeError):
        pass

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "semantic_score": 93,
                        "accepted": True,
                        "hero_object_legibility": True,
                        "hero_object_notes": "Visible at full-frame scale.",
                        "issues": [],
                        "critical_failures": [],
                        "retry_prompt": "",
                    }
                )
            )

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.responses = FakeResponses()

    fake_openai = SimpleNamespace(OpenAI=FakeOpenAI, APIError=FakeAPIError)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"not-a-real-png")

    result = _evaluate_semantic_qa_with_openai(
        image_path=image_path,
        prompt="Evaluate the scene.",
        model="gpt-5.4-mini",
        api_key="test-key",
    )

    content = captured["input"][0]["content"]
    assert result["semantic_score"] == 93
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["text"]["format"]["strict"] is True
    assert captured["store"] is False
    assert captured["max_output_tokens"] == 1200


def test_semantic_qa_uses_openai_when_gemini_fails(monkeypatch, tmp_path):
    def fail_gemini(**_kwargs):
        raise langgraph_adapter.SemanticQAProviderError("gemini:invalid_json")

    def pass_openai(**_kwargs):
        return {
            "semantic_score": 94,
            "accepted": True,
            "hero_object_legibility": True,
            "hero_object_notes": "Sugar bowl and mouse are clear.",
            "issues": [],
            "critical_failures": [],
            "retry_prompt": "",
        }

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("IMAGE_SEMANTIC_QA_PROVIDER", "gemini")
    monkeypatch.setenv("IMAGE_SEMANTIC_QA_FALLBACK_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_VISION_QA_MODEL", "gpt-5.4-mini")
    monkeypatch.setattr(
        langgraph_adapter, "_evaluate_semantic_qa_with_gemini", fail_gemini
    )
    monkeypatch.setattr(
        langgraph_adapter, "_evaluate_semantic_qa_with_openai", pass_openai
    )
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"not-a-real-png")

    result = _evaluate_image_semantics(
        str(image_path),
        {"description": "Alice reads beside a tree."},
        "Alice reads beside a tree.",
        DEFAULT_IMAGE_STYLE,
    )

    assert result["accepted"] is True
    assert result["semantic_score"] == 94
    assert result["provider"] == "openai"
    assert result["fallback_used"] is True
    assert result["provider_warnings"] == ["gemini:invalid_json"]


def test_semantic_qa_defaults_to_local_provider_and_models(monkeypatch):
    monkeypatch.delenv("IMAGE_SEMANTIC_QA_PROVIDER", raising=False)
    monkeypatch.setenv("LOCAL_VISION_QA_MODEL", "")
    monkeypatch.setenv("LOCAL_AGE_QA_MODEL", "")

    assert langgraph_adapter._semantic_qa_primary_provider() == "local"
    assert (
        langgraph_adapter._semantic_qa_model("local")
        == "HuggingFaceTB/SmolVLM-500M-Instruct"
    )


def test_semantic_qa_rejects_unknown_provider_to_local(monkeypatch):
    monkeypatch.setenv("IMAGE_SEMANTIC_QA_PROVIDER", "unknown-provider")

    assert langgraph_adapter._semantic_qa_primary_provider() == "local"


def test_local_visual_qa_requires_revision_for_custom_model(monkeypatch):
    from open3d_implementation.core import local_visual_qa

    monkeypatch.delenv("LOCAL_VISION_QA_REVISION", raising=False)

    with pytest.raises(
        local_visual_qa.LocalVisualQAError,
        match="LOCAL_VISION_QA_REVISION",
    ):
        local_visual_qa._model_revision(
            model_name="owner/custom-vision-model",
            env_name="LOCAL_VISION_QA_REVISION",
            default_model=local_visual_qa.DEFAULT_LOCAL_VISION_QA_MODEL,
            default_revision=local_visual_qa.DEFAULT_LOCAL_VISION_QA_REVISION,
        )


def test_semantic_qa_can_run_locally_without_external_provider(monkeypatch, tmp_path):
    def pass_local(**_kwargs):
        return {
            "semantic_score": 92,
            "accepted": True,
            "hero_object_legibility": True,
            "hero_object_notes": "The mouse and sugar bowl are clear.",
            "issues": [],
            "critical_failures": [],
            "retry_prompt": "",
        }

    def reject_external(**_kwargs):
        raise AssertionError("local QA must not call an external provider")

    monkeypatch.setenv("IMAGE_SEMANTIC_QA_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_VISION_QA_MODEL", "local-test-model")
    monkeypatch.setenv("IMAGE_SEMANTIC_QA_FALLBACK_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.delenv("IMAGE_SEMANTIC_QA_ALLOW_EXTERNAL_FALLBACK", raising=False)
    monkeypatch.setattr(
        langgraph_adapter, "_evaluate_semantic_qa_with_local_vlm", pass_local
    )
    monkeypatch.setattr(
        langgraph_adapter, "_evaluate_semantic_qa_with_openai", reject_external
    )
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"local-test-image")

    result = _evaluate_image_semantics(
        str(image_path),
        {"description": "Alice and Ludovico observe a mouse in a sugar bowl."},
        "Alice and Ludovico observe a mouse in a sugar bowl.",
        DEFAULT_IMAGE_STYLE,
    )

    assert result["accepted"] is True
    assert result["semantic_score"] == 92
    assert result["provider"] == "local"
    assert result["model"] == "local-test-model"
    assert "fallback_used" not in result


def test_local_semantic_qa_does_not_fallback_externally_by_default(
    monkeypatch, tmp_path
):
    def fail_local(**_kwargs):
        raise langgraph_adapter.SemanticQAProviderError("local_vlm:invalid_json")

    def reject_external(**_kwargs):
        raise AssertionError("external fallback requires explicit opt-in")

    monkeypatch.setenv("IMAGE_SEMANTIC_QA_PROVIDER", "local")
    monkeypatch.setenv("IMAGE_SEMANTIC_QA_FALLBACK_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.delenv("IMAGE_SEMANTIC_QA_ALLOW_EXTERNAL_FALLBACK", raising=False)
    monkeypatch.setattr(
        langgraph_adapter, "_evaluate_semantic_qa_with_local_vlm", fail_local
    )
    monkeypatch.setattr(
        langgraph_adapter, "_evaluate_semantic_qa_with_openai", reject_external
    )
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"local-test-image")

    result = _evaluate_image_semantics(
        str(image_path),
        {"description": "Alice reads beside a tree."},
        "Alice reads beside a tree.",
        DEFAULT_IMAGE_STYLE,
    )

    assert result["accepted"] is False
    assert result["provider"] == "local"
    assert result["issues"] == ["semantic_qa_failed"]
    assert result["provider_errors"] == ["local_vlm:invalid_json"]


def test_local_semantic_qa_scores_atomic_evidence(monkeypatch, tmp_path):
    from open3d_implementation.core import local_visual_qa

    def evaluate_checklist(**kwargs):
        answers = []
        for criterion in kwargs["criteria"]:
            answer = (
                "no"
                if "approximately 45 to 60 years old" in criterion.question
                else criterion.expected
            )
            answers.append(
                local_visual_qa.LocalVisualAnswer(
                    criterion=criterion,
                    answer=answer,
                    raw_response=f"{answer}.",
                )
            )
        return answers

    monkeypatch.setattr(
        local_visual_qa, "evaluate_local_visual_checklist", evaluate_checklist
    )
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"local-test-image")

    result = _evaluate_semantic_qa_with_local_vlm(
        image_path=image_path,
        scene={
            "description": "Alice and Ludovico observe a mouse.",
            "must_include": [
                "one ten-year-old child Alice",
                "one adult male professor around 50 years old",
                "one tiny white mouse in a sugar bowl",
            ],
            "must_not_include": ["visible text"],
        },
        style_key=DEFAULT_IMAGE_STYLE,
        model="local-test-model",
    )

    assert result["accepted"] is False
    assert result["semantic_score"] < 88
    assert result["critical_failures"] == ["wrong_ludovico_age"]
    assert result["hero_object_legibility"] is True
    assert result["evidence"][1]["answer"] == "no"
    assert result["evidence"][2]["question"].startswith("Is one tiny natural")


def test_local_semantic_qa_requires_specialized_age_evidence(monkeypatch, tmp_path):
    from open3d_implementation.core import local_visual_qa

    def evaluate_checklist(**kwargs):
        return [
            local_visual_qa.LocalVisualAnswer(
                criterion=criterion,
                answer=criterion.expected,
                raw_response=f"{criterion.expected}.",
            )
            for criterion in kwargs["criteria"]
        ]

    def evaluate_age(**kwargs):
        return local_visual_qa.LocalAgeEstimate(
            predicted_label="30-39",
            probabilities={"30-39": 0.72, "40-49": 0.18, "50-59": 0.04},
            crop_box=kwargs["crop_box"],
            model_name=kwargs["model_name"],
        )

    monkeypatch.setattr(
        local_visual_qa, "evaluate_local_visual_checklist", evaluate_checklist
    )
    monkeypatch.setattr(
        local_visual_qa, "evaluate_local_age_classification", evaluate_age
    )
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"local-test-image")

    result = _evaluate_semantic_qa_with_local_vlm(
        image_path=image_path,
        scene={
            "must_include": ["one adult male professor around 50 years old"],
            "local_age_checks": [
                {
                    "code": "wrong_ludovico_age",
                    "crop_box": [0.51, 0.03, 0.92, 0.39],
                    "accepted_labels": ["40-49", "50-59"],
                    "min_probability": 0.35,
                }
            ],
        },
        style_key=DEFAULT_IMAGE_STYLE,
        model="local-test-model",
    )

    assert result["accepted"] is False
    assert result["critical_failures"] == ["wrong_ludovico_age"]
    assert result["issues"] == ["wrong_ludovico_age_age_classifier"]
    assert result["evidence"][-1]["provider"] == "local_age_classifier"
    assert result["evidence"][-1]["accepted_probability"] == 0.22


def test_missing_custom_node_is_not_retried():
    assert (
        _non_retryable_comfyui_job_error(
            {"error": "Node 'IPAdapterUnifiedLoader' not found: missing_node_type"}
        )
        is True
    )


def test_flux2_controlled_retry_can_route_to_qwen_semantic_edit():
    source = inspect.getsource(langgraph_adapter._run_comfyui_image_attempt)

    assert 'semantic_repair_backend == "qwen_image_edit_2511"' in source
    assert "_build_qwen_image_edit_2511_workflow" in source
    assert '"comfyui_qwen_image_edit_2511"' in source
    assert 'os.getenv("COMFYUI_QWEN_EDIT_ENDPOINT_ID"' in source


def test_flux2_prompt_is_compact_and_preserves_tabletop_scale():
    scene = {
        "scene_id": 2,
        "description": (
            "Alice and Ludovico watch a small white mouse emerge from an open "
            "porcelain sugar bowl on a Victorian tea table."
        ),
        "must_include": [
            "one 10-year-old Alice",
            "one adult male professor Ludovico",
            "one open sugar bowl and its single lid",
            "one small natural white mouse",
        ],
        "must_not_include": ["adult Alice", "extra people", "oversized sugar bowl"],
    }

    prompt = _build_flux2_image_prompt(
        scene,
        "comic_storybook",
        {"protagonist_identity": "Alice is one 10-year-old Victorian child."},
    )

    assert len(prompt) <= 3600
    assert "believable tabletop scale" in prompt
    assert "adult-looking child" in prompt
    assert "enlarge the object" not in prompt
    assert "teaspoon" in prompt
    assert "thumbnail" not in prompt
    assert "dominate the central lower third" not in prompt


def test_response_text_falls_back_to_candidate_parts_when_property_raises():
    class Part:
        text = '{"accepted": false}'

    class Content:
        parts = [Part()]

    class Candidate:
        content = Content()

    class Response:
        candidates = [Candidate()]

        @property
        def text(self):
            raise ValueError("response has no direct text part")

    assert _extract_response_text(Response()) == '{"accepted": false}'


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


def test_reference_crop_removes_empty_canvas_before_ipadapter(tmp_path):
    from PIL import Image, ImageDraw

    source_path = tmp_path / "prop.png"
    source = Image.new("RGB", (100, 200), "white")
    draw = ImageDraw.Draw(source)
    draw.rectangle((20, 70, 80, 150), fill="red")
    source.save(source_path)

    encoded = _encode_comfyui_reference_image(
        str(source_path),
        image_name="prop.png",
        target_size=(64, 64),
        crop_box=(0.20, 0.35, 0.81, 0.76),
    )
    image_bytes = base64.b64decode(encoded["image"].split(",", 1)[1])

    with Image.open(BytesIO(image_bytes)) as cropped:
        assert cropped.size == (64, 64)
        assert cropped.convert("RGB").getpixel((32, 32)) == (255, 0, 0)


def test_masked_inpaint_accepts_bounded_denoise_override():
    workflow = _build_comfyui_workflow(
        directed_prompt="Add only a tiny white mouse inside the existing bowl",
        checkpoint_name="ai-film-semantic-juggernaut-xl.safetensors",
        quality_preset=_resolve_quality_preset("high"),
        scene_seed=125,
        scene_id=2,
        inpaint_image_name="precise_mask.png",
        inpaint_denoise=0.68,
    )

    assert workflow["3"]["inputs"]["denoise"] == 0.68


def test_ipadapter_prop_reference_uses_precise_composition_conditioning():
    workflow = _build_comfyui_workflow(
        directed_prompt="Insert one compact sugar bowl and tiny mouse",
        checkpoint_name="ai-film-semantic-juggernaut-xl.safetensors",
        quality_preset=_resolve_quality_preset("high"),
        scene_seed=124,
        scene_id=2,
        reference_image_name="approved_prop_reference.png",
        ipadapter_enabled=True,
        ipadapter_weight=0.90,
        ipadapter_weight_type="linear",
    )

    assert workflow["20"]["inputs"]["image"] == "approved_prop_reference.png"
    assert workflow["22"]["inputs"]["weight"] == 0.90
    assert workflow["22"]["inputs"]["weight_type"] == "linear"


def test_masked_repair_routes_ipadapter_to_prop_instead_of_character():
    prop_route = _resolve_ipadapter_reference(
        controlled_workflow=True,
        control_strategy="masked_inpaint",
        reference_image_path="approved_alice.png",
        prop_reference_image_path="approved_prop.png",
    )
    character_route = _resolve_ipadapter_reference(
        controlled_workflow=True,
        control_strategy="controlled_inpaint",
        reference_image_path="approved_alice.png",
        prop_reference_image_path="approved_prop.png",
    )

    assert prop_route == (
        "approved_prop.png",
        "hero_prop",
        "linear",
        0.90,
    )
    assert character_route == ("approved_alice.png", "character", "linear", None)


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
    assert workflow["20"]["inputs"]["image"] == (
        controlnet_smoke.IPADAPTER_REFERENCE_IMAGE_NAME
    )
    assert workflow["21"]["class_type"] == "IPAdapterUnifiedLoader"
    assert workflow["22"]["class_type"] == "IPAdapterAdvanced"
    assert workflow["3"]["inputs"]["model"] == ["22", 0]
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


def test_smoke_poller_recovers_from_transient_network_error(monkeypatch):
    class CompletedResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "COMPLETED", "output": {"images": []}}

    responses = iter(
        [
            controlnet_smoke.requests.exceptions.ReadTimeout("temporary"),
            CompletedResponse(),
        ]
    )

    def fake_get(*_args, **_kwargs):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setenv("COMFYUI_CONTROLNET_SMOKE_MAX_WAIT_SECONDS", "9")
    monkeypatch.setattr(controlnet_smoke.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(controlnet_smoke.requests, "get", fake_get)

    payload = controlnet_smoke._poll_job("endpoint", "api-key", "job")

    assert payload["status"] == "COMPLETED"


def test_ipadapter_sequence_smoke_uses_approved_anchor():
    anchor_workflow = ipadapter_smoke._build_anchor_workflow()
    sequence_workflow = ipadapter_smoke._build_sequence_workflow()

    assert "20" not in anchor_workflow
    assert "21" not in anchor_workflow
    assert "22" not in anchor_workflow
    assert sequence_workflow["20"]["inputs"]["image"] == (
        ipadapter_smoke.REFERENCE_IMAGE_NAME
    )
    assert sequence_workflow["21"]["class_type"] == "IPAdapterUnifiedLoader"
    assert sequence_workflow["22"]["inputs"]["weight"] == 0.55
    assert sequence_workflow["3"]["inputs"]["model"] == ["22", 0]


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

    assert image.getpixel((160, 200))[3] == 255
    assert image.getpixel((120, 380))[3] == 0


def test_scene_can_override_inpaint_mask_with_validated_normalized_box(tmp_path):
    from PIL import Image

    source = tmp_path / "approved.png"
    Image.new("RGB", (200, 300), "#d6c7a8").save(source)
    scene = {
        "description": "Um ratinho branco surge do acucareiro aberto.",
        "inpaint_focus_boxes": [[0.57, 0.68, 0.94, 0.92]],
    }

    assert _hero_object_focus_boxes(scene) == [(0.57, 0.68, 0.94, 0.92)]
    encoded = langgraph_adapter._encode_comfyui_inpaint_image(
        str(source),
        image_name="precise-mask.png",
        width=200,
        height=300,
        scene=scene,
    )
    image_bytes = base64.b64decode(encoded["image"].split(",", 1)[1])
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")

    assert image.getpixel((20, 100))[3] == 255
    assert image.getpixel((150, 240))[3] == 0


@pytest.mark.parametrize(
    "boxes",
    [
        [],
        [[0.8, 0.2, 0.4, 0.9]],
        [[-0.1, 0.2, 0.4, 0.9]],
        [[0.1, 0.2, 1.1, 0.9]],
        [[True, 0.2, 0.4, 0.9]],
        [[0.1, 0.2, 0.4]],
    ],
)
def test_scene_rejects_unsafe_inpaint_focus_boxes(boxes):
    with pytest.raises(ValueError):
        _hero_object_focus_boxes({"inpaint_focus_boxes": boxes})


def test_worker_custom_node_gate_requires_both_ipadapter_nodes():
    valid_module = ModuleType("valid_ipadapter")
    valid_module.NODE_CLASS_MAPPINGS = {
        "IPAdapterUnifiedLoader": object,
        "IPAdapterAdvanced": object,
    }
    validate_ipadapter_nodes(valid_module)

    incomplete_module = ModuleType("incomplete_ipadapter")
    incomplete_module.NODE_CLASS_MAPPINGS = {"IPAdapterUnifiedLoader": object}
    with pytest.raises(RuntimeError, match="IPAdapterAdvanced"):
        validate_ipadapter_nodes(incomplete_module)


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
    assert 800 < bright_pixels < 1500


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


def test_initial_attempt_preserves_controlled_retry_contract(tmp_path):
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"image")
    summary = {
        "scenes": [{"scene_id": 2}],
        "scenes_count": 1,
        "scene_images": [
            {
                "scene_id": 2,
                "image_path": str(image_path),
                "generation_method": "comfyui",
            }
        ],
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 2,
                    "quality_score": 100,
                    "technical_accepted": True,
                    "semantic_score": 42,
                    "semantic_accepted": False,
                    "control_workflow_required": True,
                    "recommended_generation_strategy": "masked_inpaint",
                    "operator_next_action": "Repair only the hero object.",
                    "issues": ["control_workflow_required"],
                }
            ]
        },
    }

    curated = ui_server._apply_curation_summary(summary, tmp_path)
    metric = curated["quality_metrics"]["images"][0]

    assert metric["control_workflow_required"] is True
    assert metric["recommended_generation_strategy"] == "masked_inpaint"
    assert metric["operator_next_action"] == "Repair only the hero object."


def test_failed_youtube_upload_is_retryable_after_final_gate(tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"final-video")
    summary = {
        "video_path": str(video_path),
        "video_exists": True,
        "publication": {"status": "failed", "error": "temporary provider error"},
        "curation": {"final_review": {"status": "final_approved"}},
    }

    production = ui_server._apply_production_status(summary, tmp_path, [])

    assert production["status"] == "ready_to_publish"
    assert production["publication_retry_available"] is True


def test_cost_quota_blocks_publish_when_run_cost_exceeds_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_FILM_COST_LIMIT_USD", "0.50")
    video = tmp_path / "output" / "final_video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video-v1")
    image = tmp_path / "scene.png"
    image.write_bytes(b"image-v1")
    summary = {
        "video_path": str(video),
        "video_exists": True,
        "scene_images": [{"scene_id": 1, "image_path": "scene.png"}],
        "scene_videos": [{"scene_id": 1, "video_path": "scene.mp4"}],
        "audio_files": [{"scene_id": 1, "audio_path": "scene.mp3"}],
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 1,
                    "semantic_accepted": True,
                    "technical_accepted": True,
                    "quality_score": 95,
                }
            ],
            "voices": [{"scene_id": 1, "premium_audio": True, "text_characters": 200}],
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
    image = tmp_path / "scene.png"
    image.write_bytes(b"image-v1")
    summary = {
        "video_path": str(video),
        "video_exists": True,
        "scene_images": [{"scene_id": 1, "image_path": "scene.png"}],
        "scene_videos": [{"scene_id": 1, "video_path": "scene.mp4"}],
        "audio_files": [{"scene_id": 1, "audio_path": "scene.mp3"}],
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 1,
                    "semantic_accepted": True,
                    "technical_accepted": True,
                    "quality_score": 95,
                }
            ]
        },
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


def test_missing_semantic_scene_blocks_final_approval_and_publication(tmp_path):
    video = tmp_path / "output" / "final_video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video-v1")
    for scene_id in (1, 3):
        (tmp_path / f"scene-{scene_id}.png").write_bytes(b"image")
    summary = {
        "status": "completed",
        "scenes_count": 3,
        "scenes": [{"scene_id": 1}, {"scene_id": 2}, {"scene_id": 3}],
        "scene_images": [
            {"scene_id": 1, "image_path": "scene-1.png"},
            {"scene_id": 3, "image_path": "scene-3.png"},
        ],
        "video_path": str(video),
        "video_exists": True,
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 1,
                    "semantic_accepted": True,
                    "technical_accepted": True,
                },
                {
                    "scene_id": 2,
                    "semantic_accepted": False,
                    "technical_accepted": True,
                    "issues": ["semantic_gate_blocked"],
                },
                {
                    "scene_id": 3,
                    "semantic_accepted": True,
                    "technical_accepted": True,
                },
            ]
        },
        "curation": {
            "scenes": {
                "1": {"status": "approved", "attempts": []},
                "3": {"status": "approved", "attempts": []},
            },
            "final_review": {"status": "final_approved", "video_viewed": True},
        },
    }

    result = ui_server._apply_curation_summary(summary, tmp_path)

    assert result["curation"]["total_scenes"] == 3
    assert result["curation"]["quality_gate_status"] == "blocked"
    assert result["curation"]["status"] == "quality_review_blocked"
    assert result["curation"]["final_review"]["status"] == "quality_review_blocked"
    assert result["production_status"]["status"] == "blocked"
    assert result["curation"]["can_publish"] is False
