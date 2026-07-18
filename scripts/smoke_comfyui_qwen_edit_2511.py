#!/usr/bin/env python3
"""Smoke-test Qwen-Image-Edit-2511 semantic repair on an isolated RunPod endpoint."""

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
DEFAULT_SOURCE = REPO_ROOT / "data" / "outputs" / "flux2_klein_semantic_smoke.png"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "outputs" / "qwen_edit_2511_semantic_smoke.png"
INPUT_IMAGE_NAME = "qwen_edit_2511_source.png"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(OPEN3D_ROOT))

from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    _build_qwen_image_edit_2511_workflow,
    _combine_image_quality,
    _encode_comfyui_reference_image,
    _evaluate_image_semantics,
    _probe_image_quality,
    _scene_negative_prompt,
)
from scripts.smoke_comfyui_controlnet_retry import (  # noqa: E402
    _poll_job,
    _save_workflow_images,
    _submit_workflow,
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing_env:{name}")
    return value


def _smoke_scene() -> dict[str, Any]:
    return {
        "scene_id": 2,
        "description": (
            "Na sala de jantar vitoriana, Ludovico revela um pequeno ratinho "
            "branco natural surgindo de um açucareiro de porcelana aberto."
        ),
        "prompt": (
            "Victorian storybook dining room, Alice and professor Ludovico at "
            "the tea table, a tiny natural white mouse peeking from an open "
            "lidded porcelain sugar bowl"
        ),
        "must_include": [
            "one 10-year-old Alice",
            "one adult male professor Ludovico",
            "one small open lidded porcelain sugar bowl without handles",
            "one separate sugar bowl lid beside it",
            "one tiny natural white mouse peeking over the sugar bowl rim",
        ],
        "must_not_include": [
            "teacup",
            "cup handle",
            "saucer",
            "serving bowl",
            "giant mouse",
            "anthropomorphic mouse",
            "duplicate people",
            "text",
            "watermark",
        ],
    }


def _edit_prompt() -> str:
    return (
        "Preserve image 1 camera, framing, Victorian room, Alice, professor "
        "Ludovico, facial identities, poses, lighting, palette, and premium "
        "storybook illustration style. Replace only the incorrect tabletop hero "
        "prop with one small handleless porcelain sugar bowl, its single lid "
        "resting beside it, and one tiny natural white mouse peeking just above "
        "the rim. The bowl is approximately two teaspoons wide. The mouse head "
        "is smaller than a teaspoon and occupies less than one quarter of the "
        "bowl opening. Do not create a teacup, cup handle, saucer, serving bowl, "
        "giant mouse, clothed mouse, duplicate person, text, or watermark."
    )


def _topology_repair_prompt() -> str:
    return (
        "Preserve the entire image exactly: camera, framing, Alice, professor "
        "Ludovico, faces, hands, poses, room, lighting, palette, linework, and "
        "premium storybook style. Edit only the foreground porcelain vessel "
        "and mouse. Delete both side handles completely and reconstruct smooth, "
        "uninterrupted porcelain side walls where the handles were. The vessel "
        "must be one small 12-centimeter handleless lidded sugar jar, narrower "
        "than one third of Alice's head width, never a tureen, serving bowl, "
        "teacup, trophy, or soup bowl. Keep its single matching lid lying flat "
        "beside it. Reduce the natural white mouse so only its tiny head and two "
        "front paws peek above the rim; its head must be smaller than a teaspoon. "
        "Do not add handles, side loops, spouts, saucers, duplicate objects, "
        "extra people, text, or watermark."
    )


def _scale_repair_prompt() -> str:
    return (
        "Preserve every pixel outside the foreground tabletop prop area, "
        "including camera, framing, Alice, professor Ludovico, faces, hands, "
        "poses, room, lighting, palette, linework, and storybook style. Edit "
        "only the handleless porcelain sugar jar, white mouse, lid, and nearby "
        "empty tabletop. Shrink the complete sugar jar to exactly half its "
        "current width and height, keeping it centered in the same tabletop "
        "position. Shrink the mouse proportionally so only its tiny head and two "
        "front paws peek above the rim. Add one normal silver teaspoon lying "
        "flat between the jar and its lid as an unambiguous physical scale "
        "reference: the jar is only two teaspoon lengths wide and the mouse head "
        "is smaller than the spoon bowl. Reconstruct natural wooden tabletop in "
        "all vacated space. Keep the vessel sides smooth and uninterrupted. Do "
        "not add handles, loops, spouts, saucers, cups, serving bowls, duplicate "
        "objects, extra people, text, or watermark."
    )


def _character_age_repair_prompt() -> str:
    return (
        "Preserve the complete image exactly except for Alice on the left. Do "
        "not alter professor Ludovico, the table, the small handleless sugar "
        "jar, mouse, spoon, lid, room, camera, lighting, palette, linework, or "
        "storybook style. Make Alice unmistakably one 10-year-old Victorian "
        "child while preserving her brown bob haircut, eye color, and identity: "
        "use natural preteen facial proportions, a shorter rounder child face, "
        "smaller shoulders and hands, no makeup, and an age-appropriate modest "
        "white Victorian child's dress. She must look clearly younger and "
        "smaller than the adult professor. Keep her original pose and gaze. Do "
        "not create another child, duplicate any person, alter the hero object, "
        "add text, or add a watermark."
    )


def _contract_repair_prompt() -> str:
    return (
        "Image 1 is a rejected draft. Preserve only the camera, Victorian room, "
        "table, lighting, palette, linework, and premium storybook style. Keep "
        "the left figure as exactly one 10-year-old child Alice. Transform the "
        "entire right duplicate woman into one clearly adult male mathematics "
        "professor Ludovico, approximately 50 years old, with short graying brown "
        "hair, mature male facial structure, modest dark Victorian suit, waistcoat, "
        "and tie. Rebuild the foreground vessel as one compact 12-centimeter "
        "handleless porcelain sugar bowl with smooth uninterrupted sides. Place its "
        "single lid flat beside it and one normal silver teaspoon nearby. Keep one "
        "tiny natural white mouse with only its head and front paws above the rim; "
        "the mouse head is smaller than the spoon bowl. Do not preserve the duplicate "
        "girl, vessel handle, oversized bowl, extra person, text, or watermark."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--job-id",
        help="Resume an existing RunPod job instead of submitting a duplicate.",
    )
    repair_mode = parser.add_mutually_exclusive_group()
    repair_mode.add_argument(
        "--topology-repair",
        action="store_true",
        help="Repair only hero-object geometry after a semantic first pass.",
    )
    repair_mode.add_argument(
        "--scale-repair",
        action="store_true",
        help="Repair hero-object scale and add an explicit teaspoon reference.",
    )
    repair_mode.add_argument(
        "--character-age-repair",
        action="store_true",
        help="Repair Alice's child age while preserving the approved hero object.",
    )
    repair_mode.add_argument(
        "--contract-repair",
        action="store_true",
        help="Replace duplicate characters and rebuild the hero prop to contract.",
    )
    args = parser.parse_args()

    load_dotenv(OPEN3D_ROOT / ".env", override=False)
    source_path = args.source.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if not source_path.is_file():
        raise RuntimeError(f"missing_source_image:{source_path}")

    endpoint_id = (
        os.getenv("COMFYUI_QWEN_EDIT_ENDPOINT_ID", "").strip()
        or os.getenv("COMFYUI_SMOKE_ENDPOINT_ID", "").strip()
        or _required_env("RUNPOD_ENDPOINT_ID")
    )
    api_key = _required_env("RUNPOD_API_KEY")
    scene = _smoke_scene()
    if args.contract_repair:
        edit_prompt = _contract_repair_prompt()
    elif args.topology_repair:
        edit_prompt = _topology_repair_prompt()
    elif args.scale_repair:
        edit_prompt = _scale_repair_prompt()
    elif args.character_age_repair:
        edit_prompt = _character_age_repair_prompt()
    else:
        edit_prompt = _edit_prompt()
    job_id = str(args.job_id or "").strip()
    if not job_id:
        workflow = _build_qwen_image_edit_2511_workflow(
            edit_prompt=edit_prompt,
            input_image_name=INPUT_IMAGE_NAME,
            scene_seed=20260716,
            scene_id="semantic_repair_smoke",
            negative_prompt=_scene_negative_prompt(scene),
        )
        source_image = _encode_comfyui_reference_image(
            str(source_path),
            image_name=INPUT_IMAGE_NAME,
        )
        job_id = _submit_workflow(endpoint_id, api_key, workflow, [source_image])
    payload = _poll_job(endpoint_id, api_key, job_id)
    saved = _save_workflow_images(payload, output_path)
    technical = _probe_image_quality(str(output_path), scene=scene)
    semantic = _evaluate_image_semantics(
        str(output_path),
        scene,
        edit_prompt,
        "comic_storybook",
        {"protagonist_identity": "Alice is one 10-year-old Victorian child."},
    )
    quality = _combine_image_quality(technical, semantic)
    print(
        json.dumps(
            {
                "status": "ok" if quality.get("semantic_accepted") else "rejected",
                "job_id": job_id,
                "source_path": str(source_path),
                "output_path": str(output_path),
                "size_bytes": saved["size_bytes"],
                "technical": technical,
                "semantic": semantic,
                "quality": quality,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not quality.get("semantic_accepted"):
        raise RuntimeError(
            "qwen_semantic_gate_failed:"
            f"semantic_score={quality.get('semantic_score')}:"
            f"issues={quality.get('issues')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
