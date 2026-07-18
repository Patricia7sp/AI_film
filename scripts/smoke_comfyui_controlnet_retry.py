#!/usr/bin/env python3
"""Smoke test the AI Film ComfyUI ControlNet and IP-Adapter workflow on RunPod."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN3D_ROOT = REPO_ROOT / "open3d_implementation"
OUTPUT_PATH = REPO_ROOT / "data" / "outputs" / "controlnet_depth_single_pass_smoke.png"
CONTROL_SOURCE_PATH = (
    REPO_ROOT / "data" / "outputs" / "controlnet_retry_builder_smoke.png"
)

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(OPEN3D_ROOT))

from open3d_implementation.core.langgraph_adapter import (  # noqa: E402
    _build_comfyui_workflow,
    _build_image_prompt,
    _encode_comfyui_control_image,
    _encode_comfyui_inpaint_image,
    _encode_comfyui_reference_image,
    _probe_image_quality,
    _resolve_comfyui_checkpoint,
    _resolve_quality_preset,
    _scene_negative_prompt,
)

CONTROL_IMAGE_NAME = "controlnet_retry_reference.png"
INPAINT_IMAGE_NAME = "controlnet_retry_inpaint.png"
IPADAPTER_REFERENCE_IMAGE_NAME = "ipadapter_story_reference.png"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing_env:{name}")
    return value


def _submit_workflow(
    endpoint_id: str,
    api_key: str,
    workflow: dict[str, Any],
    images: list[dict[str, str]],
) -> str:
    response = requests.post(
        f"https://api.runpod.ai/v2/{endpoint_id}/run",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"input": {"workflow": workflow, "images": images}},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"submit_failed:{response.status_code}:{response.text[:300]}"
        )
    job_id = str(response.json().get("id") or "")
    if not job_id:
        raise RuntimeError("submit_failed:missing_job_id")
    return job_id


def _poll_job(endpoint_id: str, api_key: str, job_id: str) -> dict[str, Any]:
    max_wait = int(os.getenv("COMFYUI_CONTROLNET_SMOKE_MAX_WAIT_SECONDS", "420"))
    waited = 0
    consecutive_errors = 0
    last_status = ""
    while waited < max_wait:
        time.sleep(3)
        waited += 3
        try:
            response = requests.get(
                f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
        except requests.RequestException as exc:
            consecutive_errors += 1
            if consecutive_errors in {1, 5, 10}:
                print(
                    json.dumps(
                        {
                            "job_id": job_id,
                            "status": "POLL_RETRY",
                            "waited": waited,
                            "error": type(exc).__name__,
                            "consecutive_errors": consecutive_errors,
                        }
                    ),
                    flush=True,
                )
            if consecutive_errors >= 10:
                raise RuntimeError(
                    f"job_poll_failed:{type(exc).__name__}:{consecutive_errors}"
                ) from exc
            continue
        consecutive_errors = 0
        if response.status_code != 200:
            continue
        payload = response.json()
        status = payload.get("status")
        if status != last_status or waited % 30 == 0:
            print(
                json.dumps({"job_id": job_id, "status": status, "waited": waited}),
                flush=True,
            )
            last_status = str(status or "")
        if status == "COMPLETED":
            return payload
        if status in {"FAILED", "CANCELLED", "TIMED_OUT"}:
            raise RuntimeError(f"job_failed:{status}:{payload.get('error')}")
    raise RuntimeError(f"job_timeout:{max_wait}")


def _save_workflow_images(
    payload: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    images = payload.get("output", {}).get("images", [])
    if not images:
        raise RuntimeError("completed_without_images")

    final_image = next(
        (
            item
            for item in images
            if "base_inpaint" not in str(item.get("filename") or "")
        ),
        images[0],
    )
    intermediate_image = next(
        (item for item in images if "base_inpaint" in str(item.get("filename") or "")),
        None,
    )

    def decode_image(item: dict[str, Any]) -> bytes:
        encoded = str(item.get("data") or "")
        try:
            image_bytes = base64.b64decode(encoded)
        except binascii.Error as exc:
            raise RuntimeError("invalid_base64_image") from exc
        if len(image_bytes) < 1000:
            raise RuntimeError("decoded_image_too_small")
        return image_bytes

    final_bytes = decode_image(final_image)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(final_bytes)
    result: dict[str, Any] = {
        "size_bytes": len(final_bytes),
        "final_path": str(output_path),
        "intermediate_path": "",
        "intermediate_size_bytes": 0,
    }
    if intermediate_image:
        intermediate_bytes = decode_image(intermediate_image)
        intermediate_path = output_path.with_name(
            f"{output_path.stem}_base_inpaint{output_path.suffix}"
        )
        intermediate_path.write_bytes(intermediate_bytes)
        result["intermediate_path"] = str(intermediate_path)
        result["intermediate_size_bytes"] = len(intermediate_bytes)
    return result


def _build_smoke_workflow(
    *, ipadapter_enabled: bool = True, controlnet_enabled: bool = True
) -> tuple[dict[str, Any], dict[str, Any]]:
    preset_key = os.getenv("COMFYUI_CONTROLNET_SMOKE_PRESET", "high")
    preset = _resolve_quality_preset(preset_key)
    smoke_scene = {
        "scene_id": 2,
        "description": (
            "Na sala de jantar vitoriana, um pequeno ratinho branco surge do "
            "açucareiro aberto sobre a mesa."
        ),
        "prompt": (
            "Victorian tea table insert with an open lidded porcelain sugar bowl "
            "and a tiny natural white mouse peeking over its rim"
        ),
        "must_include": [
            "open lidded porcelain sugar bowl without handles",
            "separate sugar bowl lid visible beside the bowl",
            "tiny natural white mouse peeking from the sugar bowl",
        ],
        "must_not_include": [
            "teacup",
            "coffee cup",
            "cup handle",
            "saucer",
            "anthropomorphic mouse",
        ],
    }
    directed_prompt = _build_image_prompt(
        smoke_scene,
        "comic_storybook",
        {},
        (
            "Preserve the approved scene outside the masked region. Replace only "
            "the hero prop with a lidded sugar bowl and natural white mouse."
        ),
    )
    workflow = _build_comfyui_workflow(
        directed_prompt=directed_prompt,
        checkpoint_name=_resolve_comfyui_checkpoint("comic_storybook"),
        quality_preset=preset,
        scene_seed=20260708,
        scene_id="controlnet_retry_smoke",
        negative_prompt=_scene_negative_prompt(smoke_scene),
        controlled_workflow=controlnet_enabled,
        control_image_name=CONTROL_IMAGE_NAME if controlnet_enabled else None,
        inpaint_image_name=INPAINT_IMAGE_NAME,
        refiner_enabled=False,
        reference_image_name=(
            IPADAPTER_REFERENCE_IMAGE_NAME if ipadapter_enabled else None
        ),
        ipadapter_enabled=ipadapter_enabled,
    )
    return workflow, smoke_scene


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--control-source",
        type=Path,
        default=CONTROL_SOURCE_PATH,
        help="Approved or rejected base frame to repair with masked control.",
    )
    parser.add_argument(
        "--without-ipadapter",
        action="store_true",
        help="Do not reuse the rejected frame as an IP-Adapter identity reference.",
    )
    parser.add_argument(
        "--inpaint-only",
        action="store_true",
        help="Use masked inpainting without structural ControlNet guidance.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Destination for the repaired image.",
    )
    args = parser.parse_args()
    control_source = args.control_source.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    load_dotenv(OPEN3D_ROOT / ".env", override=False)
    endpoint_id = os.getenv("COMFYUI_SMOKE_ENDPOINT_ID", "").strip() or _required_env(
        "RUNPOD_ENDPOINT_ID"
    )
    api_key = _required_env("RUNPOD_API_KEY")
    preset_key = os.getenv("COMFYUI_CONTROLNET_SMOKE_PRESET", "high")
    preset = _resolve_quality_preset(preset_key)
    if not control_source.is_file():
        raise RuntimeError(f"missing_control_source:{control_source}")
    ipadapter_enabled = not args.without_ipadapter
    workflow, smoke_scene = _build_smoke_workflow(
        ipadapter_enabled=ipadapter_enabled,
        controlnet_enabled=not args.inpaint_only,
    )
    inpaint_image = _encode_comfyui_inpaint_image(
        str(control_source),
        image_name=INPAINT_IMAGE_NAME,
        width=preset["width"],
        height=preset["height"],
        scene=smoke_scene,
    )
    images = [inpaint_image]
    if not args.inpaint_only:
        images.insert(
            0,
            _encode_comfyui_control_image(
                str(control_source),
                image_name=CONTROL_IMAGE_NAME,
                width=preset["width"],
                height=preset["height"],
                scene=smoke_scene,
            ),
        )
    if ipadapter_enabled:
        images.append(
            _encode_comfyui_reference_image(
                str(control_source),
                image_name=IPADAPTER_REFERENCE_IMAGE_NAME,
            )
        )
    job_id = _submit_workflow(
        endpoint_id,
        api_key,
        workflow,
        images,
    )
    payload = _poll_job(endpoint_id, api_key, job_id)
    saved_images = _save_workflow_images(payload, output_path)
    size_bytes = saved_images["size_bytes"]
    technical_quality = _probe_image_quality(str(output_path), scene=smoke_scene)
    quality_issues = technical_quality.get("issues", [])
    print(
        json.dumps(
            {
                "status": "ok",
                "job_id": job_id,
                "output_path": str(output_path),
                "size_bytes": size_bytes,
                "intermediate_path": saved_images["intermediate_path"],
                "intermediate_size_bytes": saved_images["intermediate_size_bytes"],
                "technical_quality": technical_quality,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if "blurry_image" in quality_issues:
        raise RuntimeError(
            "image_quality_failed:blurry_image:"
            f"edge_sharpness={technical_quality.get('edge_sharpness')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
