#!/usr/bin/env python3
"""Validate the production FLUX -> Qwen -> controlled SDXL repair route."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN3D_ROOT = REPO_ROOT / "open3d_implementation"
OUTPUT_ROOT = REPO_ROOT / "data" / "outputs" / "staged_semantic_repair"
REPORT_PATH = OUTPUT_ROOT / "report.json"
QA_REPORT_PATH = OUTPUT_ROOT / "qa_report.json"
QWEN_CANARY_REPORT_PATH = OUTPUT_ROOT / "qwen_canary_report.json"
QWEN_INPAINT_CANARY_REPORT_PATH = OUTPUT_ROOT / "qwen_inpaint_canary_report.json"
QWEN_STAGED_CANARY_REPORT_PATH = OUTPUT_ROOT / "qwen_staged_canary_report.json"
SDXL_IPADAPTER_CANARY_REPORT_PATH = OUTPUT_ROOT / "sdxl_ipadapter_canary_report.json"
PROP_REFERENCE_REPORT_PATH = OUTPUT_ROOT / "prop_reference_report.json"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(OPEN3D_ROOT))

from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    _build_character_reference_scene,
    _build_flux2_image_prompt,
    _build_image_prompt,
    _character_reference_accepted,
    _combine_image_quality,
    _comfyui_ipadapter_enabled,
    _evaluate_image_semantics,
    _non_retryable_comfyui_job_error,
    _probe_image_quality,
    _resolve_comfyui_checkpoint,
    _resolve_quality_preset,
    _run_comfyui_image_attempt,
    _select_comfyui_retry_route,
    _semantic_retry_instruction,
)

STYLE_KEY = "comic_storybook"
STYLE_LABEL = "Original premium comic storybook animation"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing_env:{name}")
    return value


def _visual_bible() -> dict[str, Any]:
    return {
        "style_label": STYLE_LABEL,
        "style_prompt": (
            "premium hand-drawn comic storybook animation, clean expressive "
            "linework, natural child proportions, warm restrained palette"
        ),
        "protagonist_identity": (
            "Alice is exactly one ten-year-old Victorian child with a round "
            "preteen face, shoulder-length chestnut-brown hair, no makeup, and "
            "a modest ivory long-sleeved day dress"
        ),
    }


def _semantic_scene() -> dict[str, Any]:
    return {
        "scene_id": 2,
        "description": (
            "Alice, uma única menina vitoriana de dez anos, e o professor "
            "Ludovico observam um pequeno ratinho branco natural surgindo de "
            "um açucareiro de porcelana aberto sobre a mesa de chá."
        ),
        "prompt": (
            "one child Alice and adult male professor Ludovico beside a "
            "Victorian tea table, tiny white mouse peeking over a handleless "
            "porcelain sugar bowl rim"
        ),
        "must_include": [
            "exactly one unmistakably preteen ten-year-old child Alice",
            "exactly one adult male professor Ludovico around 50 years old",
            "one compact 12-centimeter porcelain sugar bowl without handles",
            "one separate sugar bowl lid lying flat beside the bowl",
            "one normal teaspoon proving the sugar bowl scale",
            "one tiny natural white mouse with only head and paws above the rim",
        ],
        "must_not_include": [
            "adult Alice",
            "teenage Alice",
            "second Alice",
            "duplicate people",
            "woman replacing Ludovico",
            "cup handle",
            "teacup",
            "serving bowl",
            "oversized mouse",
            "anthropomorphic mouse",
            "visible text",
            "watermark",
        ],
        "inpaint_focus_boxes": [[0.57, 0.68, 0.94, 0.92]],
    }


def _prop_reference_scene() -> dict[str, Any]:
    return {
        "scene_id": "prop_reference",
        "scene_role": "prop_reference",
        "description": (
            "A clean isolated design reference of one compact handleless "
            "Victorian porcelain sugar bowl, its separate lid, one normal "
            "teaspoon and one tiny natural white mouse peeking from inside."
        ),
        "prompt": (
            "isolated tabletop prop design reference, compact 12-centimeter "
            "handleless porcelain sugar bowl, separate matching lid, normal "
            "teaspoon, tiny natural white mouse with only head and front paws "
            "above the rim, neutral warm-gray background"
        ),
        "must_include": [
            "exactly one compact 12-centimeter handleless porcelain sugar bowl",
            "exactly one separate matching sugar bowl lid lying flat",
            "exactly one normal teaspoon lying beside the bowl to prove scale",
            "one tiny natural white mouse with only head and front paws above the rim",
        ],
        "must_not_include": [
            "human",
            "hand",
            "Alice",
            "Ludovico",
            "teacup",
            "cup handle",
            "serving bowl",
            "tureen",
            "second bowl",
            "second lid",
            "duplicate lid",
            "saucer",
            "plate",
            "spoon inside the bowl",
            "oversized mouse",
            "full mouse body",
            "mouse torso above the rim",
            "text",
            "watermark",
        ],
    }


def _stage_payload(
    *,
    name: str,
    monitor: dict[str, Any],
    metric: dict[str, Any] | None,
    path: Path,
) -> dict[str, Any]:
    return {
        "stage": name,
        "job_id": monitor.get("job_id"),
        "status": monitor.get("status"),
        "error": monitor.get("error"),
        "elapsed_seconds": monitor.get("elapsed_seconds"),
        "queue_seconds": monitor.get("queue_seconds"),
        "execution_seconds": monitor.get("execution_seconds"),
        "estimated_cost_usd": monitor.get("estimated_cost_usd"),
        "cost_estimate_status": monitor.get("cost_estimate_status"),
        "last_remote_status": monitor.get("last_remote_status"),
        "generation_method": monitor.get("generation_method"),
        "path": str(path),
        "exists": path.is_file() and path.stat().st_size > 1000,
        "technical_score": (metric or {}).get("technical_score"),
        "semantic_score": (metric or {}).get("semantic_score"),
        "semantic_accepted": (metric or {}).get("semantic_accepted", False),
        "semantic_qa_provider": (metric or {}).get("semantic_qa_provider"),
        "semantic_qa_model": (metric or {}).get("semantic_qa_model"),
        "semantic_qa_error": (metric or {}).get("semantic_qa_error")
        or (metric or {}).get("error"),
        "issues": (metric or {}).get("issues", []),
        "recommended_generation_strategy": (metric or {}).get(
            "recommended_generation_strategy"
        ),
    }


def _stage_report_status(accepted: bool, stage: dict[str, Any]) -> str:
    if accepted:
        return "accepted"
    if (
        stage.get("status") == "LOCAL_TIMEOUT"
        and stage.get("last_remote_status") == "IN_QUEUE"
    ):
        return "blocked_infrastructure_capacity"
    if not stage.get("exists") or stage.get("technical_score") is None:
        return "blocked_generation"
    return "blocked_semantic_gate"


def _stage_approved_prop_on_scene(
    *,
    scene_path: Path,
    prop_reference_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Place an approved prop deterministically before low-denoise harmonization."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps

    with Image.open(scene_path) as scene_image:
        scene = scene_image.convert("RGB")
    with Image.open(prop_reference_path) as prop_image:
        prop = prop_image.convert("RGB")

    prop_crop_box = (
        int(prop.width * 0.17),
        int(prop.height * 0.38),
        int(prop.width * 0.555),
        int(prop.height * 0.70),
    )
    crop = prop.crop(prop_crop_box)
    target_box = (
        int(scene.width * 0.59),
        int(scene.height * 0.70),
        int(scene.width * 0.92),
        int(scene.height * 0.90),
    )
    target_size = (
        target_box[2] - target_box[0],
        target_box[3] - target_box[1],
    )
    corner_colors = (
        crop.getpixel((0, 0)),
        crop.getpixel((crop.width - 1, 0)),
        crop.getpixel((0, crop.height - 1)),
        crop.getpixel((crop.width - 1, crop.height - 1)),
    )
    background_color = tuple(
        sum(color[channel] for color in corner_colors) // len(corner_colors)
        for channel in range(3)
    )
    staged_prop = Image.new("RGB", target_size, background_color)
    contained_prop = ImageOps.contain(
        crop,
        (
            int(target_size[0] * 0.58),
            int(target_size[1] * 0.78),
        ),
        method=Image.Resampling.LANCZOS,
    )
    staged_prop.paste(
        contained_prop,
        (
            (target_size[0] - contained_prop.width) // 2,
            (target_size[1] - contained_prop.height) // 2,
        ),
    )
    edge_mask = Image.new("L", target_size, 0)
    edge_draw = ImageDraw.Draw(edge_mask)
    inset = max(3, min(target_size) // 35)
    edge_draw.rounded_rectangle(
        (inset, inset, target_size[0] - inset, target_size[1] - inset),
        radius=max(12, min(target_size) // 12),
        fill=255,
    )
    edge_mask = edge_mask.filter(
        ImageFilter.GaussianBlur(radius=max(3, min(target_size) // 45))
    )
    scene.paste(staged_prop, target_box[:2], edge_mask)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.save(output_path, format="PNG", optimize=True)
    return {
        "source_path": str(scene_path),
        "prop_reference_path": str(prop_reference_path),
        "output_path": str(output_path),
        "prop_crop_box": prop_crop_box,
        "target_box": target_box,
    }


def _write_report(
    report: dict[str, Any],
    report_path: Path = REPORT_PATH,
) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse the approved reference and rejected FLUX base from the last report.",
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Re-run technical and semantic QA on existing images without RunPod.",
    )
    parser.add_argument(
        "--qwen-canary",
        action="store_true",
        help=(
            "Run one corrected Qwen edit from attempt 1 and the approved Alice "
            "reference, then stop."
        ),
    )
    parser.add_argument(
        "--qwen-inpaint-canary",
        action="store_true",
        help=(
            "Run one masked Qwen edit over only the failed hero objects from "
            "attempt 5."
        ),
    )
    parser.add_argument(
        "--qwen-staged-canary",
        action="store_true",
        help=(
            "Stage the approved prop deterministically, then run one low-denoise "
            "masked Qwen harmonization."
        ),
    )
    parser.add_argument(
        "--sdxl-ipadapter-canary",
        action="store_true",
        help=(
            "Run one precise masked SDXL repair using the approved prop as an "
            "IPAdapter composition reference."
        ),
    )
    parser.add_argument(
        "--prop-reference-canary",
        action="store_true",
        help="Generate and gate one isolated sugar-bowl and mouse reference.",
    )
    parser.add_argument(
        "--evaluate-prop-reference",
        action="store_true",
        help="Gate the existing prop reference without starting a RunPod worker.",
    )
    args = parser.parse_args()
    load_dotenv(OPEN3D_ROOT / ".env", override=False)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    visual_bible = _visual_bible()

    if args.evaluate_only:
        scene = _semantic_scene()
        evaluations = []
        for attempt in range(1, 5):
            image_path = OUTPUT_ROOT / f"scene_2_attempt_{attempt}.png"
            if not image_path.is_file():
                continue
            technical = _probe_image_quality(str(image_path), scene=scene)
            semantic = _evaluate_image_semantics(
                str(image_path),
                scene,
                str(scene["prompt"]),
                STYLE_KEY,
                visual_bible,
            )
            quality_metrics = _combine_image_quality(technical, semantic)
            evaluations.append(
                {
                    "attempt": attempt,
                    "path": str(image_path),
                    "technical_score": quality_metrics.get("technical_score"),
                    "semantic_score": quality_metrics.get("semantic_score"),
                    "semantic_accepted": quality_metrics.get("semantic_accepted"),
                    "semantic_qa_provider": quality_metrics.get("semantic_qa_provider"),
                    "semantic_qa_model": quality_metrics.get("semantic_qa_model"),
                    "semantic_qa_fallback_used": quality_metrics.get(
                        "semantic_qa_fallback_used", False
                    ),
                    "semantic_qa_provider_warnings": quality_metrics.get(
                        "semantic_qa_provider_warnings", []
                    ),
                    "issues": quality_metrics.get("issues", []),
                    "semantic_qa_error": quality_metrics.get("semantic_qa_error"),
                    "recommended_generation_strategy": quality_metrics.get(
                        "recommended_generation_strategy"
                    ),
                }
            )
        qa_report = {"status": "evaluated", "evaluations": evaluations}
        QA_REPORT_PATH.write_text(
            json.dumps(qa_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(qa_report, ensure_ascii=False, indent=2))
        return 0

    if args.evaluate_prop_reference:
        prop_scene = _prop_reference_scene()
        prop_reference_path = OUTPUT_ROOT / "hero_prop_reference.png"
        if (
            not prop_reference_path.is_file()
            or prop_reference_path.stat().st_size <= 1000
        ):
            raise RuntimeError("prop_reference_missing")
        prop_visual_bible = {
            "style_label": STYLE_LABEL,
            "style_prompt": visual_bible["style_prompt"],
        }
        technical = _probe_image_quality(
            str(prop_reference_path),
            scene=prop_scene,
        )
        semantic = _evaluate_image_semantics(
            str(prop_reference_path),
            prop_scene,
            str(prop_scene["prompt"]),
            STYLE_KEY,
            prop_visual_bible,
        )
        metric = _combine_image_quality(technical, semantic)
        stage = _stage_payload(
            name="hero_prop_reference_local_evaluation",
            monitor={
                "status": "EVALUATED",
                "elapsed_seconds": 0.0,
                "estimated_cost_usd": 0.0,
                "generation_method": "curated_reference",
            },
            metric=metric,
            path=prop_reference_path,
        )
        accepted = bool(metric.get("semantic_accepted"))
        report = {
            "status": _stage_report_status(accepted, stage),
            "accepted": accepted,
            "semantic_threshold": int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88")),
            "stages": [stage],
            "total_estimated_cost_usd": 0.0,
        }
        _write_report(report, PROP_REFERENCE_REPORT_PATH)
        return 0 if accepted else 1

    endpoint_id = _required_env("RUNPOD_ENDPOINT_ID")
    api_key = _required_env("RUNPOD_API_KEY")
    quality = _resolve_quality_preset("high")
    checkpoint = _resolve_comfyui_checkpoint(STYLE_KEY)
    gpu_rate = float(os.getenv("RUNPOD_GPU_USD_PER_SECOND", "0.000553"))
    stages: list[dict[str, Any]] = []

    if args.qwen_canary:
        scene = _semantic_scene()
        source_path = OUTPUT_ROOT / "scene_2_attempt_1.png"
        reference_path = OUTPUT_ROOT / "alice_character_reference.png"
        if not source_path.is_file() or source_path.stat().st_size <= 1000:
            raise RuntimeError("qwen_canary_source_missing")
        if not reference_path.is_file() or reference_path.stat().st_size <= 1000:
            raise RuntimeError("qwen_canary_reference_missing")

        visual_bible["character_reference_image_path"] = str(reference_path)
        correction = (
            "Keep the approved portrait canvas and scene blocking. Replace the "
            "young woman with the exact ten-year-old Alice from image 2. Shrink "
            "the sugar bowl to one adult hand-span and show only the tiny mouse "
            "head and front paws above its rim. Keep the lid and teaspoon beside "
            "the bowl as scale references."
        )
        prompt = _build_flux2_image_prompt(
            scene,
            STYLE_KEY,
            visual_bible,
            correction,
        )
        output_path = OUTPUT_ROOT / "scene_2_attempt_5.png"
        monitor, _record, metric = _run_comfyui_image_attempt(
            scene=scene,
            image_path=str(output_path),
            directed_prompt=prompt,
            image_style=STYLE_KEY,
            style_label=STYLE_LABEL,
            quality_preset_key="high",
            quality_preset=quality,
            checkpoint_name=checkpoint,
            scene_seed=2026071815,
            visual_bible=visual_bible,
            runpod_endpoint_id=endpoint_id,
            runpod_api_key=api_key,
            runpod_gpu_usd_per_second=gpu_rate,
            attempt=5,
            controlled_workflow=True,
            control_strategy="controlled_inpaint",
            control_image_path=str(source_path),
            reference_image_path=str(reference_path),
            semantic_repair_backend_override="qwen_image_edit_2511",
        )
        stage = _stage_payload(
            name="scene_attempt_5_qwen_portrait_canary",
            monitor=monitor,
            metric=metric,
            path=output_path,
        )
        accepted = bool(metric and metric.get("semantic_accepted"))
        report = {
            "status": _stage_report_status(accepted, stage),
            "accepted": accepted,
            "semantic_threshold": int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88")),
            "source_path": str(source_path),
            "reference_path": str(reference_path),
            "stages": [stage],
            "total_estimated_cost_usd": float(stage.get("estimated_cost_usd") or 0),
        }
        _write_report(report, QWEN_CANARY_REPORT_PATH)
        return 0 if accepted else 1

    if args.prop_reference_canary:
        prop_scene = _prop_reference_scene()
        prop_visual_bible = {
            "style_label": STYLE_LABEL,
            "style_prompt": visual_bible["style_prompt"],
        }
        prompt = _build_flux2_image_prompt(
            prop_scene,
            STYLE_KEY,
            prop_visual_bible,
            (
                "This is an isolated approved prop design sheet, not a story "
                "scene. Use a neutral background and show no human or hand. "
                "Exactly one bowl, one separate lid and one teaspoon are visible; "
                "the teaspoon lies beside the bowl. Never add a saucer, plate, "
                "second lid or second bowl. Hide the mouse torso inside the bowl."
            ),
        )
        output_path = OUTPUT_ROOT / "hero_prop_reference.png"
        monitor, _record, metric = _run_comfyui_image_attempt(
            scene=prop_scene,
            image_path=str(output_path),
            directed_prompt=prompt,
            image_style=STYLE_KEY,
            style_label=STYLE_LABEL,
            quality_preset_key="high",
            quality_preset=quality,
            checkpoint_name=checkpoint,
            scene_seed=2026071817,
            visual_bible=prop_visual_bible,
            runpod_endpoint_id=endpoint_id,
            runpod_api_key=api_key,
            runpod_gpu_usd_per_second=gpu_rate,
            attempt=0,
        )
        stage = _stage_payload(
            name="hero_prop_reference",
            monitor=monitor,
            metric=metric,
            path=output_path,
        )
        accepted = bool(metric and metric.get("semantic_accepted"))
        report = {
            "status": _stage_report_status(accepted, stage),
            "accepted": accepted,
            "semantic_threshold": int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88")),
            "stages": [stage],
            "total_estimated_cost_usd": float(stage.get("estimated_cost_usd") or 0),
        }
        _write_report(report, PROP_REFERENCE_REPORT_PATH)
        return 0 if accepted else 1

    if args.qwen_inpaint_canary:
        scene = _semantic_scene()
        source_path = OUTPUT_ROOT / "scene_2_attempt_5.png"
        prop_reference_path = OUTPUT_ROOT / "hero_prop_reference.png"
        if not source_path.is_file() or source_path.stat().st_size <= 1000:
            raise RuntimeError("qwen_inpaint_canary_source_missing")
        if (
            not prop_reference_path.is_file()
            or prop_reference_path.stat().st_size <= 1000
        ):
            raise RuntimeError("qwen_inpaint_canary_prop_reference_missing")
        if not PROP_REFERENCE_REPORT_PATH.is_file():
            raise RuntimeError("qwen_inpaint_canary_prop_report_missing")
        try:
            prop_report = json.loads(
                PROP_REFERENCE_REPORT_PATH.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("qwen_inpaint_canary_prop_report_invalid") from exc
        if not bool(prop_report.get("accepted")):
            raise RuntimeError("qwen_inpaint_canary_prop_reference_not_approved")

        correction = (
            "Edit only the masked tabletop props. Replace the oversized serving "
            "bowl with one compact handleless 12-centimeter porcelain sugar bowl, "
            "about one adult hand-span wide. Hide the mouse body inside it and show "
            "only a tiny natural white head and two front paws above the rim. Keep "
            "one separate lid and one normal teaspoon beside the bowl. Preserve all "
            "unmasked pixels, especially Alice, Ludovico, their hands, the library, "
            "camera, lighting and portrait frame. Copy prop geometry only from "
            "image 2, not its background or framing."
        )
        prompt = _build_flux2_image_prompt(
            scene,
            STYLE_KEY,
            visual_bible,
            correction,
        )
        output_path = OUTPUT_ROOT / "scene_2_attempt_8.png"
        monitor, _record, metric = _run_comfyui_image_attempt(
            scene=scene,
            image_path=str(output_path),
            directed_prompt=prompt,
            image_style=STYLE_KEY,
            style_label=STYLE_LABEL,
            quality_preset_key="high",
            quality_preset=quality,
            checkpoint_name=checkpoint,
            scene_seed=2026071818,
            visual_bible=visual_bible,
            runpod_endpoint_id=endpoint_id,
            runpod_api_key=api_key,
            runpod_gpu_usd_per_second=gpu_rate,
            attempt=8,
            controlled_workflow=True,
            control_strategy="masked_inpaint",
            control_image_path=str(source_path),
            reference_image_path=None,
            prop_reference_image_path=str(prop_reference_path),
            semantic_repair_backend_override="qwen_image_edit_2511",
        )
        stage = _stage_payload(
            name="scene_attempt_8_qwen_official_conditioning_repair",
            monitor=monitor,
            metric=metric,
            path=output_path,
        )
        accepted = bool(metric and metric.get("semantic_accepted"))
        report = {
            "status": _stage_report_status(accepted, stage),
            "accepted": accepted,
            "semantic_threshold": int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88")),
            "source_path": str(source_path),
            "character_reference_path": None,
            "prop_reference_path": str(prop_reference_path),
            "stages": [stage],
            "total_estimated_cost_usd": float(stage.get("estimated_cost_usd") or 0),
        }
        _write_report(report, QWEN_INPAINT_CANARY_REPORT_PATH)
        return 0 if accepted else 1

    if args.qwen_staged_canary:
        scene = _semantic_scene()
        source_path = OUTPUT_ROOT / "scene_2_attempt_8.png"
        prop_reference_path = OUTPUT_ROOT / "hero_prop_reference.png"
        staged_input_path = OUTPUT_ROOT / "scene_2_attempt_9_staged_input.png"
        output_path = OUTPUT_ROOT / "scene_2_attempt_9.png"
        if not source_path.is_file() or source_path.stat().st_size <= 1000:
            raise RuntimeError("qwen_staged_canary_source_missing")
        if (
            not prop_reference_path.is_file()
            or prop_reference_path.stat().st_size <= 1000
        ):
            raise RuntimeError("qwen_staged_canary_prop_reference_missing")
        prop_report = json.loads(PROP_REFERENCE_REPORT_PATH.read_text(encoding="utf-8"))
        if not bool(prop_report.get("accepted")):
            raise RuntimeError("qwen_staged_canary_prop_reference_not_approved")

        placement = _stage_approved_prop_on_scene(
            scene_path=source_path,
            prop_reference_path=prop_reference_path,
            output_path=staged_input_path,
        )
        staged_technical = _probe_image_quality(str(staged_input_path), scene=scene)
        staged_semantic = _evaluate_image_semantics(
            str(staged_input_path),
            scene,
            str(scene["prompt"]),
            STYLE_KEY,
            visual_bible,
        )
        staged_metric = _combine_image_quality(staged_technical, staged_semantic)
        staged_stage = {
            "stage": "scene_attempt_9_deterministic_prop_stage",
            "job_id": None,
            "status": "COMPLETED_LOCAL",
            "error": None,
            "elapsed_seconds": 0.0,
            "queue_seconds": 0.0,
            "execution_seconds": 0.0,
            "estimated_cost_usd": 0.0,
            "cost_estimate_status": "local_no_gpu",
            "last_remote_status": None,
            "generation_method": "deterministic_prop_stage",
            "path": str(staged_input_path),
            "exists": True,
            "technical_score": staged_metric.get("technical_score"),
            "semantic_score": staged_metric.get("semantic_score"),
            "semantic_accepted": staged_metric.get("semantic_accepted", False),
            "semantic_qa_provider": staged_metric.get("semantic_qa_provider"),
            "semantic_qa_model": staged_metric.get("semantic_qa_model"),
            "semantic_qa_error": staged_metric.get("semantic_qa_error"),
            "issues": staged_metric.get("issues", []),
            "recommended_generation_strategy": staged_metric.get(
                "recommended_generation_strategy"
            ),
            "placement": placement,
        }
        correction = (
            "Harmonize only the masked tabletop patch. Preserve the already staged "
            "approved blue floral sugar bowl, tiny white mouse head and paws, lid "
            "and teaspoon exactly. Remove the rectangular reference background and "
            "blend it into the wooden table without changing any object geometry, "
            "person, camera, lighting or framing."
        )
        prompt = _build_flux2_image_prompt(
            scene,
            STYLE_KEY,
            visual_bible,
            correction,
        )
        monitor, _record, metric = _run_comfyui_image_attempt(
            scene=scene,
            image_path=str(output_path),
            directed_prompt=prompt,
            image_style=STYLE_KEY,
            style_label=STYLE_LABEL,
            quality_preset_key="high",
            quality_preset=quality,
            checkpoint_name=checkpoint,
            scene_seed=2026071819,
            visual_bible=visual_bible,
            runpod_endpoint_id=endpoint_id,
            runpod_api_key=api_key,
            runpod_gpu_usd_per_second=gpu_rate,
            attempt=9,
            controlled_workflow=True,
            control_strategy="masked_inpaint",
            control_image_path=str(staged_input_path),
            reference_image_path=None,
            prop_reference_image_path=str(prop_reference_path),
            semantic_repair_backend_override="qwen_image_edit_2511",
            qwen_inpaint_denoise_override=0.35,
        )
        final_stage = _stage_payload(
            name="scene_attempt_9_qwen_low_denoise_harmonization",
            monitor=monitor,
            metric=metric,
            path=output_path,
        )
        accepted = bool(metric and metric.get("semantic_accepted"))
        stages = [staged_stage, final_stage]
        report = {
            "status": _stage_report_status(accepted, final_stage),
            "accepted": accepted,
            "semantic_threshold": int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88")),
            "stages": stages,
            "total_estimated_cost_usd": round(
                sum(float(stage.get("estimated_cost_usd") or 0) for stage in stages),
                6,
            ),
        }
        _write_report(report, QWEN_STAGED_CANARY_REPORT_PATH)
        return 0 if accepted else 1

    if args.sdxl_ipadapter_canary:
        if not _comfyui_ipadapter_enabled():
            raise RuntimeError("sdxl_ipadapter_canary_requires_ipadapter")
        scene = _semantic_scene()
        source_path = OUTPUT_ROOT / "scene_2_attempt_8.png"
        prop_reference_path = OUTPUT_ROOT / "hero_prop_reference.png"
        output_path = OUTPUT_ROOT / "scene_2_attempt_10.png"
        if not source_path.is_file() or source_path.stat().st_size <= 1000:
            raise RuntimeError("sdxl_ipadapter_canary_source_missing")
        if (
            not prop_reference_path.is_file()
            or prop_reference_path.stat().st_size <= 1000
        ):
            raise RuntimeError("sdxl_ipadapter_canary_prop_reference_missing")
        prop_report = json.loads(PROP_REFERENCE_REPORT_PATH.read_text(encoding="utf-8"))
        if not bool(prop_report.get("accepted")):
            raise RuntimeError("sdxl_ipadapter_canary_prop_reference_not_approved")

        correction = (
            "Inside only the masked tabletop area, insert the approved compact "
            "handleless porcelain sugar bowl, its separate lid, one teaspoon and "
            "a tiny natural white mouse with only its head and front paws above "
            "the rim. Match the exact object geometry and scale from the approved "
            "prop reference. Preserve Alice, Ludovico, the room, camera, lighting "
            "and every unmasked pixel."
        )
        prompt = _build_image_prompt(
            scene,
            STYLE_KEY,
            visual_bible,
            correction,
        )
        monitor, _record, metric = _run_comfyui_image_attempt(
            scene=scene,
            image_path=str(output_path),
            directed_prompt=prompt,
            image_style=STYLE_KEY,
            style_label=STYLE_LABEL,
            quality_preset_key="high",
            quality_preset=quality,
            checkpoint_name=checkpoint,
            scene_seed=2026071820,
            visual_bible=visual_bible,
            runpod_endpoint_id=endpoint_id,
            runpod_api_key=api_key,
            runpod_gpu_usd_per_second=gpu_rate,
            attempt=10,
            controlled_workflow=True,
            control_strategy="masked_inpaint",
            control_image_path=str(source_path),
            reference_image_path=None,
            prop_reference_image_path=str(prop_reference_path),
            semantic_repair_backend_override="sdxl",
        )
        stage = _stage_payload(
            name="scene_attempt_10_sdxl_ipadapter_precise_prop_inpaint",
            monitor=monitor,
            metric=metric,
            path=output_path,
        )
        accepted = bool(metric and metric.get("semantic_accepted"))
        report = {
            "status": _stage_report_status(accepted, stage),
            "accepted": accepted,
            "semantic_threshold": int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88")),
            "source_path": str(source_path),
            "prop_reference_path": str(prop_reference_path),
            "stages": [stage],
            "total_estimated_cost_usd": float(stage.get("estimated_cost_usd") or 0),
        }
        _write_report(report, SDXL_IPADAPTER_CANARY_REPORT_PATH)
        return 0 if accepted else 1

    reference_path = OUTPUT_ROOT / "alice_character_reference.png"
    base_path: Path | None = None
    base_stage: dict[str, Any] = {}
    if args.resume:
        if not REPORT_PATH.is_file():
            raise RuntimeError("resume_report_missing")
        previous_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        prior_stages = previous_report.get("stages", [])
        if len(prior_stages) < 2:
            raise RuntimeError("resume_stages_missing")
        reference_stage = prior_stages[0]
        base_stage = prior_stages[1]
        if not (
            reference_stage.get("semantic_accepted")
            and reference_path.is_file()
            and reference_path.stat().st_size > 1000
        ):
            raise RuntimeError("resume_character_reference_not_approved")
        base_path = Path(str(base_stage.get("path") or ""))
        if not base_path.is_file() or base_path.stat().st_size <= 1000:
            raise RuntimeError("resume_flux_base_missing")
        stages.extend([reference_stage, base_stage])
    else:
        reference_scene = _build_character_reference_scene(visual_bible)
        reference_prompt = _build_flux2_image_prompt(
            reference_scene,
            STYLE_KEY,
            visual_bible,
            (
                "One unmistakably preteen ten-year-old Alice only, neutral full-body "
                "three-quarter pose, plain warm-gray studio background, no props."
            ),
        )
        reference_monitor, _reference_record, reference_metric = (
            _run_comfyui_image_attempt(
                scene=reference_scene,
                image_path=str(reference_path),
                directed_prompt=reference_prompt,
                image_style=STYLE_KEY,
                style_label=STYLE_LABEL,
                quality_preset_key="high",
                quality_preset=quality,
                checkpoint_name=checkpoint,
                scene_seed=2026071801,
                visual_bible=visual_bible,
                runpod_endpoint_id=endpoint_id,
                runpod_api_key=api_key,
                runpod_gpu_usd_per_second=gpu_rate,
                attempt=0,
            )
        )
        stages.append(
            _stage_payload(
                name="character_reference",
                monitor=reference_monitor,
                metric=reference_metric,
                path=reference_path,
            )
        )
        if not _character_reference_accepted(reference_metric):
            report = {
                "status": "blocked_character_reference",
                "accepted": False,
                "stages": stages,
            }
            _write_report(report)
            return 2

    visual_bible["character_reference_image_path"] = str(reference_path)
    scene = _semantic_scene()
    repair_source_path: str | None = str(base_path) if base_path else None
    previous_metric: dict[str, Any] | None = None
    retry_instruction = ""
    start_attempt = 2 if args.resume else 1
    if args.resume:
        previous_metric = {
            "semantic_score": base_stage.get("semantic_score"),
            "issues": base_stage.get("issues", []),
            "recommended_generation_strategy": base_stage.get(
                "recommended_generation_strategy", "txt2img_retry"
            ),
        }
        retry_instruction = _semantic_retry_instruction(scene, previous_metric)
    accepted = False

    for attempt in range(start_attempt, 5):
        controlled, backend, strategy = _select_comfyui_retry_route(
            model_family="flux2_klein",
            attempt=attempt,
            repair_source_path=repair_source_path,
            previous_metric=previous_metric,
        )
        prompt_builder = (
            _build_image_prompt if backend == "sdxl" else _build_flux2_image_prompt
        )
        prompt = prompt_builder(
            scene,
            STYLE_KEY,
            visual_bible,
            retry_instruction,
        )
        output_path = OUTPUT_ROOT / f"scene_2_attempt_{attempt}.png"
        monitor, _record, metric = _run_comfyui_image_attempt(
            scene=scene,
            image_path=str(output_path),
            directed_prompt=prompt,
            image_style=STYLE_KEY,
            style_label=STYLE_LABEL,
            quality_preset_key="high",
            quality_preset=quality,
            checkpoint_name=checkpoint,
            scene_seed=2026071810 + attempt,
            visual_bible=visual_bible,
            runpod_endpoint_id=endpoint_id,
            runpod_api_key=api_key,
            runpod_gpu_usd_per_second=gpu_rate,
            attempt=attempt,
            controlled_workflow=controlled,
            control_strategy=strategy,
            control_image_path=repair_source_path if controlled else None,
            reference_image_path=str(reference_path),
            semantic_repair_backend_override=backend,
        )
        stages.append(
            _stage_payload(
                name=f"scene_attempt_{attempt}_{backend or 'flux2'}_{strategy}",
                monitor=monitor,
                metric=metric,
                path=output_path,
            )
        )
        if _non_retryable_comfyui_job_error(monitor):
            break
        if metric and metric.get("semantic_accepted"):
            accepted = True
            break
        if output_path.is_file() and output_path.stat().st_size > 1000:
            repair_source_path = str(output_path)
        if metric:
            previous_metric = metric
            retry_instruction = _semantic_retry_instruction(scene, metric)
        if not repair_source_path:
            break

    final_stage = stages[-1] if stages else {}
    report = {
        "status": _stage_report_status(accepted, final_stage),
        "accepted": accepted,
        "semantic_threshold": int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88")),
        "stages": stages,
        "total_estimated_cost_usd": round(
            sum(float(stage.get("estimated_cost_usd") or 0) for stage in stages),
            6,
        ),
    }
    _write_report(report)
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
