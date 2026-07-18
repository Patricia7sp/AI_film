#!/usr/bin/env python3
"""Validate a two-scene ComfyUI sequence with an approved IP-Adapter anchor."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN3D_ROOT = REPO_ROOT / "open3d_implementation"
ANCHOR_OUTPUT_PATH = REPO_ROOT / "data" / "outputs" / "ipadapter_anchor_smoke.png"
SEQUENCE_OUTPUT_PATH = REPO_ROOT / "data" / "outputs" / "ipadapter_sequence_smoke.png"
REFERENCE_IMAGE_NAME = "approved_story_anchor.png"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(OPEN3D_ROOT))

from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    _build_comfyui_workflow,
    _build_image_prompt,
    _encode_comfyui_reference_image,
    _probe_image_quality,
    _resolve_comfyui_checkpoint,
    _resolve_quality_preset,
    _scene_negative_prompt,
)
from scripts.smoke_comfyui_controlnet_retry import (  # noqa: E402
    _poll_job,
    _required_env,
    _save_workflow_images,
    _submit_workflow,
)


def _anchor_scene() -> dict[str, object]:
    return {
        "scene_id": 1,
        "description": (
            "Alice, uma menina vitoriana de cabelos castanhos e vestido branco simples, "
            "lê um livro sob uma grande árvore em um jardim inglês."
        ),
        "prompt": (
            "single Victorian child Alice reading beneath an old oak tree, original "
            "premium comic storybook animation frame, hand-inked linework, painterly color"
        ),
        "must_include": [
            "exactly one child Alice",
            "brown shoulder-length hair",
            "simple white Victorian day dress",
            "open book",
            "large old oak tree",
        ],
        "must_not_include": [
            "second girl",
            "adult woman",
            "princess gown",
            "photorealism",
            "text",
        ],
    }


def _sequence_scene() -> dict[str, object]:
    return {
        "scene_id": 2,
        "description": (
            "A mesma Alice observa um pequeno ratinho branco natural surgindo de um "
            "açucareiro de porcelana aberto sobre uma mesa de chá vitoriana."
        ),
        "prompt": (
            "same child Alice beside a Victorian tea table, close readable porcelain "
            "sugar bowl with its separate lid, tiny natural white mouse peeking over the rim"
        ),
        "must_include": [
            "the same single child Alice from the approved anchor",
            "open lidded porcelain sugar bowl without handles",
            "separate sugar bowl lid visible beside the bowl",
            "tiny natural white mouse peeking from the sugar bowl",
        ],
        "must_not_include": [
            "teacup replacing the sugar bowl",
            "cup handle on the sugar bowl",
            "anthropomorphic mouse",
            "mouse wearing clothes",
            "second Alice",
            "photorealism",
        ],
    }


def _build_anchor_workflow() -> dict[str, object]:
    scene = _anchor_scene()
    preset = _resolve_quality_preset("high")
    prompt = _build_image_prompt(scene, "comic_storybook", {}, "")
    return _build_comfyui_workflow(
        directed_prompt=prompt,
        checkpoint_name=_resolve_comfyui_checkpoint("comic_storybook"),
        quality_preset=preset,
        scene_seed=20260713,
        scene_id="ipadapter_anchor_smoke",
        negative_prompt=_scene_negative_prompt(scene),
    )


def _build_sequence_workflow() -> dict[str, object]:
    scene = _sequence_scene()
    preset = _resolve_quality_preset("high")
    prompt = _build_image_prompt(
        scene,
        "comic_storybook",
        {
            "style_label": "Comic storybook",
            "protagonist_identity": (
                "Alice is the exact child established by the approved anchor image"
            ),
        },
        "Preserve Alice's face, age, hair, dress, linework, palette, and rendering style.",
    )
    return _build_comfyui_workflow(
        directed_prompt=prompt,
        checkpoint_name=_resolve_comfyui_checkpoint("comic_storybook"),
        quality_preset=preset,
        scene_seed=20260714,
        scene_id="ipadapter_sequence_smoke",
        negative_prompt=_scene_negative_prompt(scene),
        reference_image_name=REFERENCE_IMAGE_NAME,
        ipadapter_enabled=True,
        ipadapter_weight=0.55,
    )


def _require_technical_quality(
    path: Path,
    scene: dict[str, object],
) -> dict[str, object]:
    quality = _probe_image_quality(str(path), scene=scene)
    issues = {str(issue) for issue in quality.get("issues", [])}
    if "blurry_image" in issues:
        raise RuntimeError(
            f"image_quality_failed:{path.name}:"
            f"focal_edge_sharpness={quality.get('focal_edge_sharpness')}"
        )
    return quality


def main() -> int:
    load_dotenv(OPEN3D_ROOT / ".env", override=True)
    endpoint_id = os.getenv("COMFYUI_SMOKE_ENDPOINT_ID", "").strip() or _required_env(
        "RUNPOD_ENDPOINT_ID"
    )
    api_key = _required_env("RUNPOD_API_KEY")

    anchor_job_id = _submit_workflow(
        endpoint_id,
        api_key,
        _build_anchor_workflow(),
        [],
    )
    anchor_payload = _poll_job(endpoint_id, api_key, anchor_job_id)
    _save_workflow_images(anchor_payload, ANCHOR_OUTPUT_PATH)
    anchor_quality = _require_technical_quality(ANCHOR_OUTPUT_PATH, _anchor_scene())

    reference_image = _encode_comfyui_reference_image(
        str(ANCHOR_OUTPUT_PATH),
        image_name=REFERENCE_IMAGE_NAME,
    )
    sequence_job_id = _submit_workflow(
        endpoint_id,
        api_key,
        _build_sequence_workflow(),
        [reference_image],
    )
    sequence_payload = _poll_job(endpoint_id, api_key, sequence_job_id)
    _save_workflow_images(sequence_payload, SEQUENCE_OUTPUT_PATH)
    sequence_quality = _require_technical_quality(
        SEQUENCE_OUTPUT_PATH,
        _sequence_scene(),
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "anchor": {
                    "job_id": anchor_job_id,
                    "path": str(ANCHOR_OUTPUT_PATH),
                    "quality": anchor_quality,
                },
                "sequence": {
                    "job_id": sequence_job_id,
                    "path": str(SEQUENCE_OUTPUT_PATH),
                    "quality": sequence_quality,
                    "ipadapter_reference": str(ANCHOR_OUTPUT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
