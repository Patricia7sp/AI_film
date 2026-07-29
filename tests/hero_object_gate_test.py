import base64
import hashlib
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
from open3d_implementation.core import runpod_cost_guard  # noqa: E402
from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    CAST_BIBLE_SCHEMA_VERSION,
    CAST_REFERENCE_POSE_VIEWS,
    CAST_REFERENCE_VIEWS,
    DEFAULT_IMAGE_STYLE,
    _apply_cast_reference_identity_gate,
    _apply_runpod_execution_telemetry,
    _audio_quality_gate,
    _begin_cast_reference_revision,
    _block_cast_reference_views_for_pose_circuit,
    _build_cast_bible,
    _build_character_reference_scene,
    _build_comfyui_workflow,
    _build_flux2_image_prompt,
    _build_flux2_klein_workflow,
    _build_image_prompt,
    _build_qwen_image_edit_2511_workflow,
    _build_qwen_semantic_edit_prompt,
    _build_scene_contract,
    _build_visual_bible,
    _cast_reference_attempt_path,
    _cast_reference_attempt_reusable,
    _cast_reference_derived_concurrency,
    _cast_reference_job_retryable,
    _cast_reference_max_attempts,
    _cast_reference_pose_failure_limit,
    _cast_reference_quality_preset,
    _cast_reference_qwen_denoise,
    _cast_reference_waiting_stage,
    _character_reference_accepted,
    _combine_image_quality,
    _comfyui_control_image_mode,
    _comfyui_controlnet_model,
    _comfyui_model_family,
    _comfyui_refiner_enabled,
    _create_cast_reference_pose_guide,
    _detect_profile_eye_count,
    _elevenlabs_voice_id_for_scene,
    _encode_comfyui_control_image,
    _encode_comfyui_reference_image,
    _evaluate_image_semantics,
    _evaluate_semantic_qa_with_local_vlm,
    _evaluate_semantic_qa_with_openai,
    _extract_response_text,
    _flux2_lora_gate,
    _flux2_scene_lora_stack,
    _hero_object_focus_boxes,
    _hero_object_requirements,
    _identity_retry_reference_path,
    _image_generation_max_attempts,
    _image_generation_provider,
    _local_required_visual_code,
    _local_required_visual_question,
    _merge_canonical_scenes,
    _non_retryable_comfyui_job_error,
    _parse_semantic_qa_response,
    _premium_audio_direction,
    _premium_audio_narration,
    _probe_image_quality,
    _qwen_semantic_retry_enabled,
    _refresh_cast_bible_status,
    _required_production_cast,
    _required_scene_cast,
    _resolve_comfyui_checkpoint,
    _resolve_ipadapter_reference,
    _resolve_quality_preset,
    _runpod_poll_timeout_reason,
    _scene_cast_characters,
    _scene_cast_identity_text,
    _scene_cast_reference_versions,
    _scene_lora_trigger_tokens,
    _scene_negative_prompt,
    _scene_response_json_schema,
    _select_comfyui_retry_route,
    _semantic_retry_instruction,
    _set_cast_reference_human_approval,
    _submit_runpod_job,
    _update_cast_reference,
    _validate_structured_scenes,
    _validated_lora_name,
)
from open3d_implementation.core.local_visual_qa import (  # noqa: E402
    _identity_composition_threshold,
    _identity_similarity_threshold,
)
from open3d_implementation.orchestration import llm_config  # noqa: E402
from runpod_worker.validate_custom_nodes import (  # noqa: E402
    validate_ipadapter_nodes,
)
from scripts import smoke_comfyui_controlnet_retry as controlnet_smoke  # noqa: E402
from scripts import smoke_comfyui_ipadapter_sequence as ipadapter_smoke  # noqa: E402
from scripts import smoke_comfyui_staged_repair as staged_smoke  # noqa: E402
from scripts.create_cast_reference_resume_manifest import (  # noqa: E402
    create_manifest as create_cast_reference_resume_manifest,
)
from scripts.export_cast_bible_lora_manifest import (  # noqa: E402
    export_training_packs,
)
from scripts.runpod_endpoint_control import (  # noqa: E402
    redact_sensitive_values,
    save_endpoint,
    update_endpoint_template_runtime,
    update_stopped_endpoint_gpu_types,
)


@pytest.fixture(autouse=True)
def _disable_runpod_hard_cost_guard(monkeypatch):
    monkeypatch.setenv("AI_FILM_RUNPOD_HARD_COST_GUARD_ENABLED", "false")
    runpod_cost_guard.reset_runpod_cost_reservations_for_tests()
    yield
    runpod_cost_guard.reset_runpod_cost_reservations_for_tests()


def _names(scene):
    return [item["name"] for item in _hero_object_requirements(scene)]


@pytest.mark.parametrize(
    ("view_id", "expected_code", "question_fragment"),
    [
        ("three_quarter", "cast_three_quarter_pose_missing", "three-quarter view"),
        ("profile", "cast_profile_pose_missing", "strict left-facing side profile"),
        ("full_body", "cast_full_body_pose_missing", "head to both shoes"),
    ],
)
def test_cast_reference_pose_checks_are_short_and_specific(
    view_id,
    expected_code,
    question_fragment,
):
    scene = _build_character_reference_scene(
        _build_visual_bible("Alice", "comic_storybook"),
        "alice",
        view_id,
    )
    requirement = scene["must_include"][0]

    assert (
        langgraph_adapter._local_required_visual_code(requirement, 1) == expected_code
    )
    question = langgraph_adapter._local_required_visual_question(requirement)
    assert question_fragment in question
    assert len(question) < 220


@pytest.mark.parametrize(
    ("requirement", "expected_code", "question_fragment"),
    [
        (
            "chestnut-brown shoulder-length hair",
            "cast_identity_hair_mismatch",
            "rather than short",
        ),
        (
            "modest ivory-white long-sleeved Victorian day dress",
            "cast_identity_wardrobe_mismatch",
            "exact wardrobe",
        ),
        (
            "natural preteen proportions",
            "cast_identity_proportions_mismatch",
            "body-age contract",
        ),
    ],
)
def test_cast_reference_identity_checks_are_atomic(
    requirement,
    expected_code,
    question_fragment,
):
    assert (
        langgraph_adapter._local_required_visual_code(requirement, 1) == expected_code
    )
    assert question_fragment in langgraph_adapter._local_required_visual_question(
        requirement
    )


def test_profile_second_eye_is_an_atomic_critical_exclusion():
    exclusion = "two eyes or two eyebrows visible in a profile reference"

    assert (
        langgraph_adapter._local_forbidden_visual_code(exclusion, 1)
        == "cast_profile_second_eye_visible"
    )
    question = langgraph_adapter._local_forbidden_visual_question(exclusion)
    assert "any part of a second eye" in question
    assert "three-quarter views" in question


def test_profile_eye_detector_rejects_the_known_three_quarter_regression():
    regression_image = (
        ROOT
        / "data"
        / "runs"
        / "20260726_065731_40e48421"
        / "output"
        / "alice_character_reference_profile_attempt_5.png"
    )
    if not regression_image.exists():
        pytest.skip("local generated regression artifact is unavailable")

    assert _detect_profile_eye_count(regression_image) >= 2


def test_gemini_text_client_has_bounded_timeout_and_retries(monkeypatch):
    from google import genai

    captured = {}
    fake_client = object()

    def build_fake_client(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    monkeypatch.setenv("GEMINI_TEXT_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("GEMINI_TEXT_RETRY_ATTEMPTS", "99")
    monkeypatch.setattr(genai, "Client", build_fake_client)

    client = llm_config._GeminiChat("test-model")._get_client()
    http_options = captured["http_options"]

    assert client is fake_client
    assert http_options.timeout == 15_000
    assert http_options.retry_options.attempts == 3
    assert http_options.retry_options.max_delay == 5.0


def test_gemini_media_client_has_bounded_timeout_and_retries(monkeypatch):
    from google import genai

    captured = {}
    fake_client = object()

    def build_fake_client(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setenv("GEMINI_VISION_QA_TIMEOUT_SECONDS", "999")
    monkeypatch.setenv("GEMINI_REQUEST_RETRY_ATTEMPTS", "0")
    monkeypatch.setattr(genai, "Client", build_fake_client)

    client = langgraph_adapter._build_google_genai_client(
        "test-only-key",
        timeout_env="GEMINI_VISION_QA_TIMEOUT_SECONDS",
        default_timeout_seconds=90,
    )
    http_options = captured["http_options"]

    assert client is fake_client
    assert http_options.timeout == 300_000
    assert http_options.retry_options.attempts == 1


def test_scene_structured_output_schema_requires_exact_count():
    schema = _scene_response_json_schema(8)

    assert schema["type"] == "array"
    assert schema["minItems"] == 8
    assert schema["maxItems"] == 8
    assert schema["items"]["additionalProperties"] is False


def test_structured_scene_validation_and_canonical_merge_preserve_scene_count():
    payload = [
        {
            "scene_id": index,
            "description": f"Alice performs a distinct narrative action number {index}.",
            "prompt": f"A complete comic storybook frame for narrative action {index}.",
            "duration": 6,
            "must_include": [f"narrative action {index}"],
            "must_not_include": ["duplicate Alice"],
            "source_excerpt": f"Original passage number {index}.",
            "camera_motion": "slow controlled cinematic push-in",
        }
        for index in range(1, 9)
    ]
    scenes = _validate_structured_scenes(payload, 8)
    story = "Alice viu um formigueiro, um açucareiro com ratinho e uma toca de coelho."

    merged = _merge_canonical_scenes(scenes, story, "comic_storybook", 8)

    assert len(merged) == 8
    assert [scene["scene_id"] for scene in merged] == list(range(1, 9))
    assert any("narrative action" in scene["description"] for scene in merged[3:])


def _mock_valid_video_probe(monkeypatch):
    def probe(video_path):
        stat = video_path.stat()
        return {
            "exists": True,
            "valid": True,
            "path": str(video_path),
            "size_bytes": stat.st_size,
            "mtime": stat.st_mtime,
            "duration_seconds": 2.0,
            "frame_count": 60,
            "codec": "h264",
            "width": 1080,
            "height": 1920,
            "first_frame_decoded": True,
            "issues": [],
        }

    monkeypatch.setattr(ui_server, "_probe_video_artifact", probe)


def _approve_cast_reference_pack(character, tmp_path, payload_byte=b"r"):
    metric = {
        "quality_score": 96,
        "technical_score": 100,
        "technical_accepted": True,
        "semantic_score": 96,
        "semantic_accepted": True,
        "semantic_critical_failures": [],
        "issues": [],
    }
    _begin_cast_reference_revision(character)
    for index, view_id in enumerate(CAST_REFERENCE_VIEWS, start=1):
        reference_path = tmp_path / f"{character['id']}-{view_id}.png"
        reference_path.write_bytes(payload_byte * (1200 + index))
        _update_cast_reference(
            character,
            str(reference_path),
            metric,
            view_id,
            human_approved=True,
        )
    assert character["reference"]["approved"] is True
    return str(character["reference"]["path"])


def _auto_approve_cast_reference_pack(character, tmp_path, payload_byte=b"a"):
    metric = {
        "quality_score": 96,
        "technical_score": 100,
        "technical_accepted": True,
        "semantic_score": 96,
        "semantic_accepted": True,
        "semantic_critical_failures": [],
        "issues": [],
    }
    _begin_cast_reference_revision(character)
    for index, view_id in enumerate(CAST_REFERENCE_VIEWS, start=1):
        reference_path = tmp_path / f"{character['id']}-{view_id}.png"
        reference_path.write_bytes(payload_byte * (1200 + index))
        _update_cast_reference(
            character,
            str(reference_path),
            metric,
            view_id,
            human_approved=False,
        )
    assert character["reference"]["automatic_approved"] is True
    assert character["reference"]["human_approved"] is False
    return str(character["reference"]["path"])


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


def test_save_endpoint_preserves_explicit_idle_timeout(monkeypatch):
    from scripts import runpod_endpoint_control

    captured = {}

    def request_json(url, *, api_key, payload=None, method=None, timeout=30):
        captured["payload"] = payload
        return {
            "data": {
                "saveEndpoint": {
                    "id": "endpoint",
                    "idleTimeout": payload["variables"]["input"]["idleTimeout"],
                }
            }
        }

    monkeypatch.setattr(runpod_endpoint_control, "request_json", request_json)

    result = save_endpoint(
        api_key="secret",
        endpoint_id="endpoint",
        endpoint_name="ai-film",
        workers_min=0,
        workers_max=1,
        idle_timeout=900,
        locations="EUR-IS-1",
    )

    assert captured["payload"]["variables"]["input"]["idleTimeout"] == 900
    assert result["idleTimeout"] == 900


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
    assert "_update_cast_reference" in source
    assert 'visual_bible["character_reference_image_path"]' in source
    assert "_required_production_cast" in source
    assert "_cast_reference_waiting_stage" in source
    assert '"pending_human_review"' in source
    assert '"current_step": stage' in source
    assert '"status": stage' in source
    assert "cast_reference_gate_blocked" not in source
    assert "_scene_reference_image_path" in source


def test_cast_bible_is_versioned_and_contains_recurring_characters():
    story = (
        "Alice asks Professor Ludovico for help. Ludovico smiles at Alice. "
        "Edith and Lóri watch while Mia rests nearby."
    )

    cast = _build_cast_bible(story, "comic_storybook")
    repeated = _build_cast_bible(story, "comic_storybook")
    character_ids = [character["id"] for character in cast["characters"]]

    assert cast["schema_version"] == CAST_BIBLE_SCHEMA_VERSION
    assert cast["revision"] == repeated["revision"]
    assert character_ids == ["alice", "ludovico", "lori", "edith", "mia"]
    assert all(
        character["reference"]["status"] == "pending"
        for character in cast["characters"]
    )
    assert cast["status"] == "references_pending"


def test_ludovico_reference_scene_uses_his_identity_not_alice():
    visual_bible = _build_visual_bible(
        "Alice conversa com o professor Ludovico. Ludovico sorri.",
        "comic_storybook",
    )

    reference_scene = _build_character_reference_scene(visual_bible, "ludovico")

    assert reference_scene["scene_id"] == "ludovico_reference"
    assert reference_scene["character_id"] == "ludovico"
    assert "Professor Ludovico" in reference_scene["prompt"]
    assert "45 to 55" in reference_scene["prompt"]
    assert all("Alice" not in item for item in reference_scene["must_include"])


def test_character_reference_profile_is_an_explicit_semantic_requirement():
    visual_bible = _build_visual_bible(
        "Alice asks Professor Ludovico a question.",
        "comic_storybook",
    )

    reference_scene = _build_character_reference_scene(
        visual_bible,
        "alice",
        "profile",
    )
    prompt = _build_qwen_semantic_edit_prompt(
        reference_scene,
        "Preserve the canonical identity.",
    )

    assert CAST_REFERENCE_VIEWS["profile"] in reference_scene["must_include"]
    assert reference_scene["must_include"] == [
        CAST_REFERENCE_VIEWS["profile"],
        "exactly one Alice approximately 10 years old",
        "chestnut-brown shoulder-length hair",
        "modest ivory-white long-sleeved Victorian day dress",
        "natural preteen proportions",
        "plain warm gray studio backdrop",
    ]
    assert reference_scene["must_not_include"] == [
        "second subject",
        "props or story action",
        "text, logo or watermark",
        "two eyes or two eyebrows visible in a profile reference",
        "new isolated mole, beauty mark or dark facial spot",
    ]
    assert "canonical identity anchor" in prompt
    assert "strict left-side profile" in prompt
    assert "not a redesign" in prompt
    reference_scene["qwen_source_role"] = "pose_guide"
    pose_guide_prompt = _build_qwen_semantic_edit_prompt(
        reference_scene,
        "Preserve the canonical identity.",
    )
    assert "Image 1 is a neutral geometric pose and framing guide" in pose_guide_prompt
    assert "Image 2 is the sole canonical identity anchor" in pose_guide_prompt
    assert "Rotate the head exactly 90 degrees" in pose_guide_prompt
    assert "canonical preteen cheek, jaw and forehead proportions" in pose_guide_prompt
    assert "Do not invent a mole" in pose_guide_prompt
    reference_scene["qwen_source_role"] = "identity_latent_pose_reference"
    identity_latent_prompt = _build_qwen_semantic_edit_prompt(
        reference_scene,
        "Preserve the canonical identity.",
    )
    assert "Image 1 is the sole canonical identity anchor" in identity_latent_prompt
    assert "Image 2 is only a neutral geometric pose guide" in identity_latent_prompt
    assert "never copy its lines, polygons" in identity_latent_prompt
    reference_scene["qwen_source_role"] = "identity_anchor_only"
    identity_only_prompt = _build_qwen_semantic_edit_prompt(
        reference_scene,
        "Preserve the canonical identity.",
    )
    assert (
        "Image 1 is the sole canonical identity anchor and the only source image"
        in (identity_only_prompt)
    )
    assert "without adding a second face" in identity_only_prompt
    assert "Image 2" not in identity_only_prompt

    three_quarter_scene = _build_character_reference_scene(
        visual_bible,
        "alice",
        "three_quarter",
    )
    three_quarter_prompt = _build_qwen_semantic_edit_prompt(
        three_quarter_scene,
        "Preserve the canonical identity.",
    )
    assert "turned only 20 to 30 degrees" in three_quarter_prompt
    assert "both eyes fully visible" in three_quarter_prompt
    assert "nose contained inside the far-cheek silhouette" in three_quarter_prompt
    assert (
        "Generation direction: Preserve the canonical identity." in three_quarter_prompt
    )
    assert "Show an exact left-side profile" not in three_quarter_prompt
    assert "This target is not a profile" not in prompt

    front_scene = _build_character_reference_scene(visual_bible, "alice", "front")
    assert len(front_scene["must_include"]) >= len(reference_scene["must_include"])
    assert "adult or teenage Alice" in front_scene["must_not_include"]

    full_body_scene = _build_character_reference_scene(
        visual_bible,
        "alice",
        "full_body",
    )
    full_body_prompt = _build_qwen_semantic_edit_prompt(
        full_body_scene,
        "Preserve the canonical identity.",
    )
    assert full_body_scene["character_kind"] == "human"
    assert "natural human hands and feet" in full_body_scene["must_include"][0]
    assert "animal paws, claws, talons or hooves" in full_body_scene["must_not_include"]
    assert "from head through both shoes" in full_body_prompt
    assert "Never generate paws, claws, talons, hooves" in full_body_prompt


def test_character_reference_image_prompt_excludes_narrative_environment():
    visual_bible = _build_visual_bible(
        "Alice asks Professor Ludovico a question.",
        "comic_storybook",
    )
    scene = _build_character_reference_scene(
        visual_bible,
        "alice",
        "three_quarter",
    )

    prompt = _build_image_prompt(
        scene,
        "comic_storybook",
        visual_bible,
        "remove the garden",
    )

    assert "Production character turnaround reference" in prompt
    assert "plain warm-gray studio backdrop" in prompt
    assert "no scenery" in prompt
    assert "never a film still or story frame" in prompt
    assert "continuous environment" not in prompt
    assert "rule of thirds" not in prompt


def test_cast_reference_reconciliation_overrides_deterministic_false_negatives(
    monkeypatch,
    tmp_path,
):
    from PIL import Image

    candidate = tmp_path / "alice_character_reference_three_quarter.png"
    Image.new("RGB", (896, 1152), color=(211, 198, 171)).save(candidate)
    monkeypatch.setattr(
        langgraph_adapter,
        "_detect_profile_eye_count",
        lambda _path: 2,
    )
    metric = {
        "technical_score": 100.0,
        "quality_score": 83.3,
        "semantic_score": 73.0,
        "semantic_accepted": False,
        "semantic_critical_failures": [
            "cast_three_quarter_pose_missing",
            "required_6",
        ],
        "issues": [
            "cast_three_quarter_pose_missing",
            "cast_three_quarter_pose_missing_no",
            "required_6",
            "required_6_no",
            "semantic_quality_below_threshold",
        ],
        "semantic_qa_evidence": [
            {
                "code": "cast_three_quarter_pose_missing",
                "question": "Is the character visibly turned to a three-quarter view?",
                "matched": False,
            },
            {
                "code": "required_6",
                "question": (
                    "Is this requirement clearly satisfied in the image: "
                    "plain warm gray studio backdrop?"
                ),
                "matched": False,
            },
        ],
    }

    langgraph_adapter._reconcile_cast_reference_semantic_false_negatives(
        image_metric=metric,
        candidate_path=str(candidate),
        view_id="three_quarter",
        identity_accepted=True,
        composition_similarity=0.92,
    )

    assert metric["semantic_critical_failures"] == []
    assert metric["issues"] == []
    assert metric["semantic_score"] == 100.0
    assert metric["semantic_accepted"] is True
    assert metric["quality_score"] == 100.0
    assert metric["semantic_qa_evidence"][-1]["overridden_codes"] == [
        "cast_three_quarter_pose_missing",
        "required_6",
    ]


def test_cast_reference_reconciliation_keeps_nonuniform_background_failure(
    monkeypatch,
    tmp_path,
):
    from PIL import Image

    candidate = tmp_path / "alice_character_reference_three_quarter.png"
    image = Image.new("RGB", (896, 1152), color=(210, 190, 160))
    for x in range(0, 322):
        for y in range(0, 138):
            image.putpixel((x, y), ((x * 7) % 255, (y * 11) % 255, 30))
    image.save(candidate)
    monkeypatch.setattr(
        langgraph_adapter,
        "_detect_profile_eye_count",
        lambda _path: 2,
    )
    metric = {
        "technical_score": 100.0,
        "semantic_critical_failures": ["required_6"],
        "issues": ["required_6", "required_6_no"],
        "semantic_qa_evidence": [
            {
                "code": "required_6",
                "question": (
                    "Is this requirement clearly satisfied in the image: "
                    "plain warm gray studio backdrop?"
                ),
                "matched": False,
            }
        ],
    }

    langgraph_adapter._reconcile_cast_reference_semantic_false_negatives(
        image_metric=metric,
        candidate_path=str(candidate),
        view_id="three_quarter",
        identity_accepted=True,
        composition_similarity=0.92,
    )

    assert metric["semantic_critical_failures"] == ["required_6"]
    assert metric["issues"] == ["required_6", "required_6_no"]


def test_cast_reference_canvas_border_is_removed_without_touching_plain_image(
    tmp_path,
):
    from PIL import Image, ImageDraw

    bordered = tmp_path / "bordered.png"
    bordered_image = Image.new("RGB", (512, 768), color=(210, 198, 175))
    ImageDraw.Draw(bordered_image).rectangle(
        (8, 8, 503, 759),
        outline=(0, 0, 0),
        width=4,
    )
    bordered_image.save(bordered)
    plain = tmp_path / "plain.png"
    Image.new("RGB", (512, 768), color=(210, 198, 175)).save(plain)
    plain_checksum = hashlib.sha256(plain.read_bytes()).hexdigest()

    assert langgraph_adapter._normalize_cast_reference_canvas_border(str(bordered))
    assert not langgraph_adapter._normalize_cast_reference_canvas_border(str(plain))
    assert hashlib.sha256(plain.read_bytes()).hexdigest() == plain_checksum
    with Image.open(bordered) as normalized:
        assert normalized.convert("RGB").getpixel((0, 0))[0] > 150


def test_cast_reference_runtime_limits_and_portrait_framing(monkeypatch):
    monkeypatch.setenv("CAST_REFERENCE_DERIVED_CONCURRENCY", "99")
    monkeypatch.setenv("CAST_REFERENCE_MAX_ATTEMPTS", "0")

    assert _cast_reference_derived_concurrency() == len(CAST_REFERENCE_VIEWS) - 1
    assert _cast_reference_max_attempts() == 1
    assert _cast_reference_attempt_path("alice", "profile", 0).endswith(
        "alice_character_reference_profile.png"
    )
    assert _cast_reference_attempt_path("alice", "profile", 1).endswith(
        "alice_character_reference_profile_attempt_2.png"
    )

    base_preset = {"width": 832, "height": 1216, "steps": 35}
    assert (
        _cast_reference_quality_preset(base_preset, "three_quarter")["height"] == 1024
    )
    assert _cast_reference_quality_preset(base_preset, "full_body")["height"] == 1216
    assert base_preset["height"] == 1216

    monkeypatch.delenv("CAST_REFERENCE_QWEN_DENOISE_PROFILE", raising=False)
    assert _cast_reference_qwen_denoise("profile") == 0.90
    monkeypatch.setenv("CAST_REFERENCE_QWEN_DENOISE_PROFILE", "0.01")
    assert _cast_reference_qwen_denoise("profile") == 0.2
    assert _cast_reference_qwen_denoise("three_quarter") == 0.95
    assert _cast_reference_qwen_denoise("full_body") == 1.0
    assert _cast_reference_qwen_denoise("expression_warm") == 0.35
    with pytest.raises(ValueError, match="unknown_cast_reference_view"):
        _cast_reference_qwen_denoise("invalid")


def test_cast_reference_pose_guide_and_failure_circuit(monkeypatch, tmp_path):
    from PIL import Image

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAST_REFERENCE_POSE_FAILURE_LIMIT", "99")
    assert _cast_reference_pose_failure_limit() == len(CAST_REFERENCE_POSE_VIEWS)

    guide_path = Path(
        _create_cast_reference_pose_guide(
            character_id="alice",
            view_id="profile",
            width=832,
            height=1024,
        )
    )
    assert guide_path.is_file()
    with Image.open(guide_path) as guide:
        assert guide.size == (832, 1024)
        assert guide.getbbox() == (0, 0, 832, 1024)

    visual_bible = _build_visual_bible(
        "Alice asks Professor Ludovico a question.",
        "comic_storybook",
    )
    alice = next(
        character
        for character in visual_bible["cast_bible"]["characters"]
        if character["id"] == "alice"
    )
    _begin_cast_reference_revision(alice)
    _block_cast_reference_views_for_pose_circuit(
        alice,
        ["full_body", "expression_neutral"],
    )
    for view_id in ("full_body", "expression_neutral"):
        view = alice["reference"]["views"][view_id]
        assert view["status"] == "blocked_by_pose_circuit"
        assert view["path"] == ""
        assert view["quality"]["issues"] == ["cast_reference_pose_circuit_open"]

    with pytest.raises(ValueError, match="pose_guide_not_supported"):
        _create_cast_reference_pose_guide(
            character_id="alice",
            view_id="expression_warm",
            width=832,
            height=1024,
        )


def test_cast_reference_does_not_retry_runpod_billing_failures():
    assert _cast_reference_job_retryable({"status": "PAYMENT_REQUIRED"}) is False
    assert _cast_reference_job_retryable({"status": "LOCAL_ASSET_MISSING"}) is False
    assert (
        _cast_reference_job_retryable({"error": "HTTP 402: billing blocked"}) is False
    )
    assert _cast_reference_job_retryable({"status": "FAILED", "error": "OOM"}) is True

    source = inspect.getsource(langgraph_adapter._run_comfyui_image_attempt)
    assert "status_response.status_code == 402" in source
    assert 'job_monitor["status"] = "PAYMENT_REQUIRED"' in source


def test_runpod_preflight_blocks_payment_without_exposing_credentials(monkeypatch):
    class PaymentRequiredResponse:
        status_code = 402

    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "comfyui")
    monkeypatch.setenv("RUNPOD_API_KEY", "private-key")
    monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "main-private-endpoint")
    monkeypatch.setenv("COMFYUI_QWEN_EDIT_ENDPOINT_ID", "qwen-private-endpoint")
    monkeypatch.setattr(
        ui_server.requests,
        "get",
        lambda *args, **kwargs: PaymentRequiredResponse(),
    )

    result = ui_server._runpod_preflight()
    serialized = json.dumps(result)

    assert result["status"] == "blocked"
    assert result["http_status"] == 402
    assert {item["endpoint"] for item in result["blockers"]} == {
        "principal",
        "Qwen Cast Bible",
    }
    assert "private-key" not in serialized
    assert "main-private-endpoint" not in serialized
    assert "qwen-private-endpoint" not in serialized


def test_create_run_stops_before_thread_when_runpod_preflight_blocks(monkeypatch):
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "comfyui")
    monkeypatch.setattr(
        ui_server,
        "_runpod_preflight",
        lambda: {
            "status": "blocked",
            "http_status": 402,
            "blockers": [
                {
                    "code": "payment_required",
                    "message": "RunPod sem saldo",
                }
            ],
            "warnings": [],
            "probes": [],
        },
    )
    monkeypatch.setattr(
        ui_server,
        "_start_pipeline_run",
        lambda **kwargs: pytest.fail("pipeline thread must not start"),
    )

    response = ui_server.app.test_client().post(
        "/api/runs",
        json={
            "story_text": "Uma história válida.",
            "image_style": "comic_storybook",
            "image_quality_preset": "high",
        },
    )

    assert response.status_code == 402
    assert response.get_json()["error"] == "RunPod sem saldo"


def test_retry_run_uses_local_cast_resume_when_only_payment_is_blocked(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "comfyui")
    runs_root = tmp_path / "runs"
    retry_of = "20260722_001022_77706927"
    source_output = runs_root / retry_of / "output"
    source_output.mkdir(parents=True)
    (source_output / "alice_character_reference_front.png").write_bytes(b"p" * 2000)
    create_cast_reference_resume_manifest(
        source_output.parent,
        approved_summary=None,
        overrides=[
            "alice_character_reference_front.png=" "alice_character_reference_front.png"
        ],
    )
    monkeypatch.setattr(ui_server, "RUNS_ROOT", runs_root.resolve())
    monkeypatch.setattr(
        ui_server,
        "_runpod_preflight",
        lambda: {
            "status": "blocked",
            "http_status": 402,
            "blockers": [
                {
                    "code": "payment_required",
                    "message": "RunPod sem saldo",
                }
            ],
            "warnings": [],
            "probes": [],
        },
    )
    captured = {}

    def fake_start_pipeline_run(**kwargs):
        captured.update(kwargs)
        return {
            "id": "20260722_010000_aaaaaaaa",
            "status": "running",
            "run_dir": str(tmp_path / "run"),
        }

    monkeypatch.setattr(ui_server, "_start_pipeline_run", fake_start_pipeline_run)

    response = ui_server.app.test_client().post(
        "/api/runs",
        json={
            "story_text": "Uma história válida.",
            "image_style": "comic_storybook",
            "image_quality_preset": "high",
            "retry_of": retry_of,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["cast_resume_local_only"] is True
    assert captured["cast_resume_local_only"] is True
    assert captured["retry_of"] == retry_of


def test_create_run_skips_runpod_preflight_for_fal(monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "fal")
    monkeypatch.setattr(
        ui_server,
        "_runpod_preflight",
        lambda: pytest.fail("RunPod preflight is not required for fal"),
    )
    captured = {}

    def fake_start_pipeline_run(**kwargs):
        captured.update(kwargs)
        return {
            "id": "20260726_010000_bbbbbbbb",
            "status": "running",
            "run_dir": str(tmp_path / "run"),
        }

    monkeypatch.setattr(ui_server, "_start_pipeline_run", fake_start_pipeline_run)

    response = ui_server.app.test_client().post(
        "/api/runs",
        json={
            "story_text": "Uma história válida.",
            "image_style": "comic_storybook",
            "image_quality_preset": "high",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["cast_resume_local_only"] is False
    assert captured["cast_resume_local_only"] is False


def test_retry_run_without_summary_or_manifest_copies_nothing(monkeypatch, tmp_path):
    runs_root = tmp_path / "runs"
    run_id = "20260722_001022_77706927"
    source_output = runs_root / run_id / "output"
    target_output = runs_root / "20260722_010000_aaaaaaaa" / "output"
    source_output.mkdir(parents=True)
    target_output.mkdir(parents=True)
    valid = source_output / "alice_character_reference_front.png"
    valid.write_bytes(b"p" * 2000)
    (source_output / "alice_character_reference_profile.png").write_bytes(b"x")
    (source_output / "scene_1.png").write_bytes(b"s" * 2000)
    monkeypatch.setattr(ui_server, "RUNS_ROOT", runs_root.resolve())

    copied = ui_server._copy_cast_reference_resume_assets(run_id, target_output)

    assert copied == []
    assert not (target_output / valid.name).exists()
    assert not (target_output / "scene_1.png").exists()
    with pytest.raises(ValueError, match="invalid_retry_run_id"):
        ui_server._validated_retry_run_id("../escape")


def test_retry_run_with_summary_copies_only_automatic_pass_views(
    monkeypatch,
    tmp_path,
):
    runs_root = tmp_path / "runs"
    run_id = "20260722_001022_77706927"
    run_dir = runs_root / run_id
    source_output = run_dir / "output"
    target_output = runs_root / "20260722_010000_aaaaaaaa" / "output"
    source_output.mkdir(parents=True)
    target_output.mkdir(parents=True)
    front = source_output / "alice_character_reference_front.png"
    rejected = source_output / "alice_character_reference_profile_attempt_2.png"
    front.write_bytes(b"f" * 2000)
    rejected.write_bytes(b"r" * 2000)
    checksum = hashlib.sha256(front.read_bytes()).hexdigest()
    (run_dir / "pipeline_summary.json").write_text(
        json.dumps(
            {
                "visual_bible": {
                    "cast_bible": {
                        "characters": [
                            {
                                "id": "alice",
                                "reference": {
                                    "views": {
                                        "front": {
                                            "automatic_approved": True,
                                            "path": "output/alice_character_reference_front.png",
                                            "checksum": checksum,
                                        },
                                        "profile": {
                                            "automatic_approved": False,
                                            "path": "",
                                        },
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_server, "RUNS_ROOT", runs_root.resolve())

    copied = ui_server._copy_cast_reference_resume_assets(run_id, target_output)

    assert copied == [front.name]
    assert (target_output / front.name).is_file()
    assert not (target_output / rejected.name).exists()
    trust = json.loads(
        (target_output / ui_server.CAST_REFERENCE_RESUME_TRUST_FILE).read_text(
            encoding="utf-8"
        )
    )
    assert trust["source_run_id"] == run_id
    assert trust["assets"] == [
        {
            "name": front.name,
            "sha256": checksum,
        }
    ]


def test_retry_run_uses_checksum_verified_manifest_as_authoritative_allowlist(
    monkeypatch,
    tmp_path,
):
    runs_root = tmp_path / "runs"
    run_id = "20260722_001022_77706927"
    run_dir = runs_root / run_id
    source_output = run_dir / "output"
    target_output = runs_root / "20260722_010000_aaaaaaaa" / "output"
    source_output.mkdir(parents=True)
    target_output.mkdir(parents=True)
    front = source_output / "alice_character_reference_front.png"
    profile = source_output / "alice_character_reference_profile.png"
    front.write_bytes(b"f" * 2000)
    profile.write_bytes(b"p" * 2000)
    front_checksum = hashlib.sha256(front.read_bytes()).hexdigest()
    profile_checksum = hashlib.sha256(profile.read_bytes()).hexdigest()
    (run_dir / "pipeline_summary.json").write_text(
        json.dumps(
            {
                "visual_bible": {
                    "cast_bible": {
                        "characters": [
                            {
                                "id": "alice",
                                "reference": {
                                    "views": {
                                        "front": {
                                            "automatic_approved": True,
                                            "path": f"output/{front.name}",
                                            "checksum": front_checksum,
                                        }
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / ui_server.CAST_REFERENCE_RESUME_MANIFEST).write_text(
        json.dumps(
            {
                "schema_version": ui_server.CAST_REFERENCE_RESUME_SCHEMA_VERSION,
                "source_run_id": run_id,
                "assets": [
                    {
                        "source_name": profile.name,
                        "destination_name": profile.name,
                        "sha256": profile_checksum,
                        "validated": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_server, "RUNS_ROOT", runs_root.resolve())

    copied = ui_server._copy_cast_reference_resume_assets(run_id, target_output)

    assert copied == [profile.name]
    assert not (target_output / front.name).exists()
    assert (target_output / profile.name).is_file()


def test_retry_run_invalid_manifest_blocks_summary_fallback(
    monkeypatch,
    tmp_path,
):
    runs_root = tmp_path / "runs"
    run_id = "20260722_001022_77706927"
    run_dir = runs_root / run_id
    source_output = run_dir / "output"
    target_output = runs_root / "20260722_010000_aaaaaaaa" / "output"
    source_output.mkdir(parents=True)
    target_output.mkdir(parents=True)
    front = source_output / "alice_character_reference_front.png"
    front.write_bytes(b"f" * 2000)
    checksum = hashlib.sha256(front.read_bytes()).hexdigest()
    (run_dir / "pipeline_summary.json").write_text(
        json.dumps(
            {
                "visual_bible": {
                    "cast_bible": {
                        "characters": [
                            {
                                "id": "alice",
                                "reference": {
                                    "views": {
                                        "front": {
                                            "automatic_approved": True,
                                            "path": f"output/{front.name}",
                                            "checksum": checksum,
                                        }
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / ui_server.CAST_REFERENCE_RESUME_MANIFEST).write_text(
        '{"schema_version":"invalid","assets":[]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_server, "RUNS_ROOT", runs_root.resolve())

    copied = ui_server._copy_cast_reference_resume_assets(run_id, target_output)

    assert copied == []
    assert not (target_output / front.name).exists()


def test_resumed_cast_reference_cache_requires_matching_checksum(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    candidate = output_dir / "alice_character_reference_front.png"
    candidate.write_bytes(b"trusted-reference" * 200)
    checksum = hashlib.sha256(candidate.read_bytes()).hexdigest()
    (output_dir / ui_server.CAST_REFERENCE_RESUME_TRUST_FILE).write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source_run_id": "20260722_001022_77706927",
                "assets": [
                    {
                        "name": candidate.name,
                        "sha256": checksum,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert langgraph_adapter._trusted_resumed_cast_reference(str(candidate)) is True

    candidate.write_bytes(b"tampered-reference" * 200)

    assert langgraph_adapter._trusted_resumed_cast_reference(str(candidate)) is False


def test_retry_run_summary_normalizes_approved_attempt_to_canonical_name(
    monkeypatch,
    tmp_path,
):
    runs_root = tmp_path / "runs"
    run_id = "20260722_001022_77706927"
    run_dir = runs_root / run_id
    source_output = run_dir / "output"
    target_output = runs_root / "20260722_010000_aaaaaaaa" / "output"
    source_output.mkdir(parents=True)
    target_output.mkdir(parents=True)
    attempt = source_output / "mia_character_reference_expression_warm_attempt_2.png"
    attempt.write_bytes(b"m" * 2000)
    checksum = hashlib.sha256(attempt.read_bytes()).hexdigest()
    (run_dir / "pipeline_summary.json").write_text(
        json.dumps(
            {
                "visual_bible": {
                    "cast_bible": {
                        "characters": [
                            {
                                "id": "mia",
                                "reference": {
                                    "views": {
                                        "expression_warm": {
                                            "automatic_approved": True,
                                            "path": f"output/{attempt.name}",
                                            "checksum": checksum,
                                        }
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_server, "RUNS_ROOT", runs_root.resolve())

    copied = ui_server._copy_cast_reference_resume_assets(run_id, target_output)

    assert copied == ["mia_character_reference_expression_warm.png"]
    assert (
        target_output / "mia_character_reference_expression_warm.png"
    ).read_bytes() == attempt.read_bytes()


def test_retry_run_manifest_verifies_checksum_and_canonical_destination(
    monkeypatch,
    tmp_path,
):
    runs_root = tmp_path / "runs"
    run_id = "20260722_001022_77706927"
    run_dir = runs_root / run_id
    source_output = run_dir / "output"
    target_output = runs_root / "20260722_010000_aaaaaaaa" / "output"
    source_output.mkdir(parents=True)
    target_output.mkdir(parents=True)
    attempt = source_output / "alice_character_reference_full_body_attempt_2.png"
    attempt.write_bytes(b"a" * 2000)
    create_cast_reference_resume_manifest(
        run_dir,
        approved_summary=None,
        overrides=[
            (
                "alice_character_reference_full_body_attempt_2.png="
                "alice_character_reference_full_body.png"
            )
        ],
    )
    monkeypatch.setattr(ui_server, "RUNS_ROOT", runs_root.resolve())

    copied = ui_server._copy_cast_reference_resume_assets(run_id, target_output)

    assert copied == ["alice_character_reference_full_body.png"]
    assert (
        target_output / "alice_character_reference_full_body.png"
    ).read_bytes() == attempt.read_bytes()

    attempt.write_bytes(b"tampered" * 300)
    copied_after_tamper = ui_server._copy_cast_reference_resume_assets(
        run_id,
        target_output,
    )
    assert copied_after_tamper == []


def test_cast_reference_generation_parallelizes_only_derived_views():
    source = inspect.getsource(langgraph_adapter)

    assert "ThreadPoolExecutor" in source
    assert 'if image_provider == "comfyui" and max_workers > 1' in source
    assert "CAST_REFERENCE_POSE_VIEWS" in source
    assert '"identity_anchor_only"' in source
    assert "secondary_reference_path = None" in source
    assert "_block_cast_reference_views_for_pose_circuit" in source
    assert 'generate_reference_attempt(\n                            "front"' in source
    assert '"status": "RESUMED_LOCAL_QA"' in source
    assert '"estimated_cost_usd": 0.0' in source
    assert '"status": "LOCAL_ASSET_MISSING"' in source
    assert '"generation_method": "local_resume_missing_asset"' in source


def test_dagster_pipeline_propagates_local_cast_resume_flag():
    from orchestration import enhanced_dagster_pipeline

    source = inspect.getsource(enhanced_dagster_pipeline)

    assert "cast_resume_local_only: bool = False" in source
    assert '"cast_resume_local_only": config.cast_resume_local_only' in source
    assert '"cast_resume_local_only": enhanced_multimodal_input_asset.get(' in source


def test_cast_reference_identity_gate_blocks_a_mismatched_derived_view(
    monkeypatch,
):
    from open3d_implementation.core import local_visual_qa

    assessment = local_visual_qa.LocalCastIdentityAssessment(
        accepted=False,
        score=70.0,
        crop_similarity=0.70,
        composition_similarity=0.80,
        crop_threshold=0.90,
        composition_threshold=0.82,
        reference_box=(1, 2, 3, 4),
        candidate_box=(5, 6, 7, 8),
        model_name="facebook/dinov2-small",
    )
    monkeypatch.setattr(
        local_visual_qa,
        "evaluate_local_cast_reference_identity",
        lambda **kwargs: assessment,
    )
    metric = {
        "semantic_accepted": True,
        "semantic_score": 96.0,
        "semantic_critical_failures": [],
        "issues": [],
    }

    _apply_cast_reference_identity_gate(
        character={
            "id": "alice",
            "name": "Alice",
            "identity_prompt": "one ten-year-old Victorian child",
        },
        anchor_path="front.png",
        candidate_path="profile.png",
        view_id="profile",
        image_metric=metric,
    )

    assert metric["identity_accepted"] is False
    assert metric["identity_score"] == 70.0
    assert metric["semantic_accepted"] is False
    assert metric["semantic_score"] == 79.0
    assert metric["semantic_critical_failures"] == ["identity_mismatch_alice"]
    assert metric["character_identity"][0]["dimensions"] == {
        "appearance_embedding": 70.0,
        "composition_embedding": 80.0,
    }


def test_scene_cast_identity_includes_every_named_character():
    visual_bible = _build_visual_bible(
        "Alice conversa com Ludovico. Ludovico mostra um truque para Alice.",
        "comic_storybook",
    )
    scene = {
        "description": "Alice and Professor Ludovico stand beside the tea table.",
        "must_include": ["one Alice", "one adult Ludovico"],
    }

    scene_cast = _scene_cast_characters(scene, visual_bible)
    identity = _scene_cast_identity_text(scene, visual_bible)
    prompt = _build_flux2_image_prompt(
        scene,
        "comic_storybook",
        visual_bible,
    )

    assert [character["id"] for character in scene_cast] == ["alice", "ludovico"]
    assert "same Alice in every scene" in identity
    assert "same Professor Ludovico in every scene" in identity
    assert "45 to 55" in prompt


def test_identity_retry_switches_to_the_character_that_failed(tmp_path):
    visual_bible = _build_visual_bible(
        "Alice conversa com Ludovico. Ludovico responde a Alice.",
        "comic_storybook",
    )
    reference_paths = {}
    for character in visual_bible["cast_bible"]["characters"]:
        reference_paths[character["id"]] = _approve_cast_reference_pack(
            character,
            tmp_path,
            payload_byte=character["id"].encode("utf-8")[:1],
        )

    selected = _identity_retry_reference_path(
        {
            "character_identity": [
                {"character_id": "alice", "accepted": True},
                {"character_id": "ludovico", "accepted": False},
            ]
        },
        visual_bible,
        reference_paths["alice"],
    )
    prompt = _build_qwen_semantic_edit_prompt(
        {"description": "Alice and Ludovico stand at the tea table."},
        "Restore the failed character identity.",
        character_reference_name="Professor Ludovico",
    )

    assert selected == reference_paths["ludovico"]
    assert "approved identity reference for Professor Ludovico" in prompt
    assert "replace Professor Ludovico" in prompt


def test_cast_reference_gate_requires_all_characters_used_by_scenes(
    tmp_path,
):
    visual_bible = _build_visual_bible(
        "Alice conversa com Ludovico. Ludovico responde a Alice.",
        "comic_storybook",
    )
    scenes = [
        {
            "scene_id": 1,
            "description": "Alice and Ludovico talk in the university garden.",
        }
    ]
    required = _required_scene_cast(scenes, visual_bible)

    blocked = _refresh_cast_bible_status(visual_bible, required)
    assert blocked["status"] == "blocked"
    assert blocked["missing_reference_ids"] == ["alice", "ludovico"]

    for character in required:
        _approve_cast_reference_pack(character, tmp_path, payload_byte=b"x")

    approved = _refresh_cast_bible_status(visual_bible, required)
    assert approved["status"] == "approved"
    assert approved["approved_reference_ids"] == ["alice", "ludovico"]
    assert scenes[0]["cast_character_ids"] == ["alice", "ludovico"]


def test_cast_reference_waiting_stage_distinguishes_retry_from_human_review():
    blocked = [{"reference": {"automatic_approved": False}}]
    ready = [
        {"reference": {"automatic_approved": True}},
        {"reference": {"automatic_approved": True}},
    ]

    assert (
        _cast_reference_waiting_stage(blocked) == "awaiting_cast_reference_regeneration"
    )
    assert _cast_reference_waiting_stage(ready) == "awaiting_cast_reference_approval"


def test_cast_reference_resume_reuses_every_existing_attempt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    attempt_path = Path(_cast_reference_attempt_path("alice", "profile", 1))
    attempt_path.parent.mkdir(parents=True)
    attempt_path.write_bytes(b"x" * 1001)

    assert attempt_path.name.endswith("_attempt_2.png")
    assert _cast_reference_attempt_reusable(str(attempt_path)) is True


def test_cast_identity_thresholds_are_calibrated_per_view(monkeypatch):
    monkeypatch.delenv("LOCAL_CAST_IDENTITY_MIN_SIMILARITY", raising=False)

    assert _identity_similarity_threshold("profile") == 0.65
    assert _identity_composition_threshold("profile") == 0.72
    assert _identity_similarity_threshold("three_quarter") == 0.75
    assert _identity_composition_threshold("three_quarter") == 0.80
    assert _identity_similarity_threshold("full_body") == 0.68
    assert _identity_composition_threshold("full_body") is None
    assert _identity_similarity_threshold("expression_concerned") == 0.84


def test_refresh_cast_stage_reports_regeneration_required():
    visual_bible = _build_visual_bible(
        "Alice caminha no jardim. Alice olha para Ludovico.",
        "comic_storybook",
    )
    summary = {
        "scenes": [{"scene_id": 1, "description": "Alice talks to Ludovico."}],
        "visual_bible": visual_bible,
        "quality_metrics": {},
    }

    stage = ui_server._refresh_cast_stage(summary)

    assert stage == "awaiting_cast_reference_regeneration"
    assert summary["quality_metrics"]["cast_reference_status"] == (
        "regeneration_required"
    )


def test_refresh_cast_stage_does_not_require_lora_for_fal(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_server, "load_dotenv", lambda *args, **kwargs: True)
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "fal")
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _approve_cast_reference_pack(alice, tmp_path)
    summary = {
        "scenes": [{"scene_id": 1, "description": "Alice walks in the garden."}],
        "visual_bible": visual_bible,
        "quality_metrics": {},
    }

    stage = ui_server._refresh_cast_stage(summary)

    assert stage == "ready_to_generate_scenes"
    assert summary["visual_bible"]["lora_gate"] == {
        "status": "approved",
        "blockers": [],
        "reason": "not_required_for_fal",
    }


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


def test_cast_reference_revision_updates_checksum_version_and_lora_contract(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("COMFYUI_CHARACTER_LORA_ALICE", "char_alice_v1.safetensors")
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    first_path = _approve_cast_reference_pack(alice, tmp_path, payload_byte=b"a")
    scene = {"scene_id": 1, "description": "Alice walks through the garden."}
    first_signature = _scene_cast_reference_versions(scene, visual_bible)

    assert set(alice["reference"]["views"]) == set(CAST_REFERENCE_VIEWS)
    assert alice["reference"]["version"] == 1
    assert alice["lora"]["status"] == "configured"
    assert Path(first_path).name == "alice-three_quarter.png"

    _approve_cast_reference_pack(alice, tmp_path, payload_byte=b"b")
    second_signature = _scene_cast_reference_versions(scene, visual_bible)

    assert alice["reference"]["version"] == 2
    assert first_signature != second_signature
    assert alice["lora"]["expected_name"] == "char_alice_v2.safetensors"
    assert alice["lora"]["trigger_token"] == "char_alice_v2"
    assert alice["lora"]["status"] == "stale"


def test_flux2_lora_gate_requires_current_individual_character_adapter(
    monkeypatch,
):
    monkeypatch.setenv("COMFYUI_FLUX2_STYLE_LORA", "style_storybook_v1.safetensors")
    monkeypatch.setenv("COMFYUI_CHARACTER_LORA_ALICE", "char_alice_v1.safetensors")
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    scene = {"scene_id": 1, "description": "Alice walks through the garden."}

    approved = _flux2_lora_gate([scene], visual_bible)
    assert approved["status"] == "approved"

    monkeypatch.setenv("COMFYUI_CHARACTER_LORA_ALICE", "alice-old.safetensors")
    blocked = _flux2_lora_gate([scene], visual_bible)
    assert blocked["status"] == "blocked"
    assert blocked["blockers"] == [
        "character_lora_version_mismatch:alice:char_alice_v1.safetensors"
    ]


def test_cast_bible_export_creates_checksum_verified_training_pack(tmp_path):
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _approve_cast_reference_pack(alice, tmp_path)
    summary_path = tmp_path / "pipeline_summary.json"
    summary_path.write_text(
        json.dumps({"visual_bible": visual_bible}), encoding="utf-8"
    )

    packs = export_training_packs(summary_path, tmp_path / "training")
    spec = json.loads((packs[0] / "training_spec.json").read_text(encoding="utf-8"))

    assert spec["adapter_filename"] == "char_alice_v1.safetensors"
    assert spec["trigger_token"] == "char_alice_v1"
    assert spec["training_images"] == len(CAST_REFERENCE_VIEWS)
    assert len((packs[0] / "manifest.jsonl").read_text().splitlines()) == len(
        CAST_REFERENCE_VIEWS
    )


def test_cast_reference_requires_separate_human_approval(tmp_path):
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _auto_approve_cast_reference_pack(alice, tmp_path)

    assert alice["reference"]["status"] == "pending_human_review"
    assert alice["reference"]["approved"] is False

    approved = _set_cast_reference_human_approval(alice, True)

    assert approved["status"] == "approved"
    assert approved["human_approved"] is True
    assert all(view["human_approved"] is True for view in approved["views"].values())


def test_cast_approval_endpoint_persists_registry_and_invalidates_old_assets(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(ui_server, "load_dotenv", lambda *args, **kwargs: True)
    registry_path = tmp_path / "cast-registry.json"
    monkeypatch.setenv("AI_FILM_CAST_BIBLE_REGISTRY", str(registry_path))
    monkeypatch.setenv("COMFYUI_FLUX2_STYLE_LORA", "style_storybook_v1.safetensors")
    monkeypatch.setenv("COMFYUI_CHARACTER_LORA_ALICE", "char_alice_v1.safetensors")
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _auto_approve_cast_reference_pack(alice, tmp_path)
    scenes = [{"scene_id": 1, "description": "Alice walks through the garden."}]
    _required_scene_cast(scenes, visual_bible)
    story_path = tmp_path / "historia.txt"
    story_path.write_text("Alice walks through the garden.", encoding="utf-8")
    summary = {
        "status": "awaiting_cast_reference_approval",
        "current_step": "awaiting_cast_reference_approval",
        "scenes": scenes,
        "scenes_count": 1,
        "visual_bible": visual_bible,
        "scene_videos": [{"scene_id": 1, "video_path": "old.mp4"}],
        "curation": {
            "scenes": {
                "1": {
                    "status": "approved",
                    "approved_attempt_id": "attempt_1",
                    "attempts": [{"id": "attempt_1", "status": "approved"}],
                }
            }
        },
    }
    run_id = "cast-approval-test"
    ui_server.RUNS[run_id] = {
        "id": run_id,
        "status": "completed",
        "run_dir": str(tmp_path),
        "image_style": DEFAULT_IMAGE_STYLE,
        "image_quality_preset": "high",
        "summary": summary,
        "log": [],
    }
    try:
        response = ui_server.app.test_client().post(
            f"/api/runs/{run_id}/cast-reference-approval",
            json={"character_id": "alice", "approved": True},
        )
    finally:
        ui_server.RUNS.pop(run_id, None)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["status"] == "ready_to_generate_scenes"
    assert payload["summary"]["scene_videos"] == []
    assert payload["summary"]["curation"]["scenes"]["1"]["approved_attempt_id"] is None
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["characters"][0]["reference"]["human_approved"] is True
    assert Path(
        registry["characters"][0]["reference"]["views"]["front"]["path"]
    ).is_absolute()


def test_cast_approval_rolls_back_in_memory_when_persistence_fails(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(ui_server, "load_dotenv", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        ui_server,
        "_persist_cast_bible_registry",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _auto_approve_cast_reference_pack(alice, tmp_path)
    scenes = [{"scene_id": 1, "description": "Alice walks through the garden."}]
    _required_scene_cast(scenes, visual_bible)
    run_id = "cast-approval-rollback"
    ui_server.RUNS[run_id] = {
        "id": run_id,
        "status": "completed",
        "run_dir": str(tmp_path),
        "summary": {
            "scenes": scenes,
            "visual_bible": visual_bible,
            "curation": {
                "scenes": {
                    "1": {
                        "status": "approved",
                        "approved_attempt_id": "attempt_1",
                        "attempts": [{"id": "attempt_1", "status": "approved"}],
                    }
                }
            },
        },
    }
    try:
        response = ui_server.app.test_client().post(
            f"/api/runs/{run_id}/cast-reference-approval",
            json={"character_id": "alice", "approved": True},
        )
        persisted = ui_server.RUNS[run_id]["summary"]
    finally:
        ui_server.RUNS.pop(run_id, None)

    assert response.status_code == 409
    assert (
        persisted["visual_bible"]["cast_bible"]["characters"][0]["reference"][
            "human_approved"
        ]
        is False
    )
    assert persisted["curation"]["scenes"]["1"]["status"] == "approved"


def test_approved_registry_is_materialized_inside_next_run(monkeypatch, tmp_path):
    registry_path = tmp_path / "cast-registry.json"
    monkeypatch.setenv("AI_FILM_CAST_BIBLE_REGISTRY", str(registry_path))
    first_run = tmp_path / "first"
    first_run.mkdir()
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _approve_cast_reference_pack(alice, first_run)
    visual_bible["cast_bible"]["required_for_scenes"] = ["alice"]
    summary = {
        "image_style": DEFAULT_IMAGE_STYLE,
        "visual_bible": visual_bible,
    }
    ui_server._persist_cast_bible_registry(summary, first_run)

    next_run = tmp_path / "next"
    next_run.mkdir()
    monkeypatch.chdir(next_run)
    reloaded = _build_cast_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    reference = reloaded["characters"][0]["reference"]

    assert reference["approved"] is True
    assert reference["human_approved"] is True
    assert Path(reference["path"]).is_file()
    assert str(reference["path"]).startswith("output/cast_bible/alice/v1/")


def test_continue_after_cast_is_blocked_until_versioned_loras_are_configured(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(ui_server, "load_dotenv", lambda *args, **kwargs: True)
    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "comfyui")
    registry_path = tmp_path / "cast-registry.json"
    monkeypatch.setenv("AI_FILM_CAST_BIBLE_REGISTRY", str(registry_path))
    monkeypatch.setenv("COMFYUI_FLUX2_STYLE_LORA", "style_storybook_v1.safetensors")
    monkeypatch.delenv("COMFYUI_CHARACTER_LORA_ALICE", raising=False)
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _approve_cast_reference_pack(alice, tmp_path)
    scenes = [{"scene_id": 1, "description": "Alice walks through the garden."}]
    _required_scene_cast(scenes, visual_bible)
    (tmp_path / "historia.txt").write_text(
        "Alice walks through the garden.", encoding="utf-8"
    )
    run_id = "cast-continue-blocked"
    ui_server.RUNS[run_id] = {
        "id": run_id,
        "status": "completed",
        "run_dir": str(tmp_path),
        "image_style": DEFAULT_IMAGE_STYLE,
        "image_quality_preset": "high",
        "summary": {"scenes": scenes, "visual_bible": visual_bible},
    }
    try:
        response = ui_server.app.test_client().post(
            f"/api/runs/{run_id}/continue-after-cast"
        )
    finally:
        ui_server.RUNS.pop(run_id, None)

    assert response.status_code == 409
    assert response.get_json()["stage"] == "awaiting_character_lora_training"
    assert response.get_json()["blockers"] == ["character_lora_missing:alice"]


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


def test_flux2_klein_workflow_chains_style_and_character_loras():
    workflow = _build_flux2_klein_workflow(
        directed_prompt="aifilm_alice_v1 beneath an oak tree",
        quality_preset=_resolve_quality_preset("high"),
        scene_seed=20260720,
        scene_id=1,
        lora_stack=[
            {"name": "storybook-style.safetensors", "strength": 0.7},
            {"name": "alice-v1.safetensors", "strength": 0.85},
        ],
    )

    assert workflow["20"]["class_type"] == "LoraLoaderModelOnly"
    assert workflow["20"]["inputs"]["model"] == ["1", 0]
    assert workflow["20"]["inputs"]["strength_model"] == 0.7
    assert workflow["21"]["inputs"]["model"] == ["20", 0]
    assert workflow["21"]["inputs"]["lora_name"] == "alice-v1.safetensors"
    assert workflow["7"]["inputs"]["model"] == ["21", 0]


@pytest.mark.parametrize(
    "name",
    (
        "../alice.safetensors",
        str((Path.cwd() / "alice.safetensors").resolve()),
        "alice.ckpt",
        "",
    ),
)
def test_flux2_lora_name_rejects_unsafe_paths(name):
    with pytest.raises(ValueError, match="invalid_comfyui_lora_name"):
        _validated_lora_name(name)


def test_flux2_scene_lora_stack_and_prompt_follow_cast_bible(monkeypatch):
    monkeypatch.setenv("COMFYUI_FLUX2_STYLE_LORA", "storybook-style.safetensors")
    monkeypatch.setenv("COMFYUI_FLUX2_STYLE_LORA_TRIGGER", "aifilm_storybook_v1")
    monkeypatch.setenv("COMFYUI_CHARACTER_LORA_ALICE", "alice-v1.safetensors")
    monkeypatch.setenv("COMFYUI_CHARACTER_LORA_LUDOVICO", "ludovico-v1.safetensors")
    visual_bible = _build_visual_bible(
        "Alice conversa com Ludovico. Ludovico responde a Alice.",
        "comic_storybook",
    )
    scene = {
        "description": "Alice and Professor Ludovico speak beside an oak tree.",
        "must_include": ["Alice", "Professor Ludovico"],
    }

    stack = _flux2_scene_lora_stack(scene, visual_bible)
    tokens = _scene_lora_trigger_tokens(scene, visual_bible)
    prompt = _build_flux2_image_prompt(scene, "comic_storybook", visual_bible)

    assert [item["role"] for item in stack] == ["style", "character", "character"]
    assert [item["name"] for item in stack] == [
        "storybook-style.safetensors",
        "alice-v1.safetensors",
        "ludovico-v1.safetensors",
    ]
    assert tokens == "aifilm_storybook_v1, char_alice_v1, char_ludovico_v1"
    assert "char_alice_v1" in prompt
    assert "char_ludovico_v1" in prompt


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


def test_qwen_character_edit_uses_bounded_identity_preserving_denoise():
    workflow = _build_qwen_image_edit_2511_workflow(
        edit_prompt="Rotate the canonical character to a three-quarter view.",
        input_image_name="alice_front.png",
        reference_image_name="alice_front.png",
        scene_seed=11,
        scene_id="alice_reference",
        negative_prompt="older Alice, redesigned face",
        edit_denoise=0.48,
    )

    assert workflow["12"]["inputs"]["denoise"] == 0.48


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


def test_runpod_cost_guard_reserves_atomically_and_blocks_over_budget(monkeypatch):
    monkeypatch.setenv("AI_FILM_RUNPOD_HARD_COST_GUARD_ENABLED", "true")
    monkeypatch.setenv("AI_FILM_RUNPOD_HARD_BUDGET_USD", "0.30")
    monkeypatch.setenv("AI_FILM_RUNPOD_MIN_BALANCE_USD", "5.00")
    monkeypatch.setenv("AI_FILM_RUNPOD_MAX_WORKERS_ALLOWED", "1")
    monkeypatch.setattr(
        runpod_cost_guard,
        "fetch_runpod_account_cost",
        lambda api_key: runpod_cost_guard.RunPodAccountCost(9.73, 0.022, 80.0),
    )
    monkeypatch.setattr(
        runpod_cost_guard,
        "fetch_runpod_endpoint_workers_max",
        lambda api_key, endpoint_id: 1,
    )

    reservation = runpod_cost_guard.reserve_runpod_job_budget(
        api_key="test-key",
        endpoint_id="endpoint-1",
        budget_scope="run-1",
        estimated_max_cost_usd=0.20,
    )

    assert reservation["status"] == "reserved"
    assert reservation["run_reserved_usd"] == 0.20
    with pytest.raises(
        runpod_cost_guard.RunPodCostGuardError,
        match="run_budget_exceeded",
    ):
        runpod_cost_guard.reserve_runpod_job_budget(
            api_key="test-key",
            endpoint_id="endpoint-1",
            budget_scope="run-1",
            estimated_max_cost_usd=0.20,
        )

    settlement = runpod_cost_guard.settle_runpod_job_budget(
        budget_scope="run-1",
        reserved_usd=0.20,
        actual_cost_usd=0.05,
    )
    assert settlement["run_accounted_usd"] == 0.05

    second_reservation = runpod_cost_guard.reserve_runpod_job_budget(
        api_key="test-key",
        endpoint_id="endpoint-1",
        budget_scope="run-1",
        estimated_max_cost_usd=0.20,
    )
    assert second_reservation["run_reserved_usd"] == 0.25


def test_runpod_submission_does_not_post_when_cost_guard_blocks(monkeypatch):
    monkeypatch.setenv("AI_FILM_RUNPOD_HARD_COST_GUARD_ENABLED", "true")
    monkeypatch.setattr(
        langgraph_adapter,
        "reserve_runpod_job_budget",
        lambda **kwargs: (_ for _ in ()).throw(
            runpod_cost_guard.RunPodCostGuardError("budget_blocked")
        ),
    )
    monkeypatch.setattr(
        langgraph_adapter.requests,
        "post",
        lambda *args, **kwargs: pytest.fail("remote job must not be submitted"),
    )

    with pytest.raises(
        runpod_cost_guard.RunPodCostGuardError,
        match="budget_blocked",
    ):
        _submit_runpod_job(
            run_url="https://api.runpod.ai/v2/test/run",
            request_payload={"input": {"workflow": {}}},
            headers={"Authorization": "Bearer test"},
            api_key="test-key",
            endpoint_id="endpoint-1",
            budget_scope="run-1",
            estimated_max_cost_usd=0.20,
        )


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


def test_runpod_poll_timeout_separates_queue_from_execution():
    assert (
        _runpod_poll_timeout_reason(
            {
                "status": "IN_QUEUE",
                "delayTime": 600_000,
                "executionTime": 0,
            },
            max_queue_wait_seconds=900,
            max_execution_wait_seconds=600,
        )
        is None
    )
    assert (
        _runpod_poll_timeout_reason(
            {
                "status": "IN_PROGRESS",
                "delayTime": 600_000,
                "executionTime": 215_000,
            },
            max_queue_wait_seconds=900,
            max_execution_wait_seconds=600,
        )
        is None
    )
    assert (
        _runpod_poll_timeout_reason(
            {"status": "IN_QUEUE", "delayTime": 900_000},
            max_queue_wait_seconds=900,
            max_execution_wait_seconds=600,
        )
        == "queue_timeout_after_900s"
    )
    assert (
        _runpod_poll_timeout_reason(
            {"status": "IN_PROGRESS", "executionTime": 600_000},
            max_queue_wait_seconds=900,
            max_execution_wait_seconds=600,
        )
        == "execution_timeout_after_600s"
    )


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


def test_local_character_identity_comparison_rejects_any_failed_anchor(
    monkeypatch,
):
    from open3d_implementation.core import local_visual_qa

    monkeypatch.setattr(local_visual_qa, "_load_rgb_image", lambda path: object())
    monkeypatch.setattr(
        local_visual_qa,
        "_load_local_vision_model",
        lambda *args: (object(), object()),
    )
    monkeypatch.setattr(
        local_visual_qa,
        "_run_local_visual_prompt",
        lambda **kwargs: ("1: yes\n2: yes\n3: no\n4: yes\n5: yes\n6: yes"),
    )

    result = local_visual_qa.evaluate_local_character_identity(
        reference_path=Path("reference.png"),
        candidate_path=Path("candidate.png"),
        character_id="alice",
        character_name="Alice",
        identity_prompt="one ten-year-old Victorian child",
    )

    assert result.accepted is False
    assert result.score == pytest.approx(87.5, abs=0.1)
    assert result.answers[2].criterion.code == "identity_hair_alice"
    assert result.answers[2].matched is False


def test_local_narrative_identity_uses_contrastive_face_prototypes(
    monkeypatch,
):
    import torch
    from PIL import Image

    from open3d_implementation.core import local_visual_qa

    image = Image.new("RGB", (256, 256), "white")
    monkeypatch.setattr(local_visual_qa, "_load_rgb_image", lambda _path: image)
    monkeypatch.setattr(
        local_visual_qa,
        "_primary_reference_face",
        lambda source: (source, (10, 10, 110, 110)),
    )
    monkeypatch.setattr(
        local_visual_qa,
        "_face_candidate_boxes",
        lambda _source: ((20, 20, 120, 120), (130, 30, 220, 120)),
    )
    monkeypatch.setattr(
        local_visual_qa,
        "_expanded_face_crop",
        lambda source, _box: source,
    )

    class Processor:
        def __call__(self, **_kwargs):
            return {}

    class Output:
        last_hidden_state = torch.tensor(
            [
                [[1.0, 0.0]],
                [[0.0, 1.0]],
                [[0.95, 0.05]],
                [[0.05, 0.95]],
            ]
        )

    class Model:
        def __call__(self, **_kwargs):
            return Output()

    monkeypatch.setattr(
        local_visual_qa,
        "_load_local_identity_model",
        lambda *_args: (Processor(), Model()),
    )

    result = local_visual_qa.evaluate_local_narrative_identity(
        reference_paths=[Path("alice-front.png")],
        negative_reference_paths=[Path("ludovico-front.png")],
        candidate_path=Path("scene.png"),
        character_id="alice",
    )

    assert result.accepted is True
    assert result.score >= 80.0
    assert result.candidate_box == (20, 20, 120, 120)
    assert result.face_similarity > 0.9
    assert result.closest_negative_similarity < 0.2
    assert result.similarity_margin and result.similarity_margin > 0.7


def test_local_narrative_identity_rejects_face_closer_to_another_character(
    monkeypatch,
):
    import torch
    from PIL import Image

    from open3d_implementation.core import local_visual_qa

    image = Image.new("RGB", (256, 256), "white")
    monkeypatch.setattr(local_visual_qa, "_load_rgb_image", lambda _path: image)
    monkeypatch.setattr(
        local_visual_qa,
        "_primary_reference_face",
        lambda source: (source, (10, 10, 110, 110)),
    )
    monkeypatch.setattr(
        local_visual_qa,
        "_face_candidate_boxes",
        lambda _source: ((20, 20, 120, 120),),
    )
    monkeypatch.setattr(
        local_visual_qa,
        "_expanded_face_crop",
        lambda source, _box: source,
    )

    class Processor:
        def __call__(self, **_kwargs):
            return {}

    class Output:
        last_hidden_state = torch.tensor(
            [
                [[1.0, 0.0]],
                [[0.0, 1.0]],
                [[0.2, 0.98]],
            ]
        )

    class Model:
        def __call__(self, **_kwargs):
            return Output()

    monkeypatch.setattr(
        local_visual_qa,
        "_load_local_identity_model",
        lambda *_args: (Processor(), Model()),
    )

    result = local_visual_qa.evaluate_local_narrative_identity(
        reference_paths=[Path("alice-front.png")],
        negative_reference_paths=[Path("ludovico-front.png")],
        candidate_path=Path("scene.png"),
        character_id="alice",
    )

    assert result.accepted is False
    assert result.score < 80.0
    assert "identity_face_similarity_below_threshold" in result.issues
    assert "identity_contrastive_margin_below_threshold" in result.issues


def test_local_visual_checklist_batches_all_criteria_in_one_inference(
    monkeypatch,
):
    from open3d_implementation.core import local_visual_qa

    monkeypatch.setattr(local_visual_qa, "_load_rgb_image", lambda path: object())
    monkeypatch.setattr(
        local_visual_qa,
        "_load_local_vision_model",
        lambda *args: (object(), object()),
    )
    calls = []

    def run_prompt(**kwargs):
        calls.append(kwargs)
        return "1: yes\n2: no\n3: uncertain"

    monkeypatch.setattr(local_visual_qa, "_run_local_visual_prompt", run_prompt)
    criteria = [
        local_visual_qa.LocalVisualCriterion(
            code=f"criterion_{index}",
            question=f"criterion {index}?",
            expected="yes",
            weight=1.0,
        )
        for index in range(1, 4)
    ]

    answers = local_visual_qa.evaluate_local_visual_checklist(
        image_path=Path("candidate.png"),
        criteria=criteria,
    )

    assert len(calls) == 1
    assert [answer.answer for answer in answers] == ["yes", "no", "uncertain"]
    assert "1. criterion 1?" in calls[0]["prompt"]


def test_cast_reference_delegates_style_consistency_to_embedding_gate(
    monkeypatch,
    tmp_path,
):
    from open3d_implementation.core import local_visual_qa

    captured_codes = []

    def evaluate_checklist(**kwargs):
        captured_codes.extend(criterion.code for criterion in kwargs["criteria"])
        return [
            local_visual_qa.LocalVisualAnswer(
                criterion=criterion,
                answer=criterion.expected,
                raw_response=criterion.expected,
            )
            for criterion in kwargs["criteria"]
        ]

    monkeypatch.setattr(
        local_visual_qa,
        "evaluate_local_visual_checklist",
        evaluate_checklist,
    )
    image_path = tmp_path / "reference.png"
    image_path.write_bytes(b"reference")

    result = _evaluate_semantic_qa_with_local_vlm(
        image_path=image_path,
        scene={
            "scene_role": "character_reference",
            "must_include": ["chest-up three-quarter identity portrait"],
            "must_not_include": ["full-body view"],
        },
        style_key=DEFAULT_IMAGE_STYLE,
        model="local-test-model",
    )

    assert "style_match" not in captured_codes
    assert result["style_accepted"] is True
    assert result["style_score"] == 100


def test_cast_reference_defers_uncertain_forbidden_check_to_human_review(
    monkeypatch,
    tmp_path,
):
    from open3d_implementation.core import local_visual_qa

    def evaluate_checklist(**kwargs):
        answers = []
        for criterion in kwargs["criteria"]:
            answer = (
                "uncertain" if criterion.code == "forbidden_1" else criterion.expected
            )
            answers.append(
                local_visual_qa.LocalVisualAnswer(
                    criterion=criterion,
                    answer=answer,
                    raw_response="Props." if answer == "uncertain" else answer,
                )
            )
        return answers

    monkeypatch.setattr(
        local_visual_qa,
        "evaluate_local_visual_checklist",
        evaluate_checklist,
    )
    image_path = tmp_path / "reference.png"
    image_path.write_bytes(b"reference")
    scene = {
        "scene_role": "character_reference",
        "must_include": ["front-facing chest-up identity portrait"],
        "must_not_include": ["props or story action"],
    }

    result = _evaluate_semantic_qa_with_local_vlm(
        image_path=image_path,
        scene=scene,
        style_key=DEFAULT_IMAGE_STYLE,
        model="local-test-model",
    )

    assert result["accepted"] is True
    assert result["semantic_score"] >= 88
    assert result["critical_failures"] == []
    assert result["issues"] == ["forbidden_1_uncertain"]


def test_cast_reference_still_blocks_visible_forbidden_element(monkeypatch, tmp_path):
    from open3d_implementation.core import local_visual_qa

    def evaluate_checklist(**kwargs):
        return [
            local_visual_qa.LocalVisualAnswer(
                criterion=criterion,
                answer="yes" if criterion.code == "forbidden_1" else criterion.expected,
                raw_response="yes",
            )
            for criterion in kwargs["criteria"]
        ]

    monkeypatch.setattr(
        local_visual_qa,
        "evaluate_local_visual_checklist",
        evaluate_checklist,
    )
    image_path = tmp_path / "reference.png"
    image_path.write_bytes(b"reference")

    result = _evaluate_semantic_qa_with_local_vlm(
        image_path=image_path,
        scene={
            "scene_role": "character_reference",
            "must_include": ["front-facing chest-up identity portrait"],
            "must_not_include": ["props or story action"],
        },
        style_key=DEFAULT_IMAGE_STYLE,
        model="local-test-model",
    )

    assert result["accepted"] is False
    assert result["critical_failures"] == ["forbidden_1"]


def test_cast_reference_blocks_uncertain_identity_mark(monkeypatch, tmp_path):
    from open3d_implementation.core import local_visual_qa

    def evaluate_checklist(**kwargs):
        return [
            local_visual_qa.LocalVisualAnswer(
                criterion=criterion,
                answer=(
                    "uncertain"
                    if criterion.code == "cast_identity_unapproved_facial_mark"
                    else criterion.expected
                ),
                raw_response=(
                    "New isolated mole."
                    if criterion.code == "cast_identity_unapproved_facial_mark"
                    else criterion.expected
                ),
            )
            for criterion in kwargs["criteria"]
        ]

    monkeypatch.setattr(
        local_visual_qa,
        "evaluate_local_visual_checklist",
        evaluate_checklist,
    )
    image_path = tmp_path / "reference.png"
    image_path.write_bytes(b"reference")

    result = _evaluate_semantic_qa_with_local_vlm(
        image_path=image_path,
        scene={
            "scene_role": "character_reference",
            "must_include": ["chest-up strict left-side profile identity portrait"],
            "must_not_include": ["new isolated mole, beauty mark or dark facial spot"],
        },
        style_key=DEFAULT_IMAGE_STYLE,
        model="local-test-model",
    )

    assert result["accepted"] is False
    assert result["critical_failures"] == ["cast_identity_unapproved_facial_mark"]


def test_local_semantic_qa_records_reference_backed_identity_score(
    monkeypatch, tmp_path
):
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

    monkeypatch.setattr(
        local_visual_qa, "evaluate_local_visual_checklist", evaluate_checklist
    )
    monkeypatch.setattr(
        local_visual_qa,
        "evaluate_local_narrative_identity",
        lambda **kwargs: local_visual_qa.LocalNarrativeIdentityAssessment(
            character_id="alice",
            score=100.0,
            accepted=True,
            face_similarity=0.98,
            closest_negative_similarity=None,
            similarity_margin=None,
            face_threshold=0.68,
            margin_threshold=0.08,
            reference_boxes=((1, 2, 3, 4),),
            candidate_box=(5, 6, 7, 8),
            issues=(),
            model_name="local-test-model",
        ),
    )
    candidate_path = tmp_path / "scene.png"
    candidate_path.write_bytes(b"candidate")
    visual_bible = _build_visual_bible(
        "Alice walks through the garden. Alice looks curious.",
        DEFAULT_IMAGE_STYLE,
    )
    alice = visual_bible["cast_bible"]["characters"][0]
    _approve_cast_reference_pack(alice, tmp_path)

    result = _evaluate_semantic_qa_with_local_vlm(
        image_path=candidate_path,
        scene={
            "description": "Alice walks through the garden.",
            "must_include": ["one ten-year-old Alice"],
        },
        style_key=DEFAULT_IMAGE_STYLE,
        model="local-test-model",
        visual_bible=visual_bible,
    )

    assert result["accepted"] is True
    assert result["character_identity"][0]["character_id"] == "alice"
    assert result["character_identity"][0]["score"] == 100.0
    assert result["character_identity"][0]["accepted"] is True
    assert result["character_identity"][0]["dimensions"] == {
        "face": 100.0,
        "contrastive_margin": 100.0,
    }


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
    assert "_image_generation_provider" in source
    assert "_run_fal_flux_image_attempt" in source
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


def test_character_reference_uses_illustration_sharpness_floor(tmp_path):
    from PIL import Image, ImageDraw

    source = tmp_path / "illustrated_reference.png"
    image = Image.new("RGB", (832, 1024), "#5a504b")
    draw = ImageDraw.Draw(image)
    draw.ellipse((180, 120, 652, 620), fill="#b47443", outline="#17120f", width=5)
    draw.ellipse((300, 300, 355, 370), fill="#17120f")
    draw.ellipse((477, 300, 532, 370), fill="#17120f")
    draw.rectangle((260, 620, 572, 1000), fill="#8f4c53", outline="#17120f", width=5)
    image.save(source)
    scene = {
        "scene_role": "character_reference",
        "scene_id": "edith_reference_front",
    }

    technical = _probe_image_quality(str(source), scene=scene)

    assert technical["min_edge_sharpness"] == 20.0
    assert technical["edge_sharpness"] < technical["min_edge_sharpness"]
    assert technical["active_edge_fallback_used"] is True
    assert "blurry_image" not in technical["issues"]


def test_character_reference_still_rejects_truly_blurred_image(tmp_path):
    from PIL import Image, ImageFilter

    source = tmp_path / "blurred_reference.png"
    image = Image.new("RGB", (832, 1024), "#bca98e")
    image = image.filter(ImageFilter.GaussianBlur(radius=12))
    image.save(source)
    scene = {
        "scene_role": "character_reference",
        "scene_id": "edith_reference_front",
    }

    technical = _probe_image_quality(str(source), scene=scene)

    assert "blurry_image" in technical["issues"]


def test_edith_relative_age_requirement_is_not_mapped_to_alice():
    requirement = "younger and shorter than Alice"

    assert (
        _local_required_visual_code(requirement, 2)
        == "cast_identity_proportions_mismatch"
    )
    assert "body-age contract" in _local_required_visual_question(requirement)


def test_animal_full_body_requirement_uses_species_specific_question():
    requirement = (
        "full-body turnaround, head to both feet, complete species-correct body "
        "and natural paws or feet with no human hands or shoes"
    )

    question = _local_required_visual_question(requirement)

    assert "complete animal" in question
    assert "shoes" not in question


def test_character_reference_excludes_relative_height_comparison():
    visual_bible = {
        "style_prompt": "premium comic storybook",
        "cast_bible": {
            "characters": [
                {
                    "id": "edith",
                    "name": "Edith",
                    "kind": "human",
                    "identity_prompt": "Edith, approximately 7 years old",
                    "must_include": [
                        "exactly one Edith approximately 7 years old",
                        "younger and shorter than Alice",
                        "light brown curled hair",
                        "dusty rose Victorian child dress",
                        "plain neutral backdrop",
                    ],
                    "must_not_include": ["second Edith", "adult Edith"],
                }
            ]
        },
    }

    scene = _build_character_reference_scene(
        visual_bible,
        "edith",
        "expression_neutral",
    )

    assert "exactly one Edith approximately 7 years old" in scene["must_include"]
    assert "younger and shorter than Alice" not in scene["must_include"]


def test_human_expression_reference_forbids_new_facial_marks():
    visual_bible = {
        "style_prompt": "premium comic storybook",
        "cast_bible": {
            "characters": [
                {
                    "id": "lori",
                    "name": "Lori",
                    "kind": "human",
                    "identity_prompt": "adolescent sister with pinned hair",
                    "must_include": [
                        "exactly one adolescent Lori",
                        "dark chestnut hair pinned back",
                        "muted sage Victorian day dress",
                        "plain neutral backdrop",
                    ],
                    "must_not_include": ["second Lori", "modern clothing"],
                }
            ]
        },
    }

    scene = _build_character_reference_scene(
        visual_bible,
        "lori",
        "expression_warm",
    )

    assert "face occupies at least 40 percent" in scene["must_include"][0]
    assert (
        "new isolated mole, beauty mark or dark facial spot"
        in scene["must_not_include"]
    )


def test_required_production_cast_includes_recurring_offscreen_characters(
    monkeypatch,
):
    monkeypatch.setenv("CAST_BIBLE_RECURRING_MIN_MENTIONS", "2")
    visual_bible = {
        "cast_bible": {
            "characters": [
                {"id": "alice", "name": "Alice", "story_mentions": 2},
                {"id": "lori", "name": "Lori", "story_mentions": 6},
                {"id": "cameo", "name": "Cameo", "story_mentions": 1},
            ]
        }
    }
    scenes = [{"scene_id": 1, "cast_character_ids": ["alice"]}]
    monkeypatch.setattr(
        langgraph_adapter,
        "_scene_cast_characters",
        lambda scene, bible: [bible["cast_bible"]["characters"][0]],
    )

    required = _required_production_cast(scenes, visual_bible)

    assert [character["id"] for character in required] == ["alice", "lori"]
    assert visual_bible["cast_bible"]["required_for_scenes"] == ["alice"]
    assert visual_bible["cast_bible"]["required_for_production"] == [
        "alice",
        "lori",
    ]


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


def _gate_test_image_metric(semantic_score=96):
    return {
        "scene_id": 1,
        "quality_score": 96,
        "technical_score": 100,
        "technical_accepted": True,
        "semantic_score": semantic_score,
        "semantic_accepted": True,
        "style_score": 96,
        "style_accepted": True,
        "hero_objects": [],
        "hero_object_legibility": None,
        "character_identity": [],
        "cast_reference_versions": {},
        "issues": [],
    }


def _gate_test_summary(tmp_path, semantic_score=96, review_status="pending_review"):
    image = tmp_path / "scene.png"
    image.write_bytes(b"image" * 300)
    metric = _gate_test_image_metric(semantic_score)
    attempt = {
        "id": "attempt_1",
        "status": "approved" if review_status == "approved" else "active",
        "image_path": str(image),
        "image_provider": "comfyui_flux2_klein",
        "image_quality_score": 96,
        "image_semantic_score": semantic_score,
        "image_semantic_accepted": True,
        "image_job": metric,
    }
    return {
        "scenes_count": 1,
        "scenes": [{"scene_id": 1, "description": "A quiet landscape."}],
        "scene_images": [
            {
                "scene_id": 1,
                "image_path": str(image),
                "generation_method": "comfyui_flux2_klein",
            }
        ],
        "visual_bible": {
            "cast_bible": {
                "schema_version": CAST_BIBLE_SCHEMA_VERSION,
                "revision": "cast-no-recurring-characters",
                "status": "empty",
                "characters": [],
                "required_for_scenes": [],
            }
        },
        "quality_metrics": {"images": [metric]},
        "curation": {
            "scenes": {
                "1": {
                    "status": review_status,
                    "active_attempt_id": "attempt_1",
                    "approved_attempt_id": (
                        "attempt_1" if review_status == "approved" else None
                    ),
                    "attempts": [attempt],
                }
            },
            "final_review": {"status": "draft", "video_viewed": False},
        },
    }


def test_automatic_gate_keeps_technical_100_separate_from_semantic_79(tmp_path):
    summary = _gate_test_summary(tmp_path, semantic_score=79)
    attempt = summary["curation"]["scenes"]["1"]["attempts"][0]

    gate = ui_server._attempt_automatic_gate(summary, "1", attempt)

    assert gate["passed"] is False
    assert gate["gates"]["technical"] == {"score": 100.0, "passed": True}
    assert gate["gates"]["semantic"] == {"score": 79.0, "passed": False}
    assert gate["blockers"] == ["semantic"]


def test_human_curation_cannot_approve_automatic_gate_failure(tmp_path):
    run_id = "blocked-human-approval"
    summary = _gate_test_summary(tmp_path, semantic_score=79)
    ui_server.RUNS[run_id] = {
        "id": run_id,
        "status": "completed",
        "run_dir": str(tmp_path),
        "summary": summary,
    }
    try:
        response = ui_server.app.test_client().post(
            f"/api/runs/{run_id}/curation",
            json={
                "scene_id": "1",
                "status": "approved",
                "attempt_id": "attempt_1",
            },
        )
    finally:
        ui_server.RUNS.pop(run_id, None)

    assert response.status_code == 409
    assert response.get_json()["blockers"] == ["semantic"]


def test_existing_human_approval_is_revoked_when_automatic_gate_fails(tmp_path):
    summary = _gate_test_summary(tmp_path, semantic_score=79, review_status="approved")

    result = ui_server._apply_curation_summary(summary, tmp_path)
    review = result["curation"]["scenes"]["1"]

    assert review["status"] == "automatic_gate_blocked"
    assert review["approved_attempt_id"] is None
    assert result["curation"]["can_generate_video"] is False


def test_final_compilation_requires_temporal_identity_approved(tmp_path):
    summary = _gate_test_summary(tmp_path, review_status="approved")
    attempt = summary["curation"]["scenes"]["1"]["attempts"][0]
    clip = tmp_path / "scene.mp4"
    clip.write_bytes(b"video" * 300)
    attempt.update(
        {
            "video_path": str(clip),
            "video_provider": "runway",
            "temporal_identity": {"accepted": False, "score": 75},
        }
    )
    run = {"run_dir": str(tmp_path), "summary": summary}

    with pytest.raises(RuntimeError, match="temporal_identity_gate_blocked:1"):
        ui_server._recompile_final_video_from_attempts(run)


def test_ui_exposes_separate_workspaces_cast_bible_and_gate_matrix():
    html = ui_server.INDEX_HTML

    assert "setWorkspaceTab('curation')" in html
    assert "setWorkspaceTab('operation')" in html
    assert "setWorkspaceTab('media')" in html
    assert "referências multipose bloqueantes" in html
    assert "reference_version: 'Referência'" in html
    assert "Gerar animação real" in html
    assert "gates visuais" in html


def test_failed_youtube_upload_is_retryable_after_final_gate(monkeypatch, tmp_path):
    _mock_valid_video_probe(monkeypatch)
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"final-video")
    summary = {
        "video_path": str(video_path),
        "video_exists": True,
        "visual_bible": {
            "cast_bible": {
                "schema_version": CAST_BIBLE_SCHEMA_VERSION,
                "revision": "cast-test",
                "characters": [],
                "required_for_scenes": [],
            }
        },
        "publication": {"status": "failed", "error": "temporary provider error"},
        "curation": {"final_review": {"status": "final_approved"}},
    }

    production = ui_server._apply_production_status(summary, tmp_path, [])

    assert production["status"] == "ready_to_publish"
    assert production["publication_retry_available"] is True


def test_cost_quota_blocks_publish_when_run_cost_exceeds_limit(monkeypatch, tmp_path):
    _mock_valid_video_probe(monkeypatch)
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


def test_published_status_is_stale_when_current_video_hash_changes(
    monkeypatch, tmp_path
):
    _mock_valid_video_probe(monkeypatch)
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


def test_missing_semantic_scene_blocks_final_approval_and_publication(
    monkeypatch, tmp_path
):
    _mock_valid_video_probe(monkeypatch)
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


def test_video_probe_requires_a_decodable_video_stream(monkeypatch, tmp_path):
    video = tmp_path / "corrupt.mp4"
    video.write_bytes(b"not-a-video")
    monkeypatch.setattr(
        ui_server.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="moov atom not found",
        ),
    )

    artifact = ui_server._probe_video_artifact(video)

    assert artifact["exists"] is True
    assert artifact["valid"] is False
    assert artifact["first_frame_decoded"] is False
    assert artifact["stream_decoded"] is False
    assert artifact["issues"] == ["ffprobe_failed"]


def test_video_probe_accepts_metadata_and_first_frame_decode(monkeypatch, tmp_path):
    video = tmp_path / "valid.mp4"
    video.write_bytes(b"video-container")
    calls = iter(
        [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "streams": [
                            {
                                "codec_name": "h264",
                                "width": 1080,
                                "height": 1920,
                                "nb_read_frames": "60",
                            }
                        ],
                        "format": {"duration": "2.0", "size": "15"},
                    }
                ),
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        ]
    )
    monkeypatch.setattr(
        ui_server.subprocess,
        "run",
        lambda *args, **kwargs: next(calls),
    )

    artifact = ui_server._probe_video_artifact(video)

    assert artifact["valid"] is True
    assert artifact["first_frame_decoded"] is True
    assert artifact["stream_decoded"] is True
    assert artifact["frame_count"] == 60
    assert artifact["duration_seconds"] == 2.0


def test_corrupt_video_revokes_final_approval(monkeypatch, tmp_path):
    video = tmp_path / "output" / "final_video.mp4"
    video.parent.mkdir()
    video.write_bytes(b"corrupt-video")
    image = tmp_path / "scene.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(
        ui_server,
        "_probe_video_artifact",
        lambda path: {
            "exists": True,
            "valid": False,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "mtime": path.stat().st_mtime,
            "duration_seconds": 0.0,
            "frame_count": 0,
            "first_frame_decoded": False,
            "issues": ["ffprobe_failed"],
        },
    )
    summary = {
        "video_path": str(video),
        "video_exists": True,
        "visual_bible": {
            "cast_bible": {
                "schema_version": CAST_BIBLE_SCHEMA_VERSION,
                "revision": "cast-video-probe",
                "characters": [],
                "required_for_scenes": [],
            }
        },
        "scenes": [{"scene_id": 1}],
        "scenes_count": 1,
        "scene_images": [
            {
                "scene_id": 1,
                "image_path": str(image),
                "generation_method": "comfyui",
            }
        ],
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 1,
                    "semantic_accepted": True,
                    "semantic_score": 100,
                    "technical_accepted": True,
                    "technical_score": 100,
                    "style_accepted": True,
                    "style_score": 100,
                }
            ]
        },
        "curation": {
            "scenes": {"1": {"status": "approved", "attempts": []}},
            "final_review": {
                "status": "final_approved",
                "video_viewed": True,
            },
        },
    }

    result = ui_server._apply_curation_summary(summary, tmp_path)

    assert result["video_valid"] is False
    assert result["curation"]["final_review"]["status"] == "video_review_blocked"
    assert result["production_status"]["status"] == "blocked"
    assert result["curation"]["can_publish"] is False
    assert any(
        "vídeo final inválido ou corrompido" in blocker
        for blocker in result["curation"]["blockers"]
    )


def test_cast_bible_missing_reference_blocks_visual_approval(monkeypatch, tmp_path):
    _mock_valid_video_probe(monkeypatch)
    video = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    image = tmp_path / "scene.png"
    image.write_bytes(b"image")
    visual_bible = _build_visual_bible(
        "Alice conversa com Ludovico. Ludovico responde a Alice.",
        "comic_storybook",
    )
    visual_bible["cast_bible"]["required_for_scenes"] = ["alice", "ludovico"]
    summary = {
        "video_path": str(video),
        "scenes": [{"scene_id": 1}],
        "scenes_count": 1,
        "scene_images": [
            {
                "scene_id": 1,
                "image_path": str(image),
                "generation_method": "comfyui",
            }
        ],
        "visual_bible": visual_bible,
        "quality_metrics": {
            "images": [
                {
                    "scene_id": 1,
                    "semantic_accepted": True,
                    "technical_accepted": True,
                }
            ]
        },
        "curation": {
            "scenes": {"1": {"status": "approved", "attempts": []}},
            "final_review": {"status": "draft", "video_viewed": True},
        },
    }

    result = ui_server._apply_curation_summary(summary, tmp_path)

    assert result["curation"]["quality_gate_status"] == "blocked"
    assert result["curation"]["can_final_approve"] is False
    assert any(
        "Cast Bible sem referência aprovada: Alice, Professor Ludovico" in blocker
        for blocker in result["curation"]["quality_blockers"]
    )


def test_invalid_video_cannot_be_marked_as_viewed(monkeypatch, tmp_path):
    run_id = "invalid-video-test"
    video = tmp_path / "final.mp4"
    video.write_bytes(b"corrupt")
    monkeypatch.setattr(
        ui_server,
        "_probe_video_artifact",
        lambda path: {
            "exists": True,
            "valid": False,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "mtime": path.stat().st_mtime,
            "issues": ["ffprobe_failed"],
        },
    )
    ui_server.RUNS[run_id] = {
        "id": run_id,
        "run_dir": str(tmp_path),
        "summary": {"video_path": str(video), "curation": {}},
    }
    try:
        response = ui_server.app.test_client().post(
            f"/api/runs/{run_id}/final-video-viewed"
        )
    finally:
        ui_server.RUNS.pop(run_id, None)

    assert response.status_code == 409
    assert response.get_json()["issues"] == ["ffprobe_failed"]
