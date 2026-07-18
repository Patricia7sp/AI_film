#!/usr/bin/env python3
"""Run a semantic FLUX.2 Klein smoke against a temporary RunPod endpoint."""

from __future__ import annotations

import argparse
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
    _build_flux2_image_prompt,
    _build_flux2_klein_workflow,
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
            "exactly one unmistakably preteen ten-year-old child Alice",
            "open tabletop porcelain sugar bowl without handles",
            "one separate sugar bowl lid lying flat on the table beside the bowl",
            "tiny natural white mouse no taller than the sugar bowl rim",
        ],
        "must_not_include": [
            "teacup replacing the sugar bowl",
            "cup handle on the sugar bowl",
            "anthropomorphic mouse",
            "mouse wearing clothes",
            "second Alice",
            "adult woman",
            "teenage Alice",
            "person holding the sugar bowl lid",
            "mouse filling most of the sugar bowl",
            "visible text",
        ],
    }


def _build_smoke_workflow(
    *, seed: int = 20260716
) -> tuple[dict[str, dict[str, object]], str]:
    scene = _semantic_scene()
    prompt = _build_flux2_image_prompt(
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
            "Correct only these failures. Alice is an unmistakably preteen ten-year-old "
            "child, with a round child face and smaller head and shoulders than adult "
            "Ludovico. Center one compact 12 cm porcelain sugar basin with completely "
            "smooth handleless sides. Show only the tiny mouse head and front paws "
            "peeking above the rim; its head is no wider than one fifth of the bowl. "
            "Place exactly one matching lid flat on the table beside the bowl. No one "
            "touches or holds the lid. Do not add cups, handles or a second container."
        ),
    )
    return (
        _build_flux2_klein_workflow(
            directed_prompt=prompt,
            quality_preset=_resolve_quality_preset("high"),
            scene_seed=seed,
            scene_id="flux2_klein_semantic_smoke",
        ),
        prompt,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evaluate-existing",
        action="store_true",
        help="Run semantic QA against the existing output without a RunPod job.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260716,
        help="Deterministic seed for an isolated retry candidate.",
    )
    parser.add_argument(
        "--job-id",
        help="Resume an existing RunPod job instead of submitting a duplicate.",
    )
    args = parser.parse_args()
    # Explicit process variables select the isolated canary without mutating .env.
    load_dotenv(OPEN3D_ROOT / ".env", override=False)
    workflow, directed_prompt = _build_smoke_workflow(seed=args.seed)
    job_id = str(args.job_id or "").strip() or "existing-output"
    if args.evaluate_existing:
        if not OUTPUT_PATH.exists():
            raise FileNotFoundError(f"Missing smoke output: {OUTPUT_PATH}")
    else:
        endpoint_id = (
            os.getenv("COMFYUI_FLUX2_SMOKE_ENDPOINT_ID", "").strip()
            or os.getenv("COMFYUI_SMOKE_ENDPOINT_ID", "").strip()
            or _required_env("RUNPOD_ENDPOINT_ID")
        )
        api_key = _required_env("RUNPOD_API_KEY")
        if not args.job_id:
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
