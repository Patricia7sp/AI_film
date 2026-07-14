#!/usr/bin/env python3
"""Validate the local RunPod Serverless ComfyUI setup without exposing secrets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "open3d_implementation" / ".env"
DOCKERFILE_PATH = ROOT / "runpod_worker" / "Dockerfile"
START_SCRIPT_PATH = ROOT / "runpod_worker" / "start_ai_film.sh"
MODEL_DOWNLOAD_SCRIPT_PATH = ROOT / "scripts" / "runpod_download_hf_model.sh"
CONTROLNET_PREP_SCRIPT_PATH = ROOT / "scripts" / "runpod_prepare_controlnet_volume.sh"
IPADAPTER_PREP_SCRIPT_PATH = ROOT / "scripts" / "runpod_prepare_ipadapter_volume.sh"
FLUX2_PREP_SCRIPT_PATH = ROOT / "scripts" / "runpod_prepare_flux2_volume.sh"
CONTROLNET_COMMAND_PRINTER_PATH = (
    ROOT / "scripts" / "print_runpod_controlnet_install_command.py"
)
CONTROLNET_POD_CONTROLLER_PATH = ROOT / "scripts" / "runpod_controlnet_pod.py"
DOCKER_CANDIDATES = (
    "docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
)


def load_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def find_docker() -> str:
    for candidate in DOCKER_CANDIDATES:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return candidate
    return ""


def docker_daemon_status(docker_bin: str) -> Tuple[bool, str]:
    if not docker_bin:
        return False, "Docker CLI not found"
    result = subprocess.run(
        [docker_bin, "info"],
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if result.returncode == 0:
        return True, "Docker daemon available"
    message = (result.stderr or result.stdout).strip().splitlines()[-1]
    return False, message


def validate_dockerfile() -> List[str]:
    failures: List[str] = []
    if not DOCKERFILE_PATH.exists():
        return ["runpod_worker/Dockerfile is missing"]
    text = DOCKERFILE_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "RUNPOD_COMFYUI_BASE_IMAGE=runpod/worker-comfyui:5.8.6-base",
        "FROM ${RUNPOD_COMFYUI_BASE_IMAGE}",
        "models/checkpoints",
        "ai-film-comic-storybook-xl.safetensors",
        "start_ai_film.sh",
        "comfyorg/comfyui-ipadapter.git",
        "COMFYUI_IPADAPTER_COMMIT=",
        'CMD ["/start_ai_film.sh"]',
        "v1-5-pruned-emaonly.safetensors",
    )
    for item in required:
        if item not in text:
            failures.append(f"Dockerfile missing: {item}")
    return failures


def validate_shell_script(path: Path, label: str) -> List[str]:
    if not path.exists():
        return [f"{label} is missing"]
    try:
        result = subprocess.run(
            ["bash", "-n", str(path)],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"{label} syntax check failed: {type(exc).__name__}"]
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1]
        return [f"{label} syntax invalid: {detail}"]
    return []


def validate_worker_wrapper() -> List[str]:
    failures = validate_shell_script(
        START_SCRIPT_PATH, "runpod_worker/start_ai_film.sh"
    )
    if failures:
        return failures
    text = START_SCRIPT_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "MODEL_DIRS=",
        "checkpoints",
        "controlnet",
        "clip_vision",
        "ipadapter",
        "diffusion_models",
        "text_encoders",
        "/runpod-volume/models/${model_dir}",
        "/comfyui/models/${model_dir}",
        "exec /start.sh",
    )
    for item in required:
        if item not in text:
            failures.append(f"start_ai_film.sh missing: {item}")
    return failures


def validate_model_downloader() -> List[str]:
    failures = validate_shell_script(
        MODEL_DOWNLOAD_SCRIPT_PATH, "scripts/runpod_download_hf_model.sh"
    )
    if failures:
        return failures
    text = MODEL_DOWNLOAD_SCRIPT_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "semantic-sdxl",
        "animation-sdxl",
        "controlnet-sdxl-canny",
        "controlnet-sdxl-depth",
        "ipadapter-plus-sdxl",
        "clip-vision-vit-h",
        "flux2-klein-base-4b",
        "flux2-qwen-3-4b",
        "flux2-vae",
        "models/controlnet",
        "HF_TOKEN",
        "curl -fL",
    )
    for item in required:
        if item not in text:
            failures.append(f"runpod_download_hf_model.sh missing: {item}")
    return failures


def validate_controlnet_preparer() -> List[str]:
    failures = validate_shell_script(
        CONTROLNET_PREP_SCRIPT_PATH, "scripts/runpod_prepare_controlnet_volume.sh"
    )
    if failures:
        return failures
    text = CONTROLNET_PREP_SCRIPT_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "runpod_download_hf_model.sh",
        "controlnet-sdxl-canny",
        "controlnet-sdxl-depth",
        "models/controlnet",
        "AI_FILM_CONTROLNET_VOLUME_CONTENTS",
    )
    for item in required:
        if item not in text:
            failures.append(f"runpod_prepare_controlnet_volume.sh missing: {item}")
    return failures


def validate_ipadapter_preparer() -> List[str]:
    failures = validate_shell_script(
        IPADAPTER_PREP_SCRIPT_PATH, "scripts/runpod_prepare_ipadapter_volume.sh"
    )
    if failures:
        return failures
    text = IPADAPTER_PREP_SCRIPT_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "ipadapter-plus-sdxl",
        "clip-vision-vit-h",
        "models/ipadapter",
        "models/clip_vision",
        "AI_FILM_IPADAPTER_VOLUME_READY",
    )
    for item in required:
        if item not in text:
            failures.append(f"runpod_prepare_ipadapter_volume.sh missing: {item}")
    return failures


def validate_flux2_preparer() -> List[str]:
    failures = validate_shell_script(
        FLUX2_PREP_SCRIPT_PATH, "scripts/runpod_prepare_flux2_volume.sh"
    )
    if failures:
        return failures
    text = FLUX2_PREP_SCRIPT_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "flux2-klein-base-4b",
        "flux2-qwen-3-4b",
        "flux2-vae",
        "models/diffusion_models",
        "models/text_encoders",
        "AI_FILM_FLUX2_VOLUME_READY",
    )
    for item in required:
        if item not in text:
            failures.append(f"runpod_prepare_flux2_volume.sh missing: {item}")
    return failures


def validate_controlnet_command_printer() -> List[str]:
    if not CONTROLNET_COMMAND_PRINTER_PATH.exists():
        return ["scripts/print_runpod_controlnet_install_command.py is missing"]
    text = CONTROLNET_COMMAND_PRINTER_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "controlnet-canny-sdxl-1.0",
        "controlnet-depth-sdxl-1.0",
        "AI_FILM_CONTROLNET_VOLUME_CONTENTS",
        "bash -lc",
        "shlex.quote",
    )
    failures: List[str] = []
    for item in required:
        if item not in text:
            failures.append(
                f"print_runpod_controlnet_install_command.py missing: {item}"
            )
    return failures


def validate_controlnet_pod_controller() -> List[str]:
    if not CONTROLNET_POD_CONTROLLER_PATH.exists():
        return ["scripts/runpod_controlnet_pod.py is missing"]
    text = CONTROLNET_POD_CONTROLLER_PATH.read_text(encoding="utf-8", errors="replace")
    required = (
        "podFindAndDeployOnDemand",
        "podTerminate",
        "networkVolumeId",
        "controlnet-canny-sdxl-1.0",
        "controlnet-depth-sdxl-1.0",
        "flux-2-klein-base-4b.safetensors",
        "qwen_3_4b.safetensors",
        "flux2-vae.safetensors",
        "status.json",
        "19123/http",
    )
    failures: List[str] = []
    for item in required:
        if item not in text:
            failures.append(f"runpod_controlnet_pod.py missing: {item}")
    return failures


def test_runpod(api_key: str, endpoint_id: str) -> Tuple[bool, str]:
    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme != "https" or parsed_url.netloc != "api.runpod.ai":
        return False, "RunPod URL validation failed"

    payload = json.dumps({"input": {"workflow": {}}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:  # nosec B310
            body = response.read().decode("utf-8", errors="replace")
            return True, f"HTTP {response.status}: {body[:300]}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code in {400, 422, 500} and "auth" not in body.lower():
            return (
                True,
                f"HTTP {exc.code}: endpoint reached; response was not auth failure",
            )
        return False, f"HTTP {exc.code}: {body[:300]}"
    except urllib.error.URLError as exc:
        return False, f"URL error: {exc.reason}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RunPod ComfyUI setup.")
    parser.add_argument(
        "--test-endpoint",
        action="store_true",
        help="Call the RunPod runsync endpoint with an empty workflow.",
    )
    parser.add_argument(
        "--require-docker",
        action="store_true",
        help="Also require a local Docker daemon. Not needed for Network Volume flow.",
    )
    args = parser.parse_args()

    failures: List[str] = []
    env = load_env(ENV_PATH)
    api_key = env.get("RUNPOD_API_KEY", "")
    endpoint_id = env.get("RUNPOD_ENDPOINT_ID", "")
    network_volume_id = env.get("RUNPOD_NETWORK_VOLUME_ID", "")
    network_volume_datacenter = env.get("RUNPOD_NETWORK_VOLUME_DATACENTER", "")

    print("RunPod setup validation")
    print(
        f"- Env file: {ENV_PATH.relative_to(ROOT)} {'present' if ENV_PATH.exists() else 'missing'}"
    )
    print(f"- RUNPOD_API_KEY: {'present' if api_key else 'missing'}")
    print(f"- RUNPOD_ENDPOINT_ID: {'present' if endpoint_id else 'missing'}")
    print(
        "- RUNPOD_NETWORK_VOLUME_ID: "
        f"{'present' if network_volume_id else 'missing'}"
    )
    print(
        "- RUNPOD_NETWORK_VOLUME_DATACENTER: "
        f"{network_volume_datacenter or 'missing'}"
    )
    if endpoint_id:
        print(f"- Endpoint suffix: {endpoint_id[-4:]}")

    dockerfile_failures = validate_dockerfile()
    failures.extend(dockerfile_failures)
    print(f"- Dockerfile: {'ok' if not dockerfile_failures else 'failed'}")

    wrapper_failures = validate_worker_wrapper()
    failures.extend(wrapper_failures)
    print(f"- Worker wrapper: {'ok' if not wrapper_failures else 'failed'}")

    downloader_failures = validate_model_downloader()
    failures.extend(downloader_failures)
    print(f"- Model downloader: {'ok' if not downloader_failures else 'failed'}")

    controlnet_failures = validate_controlnet_preparer()
    failures.extend(controlnet_failures)
    print(f"- ControlNet preparer: {'ok' if not controlnet_failures else 'failed'}")

    ipadapter_failures = validate_ipadapter_preparer()
    failures.extend(ipadapter_failures)
    print(f"- IP-Adapter preparer: {'ok' if not ipadapter_failures else 'failed'}")

    flux2_failures = validate_flux2_preparer()
    failures.extend(flux2_failures)
    print(f"- FLUX.2 preparer: {'ok' if not flux2_failures else 'failed'}")

    command_printer_failures = validate_controlnet_command_printer()
    failures.extend(command_printer_failures)
    print(
        "- ControlNet paste command: "
        f"{'ok' if not command_printer_failures else 'failed'}"
    )

    pod_controller_failures = validate_controlnet_pod_controller()
    failures.extend(pod_controller_failures)
    print(
        "- ControlNet Pod controller: "
        f"{'ok' if not pod_controller_failures else 'failed'}"
    )

    docker_bin = find_docker()
    print(f"- Docker CLI: {docker_bin or 'missing'}")
    if args.require_docker:
        daemon_ok, daemon_message = docker_daemon_status(docker_bin)
        print(f"- Docker daemon: {daemon_message}")
        if not daemon_ok:
            failures.append("Docker daemon unavailable")
    else:
        print("- Docker daemon: skipped (Network Volume flow)")

    if not api_key:
        failures.append("RUNPOD_API_KEY missing")
    if not endpoint_id:
        failures.append("RUNPOD_ENDPOINT_ID missing")
    if not network_volume_id:
        failures.append("RUNPOD_NETWORK_VOLUME_ID missing")
    if not network_volume_datacenter:
        failures.append("RUNPOD_NETWORK_VOLUME_DATACENTER missing")

    if args.test_endpoint:
        if api_key and endpoint_id:
            ok, message = test_runpod(api_key, endpoint_id)
            print(f"- RunPod endpoint test: {message}")
            if not ok:
                failures.append("RunPod endpoint test failed")
        else:
            failures.append(
                "RunPod endpoint test skipped because credentials are missing"
            )

    if failures:
        print("\nStatus: BLOCKED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nStatus: READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
