#!/usr/bin/env python3
"""Run a semantic FLUX.2 Klein smoke against a temporary RunPod endpoint."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN3D_ROOT = REPO_ROOT / "open3d_implementation"
OUTPUT_PATH = REPO_ROOT / "data" / "outputs" / "flux2_klein_semantic_smoke.png"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(OPEN3D_ROOT))

from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    _build_flux2_klein_workflow,
    _build_image_prompt,
    _combine_image_quality,
    _evaluate_image_semantics,
    _probe_image_quality,
    _resolve_quality_preset,
)
from scripts.smoke_comfyui_controlnet_retry import (  # noqa: E402
    _poll_job,
    _required_env,
    _save_workflow_images,
    _submit_workflow,
)


def _semantic_scene() -> dict[str, object]:
    return {
        "scene_id": 2,
        "description": (
            "A mesma Alice, uma única menina vitoriana de dez anos, observa um "
            "pequeno ratinho branco natural surgindo de um açucareiro de porcelana "
            "aberto sobre uma mesa de chá vitoriana."
        ),
        "prompt": (
            "single child Alice beside a Victorian tea table, close readable porcelain "
            "sugar bowl with separate lid, tiny natural white mouse peeking over the rim"
        ),
        "must_include": [
            "exactly one ten-year-old child Alice",
            "open lidded porcelain sugar bowl without handles",
            "separate sugar bowl lid visible beside the bowl",
            "tiny natural white mouse emerging from the sugar bowl",
        ],
        "must_not_include": [
            "teacup replacing the sugar bowl",
            "cup handle on the sugar bowl",
            "anthropomorphic mouse",
            "mouse wearing clothes",
            "second Alice",
            "adult woman",
            "visible text",
        ],
    }


def _build_smoke_workflow() -> tuple[dict[str, dict[str, object]], str]:
    scene = _semantic_scene()
    prompt = _build_image_prompt(
        scene,
        "comic_storybook",
        {
            "style_label": "Original premium comic storybook animation",
            "protagonist_identity": (
                "Alice is one ten-year-old Victorian child with shoulder-length brown "
                "hair and a simple ivory day dress"
            ),
        },
        (
            "Render a single cinematic story frame, not a character sheet. Make the "
            "small mouse and open sugar bowl unmistakably readable in the foreground."
        ),
    )
    return (
        _build_flux2_klein_workflow(
            directed_prompt=prompt,
            quality_preset=_resolve_quality_preset("high"),
            scene_seed=20260715,
            scene_id="flux2_klein_semantic_smoke",
        ),
        prompt,
    )


def main() -> int:
    load_dotenv(OPEN3D_ROOT / ".env", override=True)
    endpoint_id = (
        os.getenv("COMFYUI_FLUX2_SMOKE_ENDPOINT_ID", "").strip()
        or os.getenv("COMFYUI_SMOKE_ENDPOINT_ID", "").strip()
        or _required_env("RUNPOD_ENDPOINT_ID")
    )
    api_key = _required_env("RUNPOD_API_KEY")
    workflow, directed_prompt = _build_smoke_workflow()
    job_id = _submit_workflow(endpoint_id, api_key, workflow, [])
    payload = _poll_job(endpoint_id, api_key, job_id)
    _save_workflow_images(payload, OUTPUT_PATH)

    scene = _semantic_scene()
    technical = _probe_image_quality(str(OUTPUT_PATH), scene=scene)
    semantic = _evaluate_image_semantics(
        str(OUTPUT_PATH),
        scene,
        directed_prompt,
        "comic_storybook",
        {},
    )
    quality = _combine_image_quality(technical, semantic)
    accepted = bool(quality.get("semantic_accepted"))
    print(
        json.dumps(
            {
                "status": "accepted" if accepted else "rejected",
                "job_id": job_id,
                "path": str(OUTPUT_PATH),
                "quality": quality,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
