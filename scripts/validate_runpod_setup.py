#!/usr/bin/env python3
"""Validate the local RunPod Serverless ComfyUI setup without exposing secrets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "open3d_implementation" / ".env"
DOCKERFILE_PATH = ROOT / "runpod_worker" / "Dockerfile"
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
        "FROM runpod/worker-comfyui:5.8.6-base",
        "models/checkpoints",
        "v1-5-pruned-emaonly.safetensors",
    )
    for item in required:
        if item not in text:
            failures.append(f"Dockerfile missing: {item}")
    return failures


def test_runpod(api_key: str, endpoint_id: str) -> Tuple[bool, str]:
    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
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
        with urllib.request.urlopen(req, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, f"HTTP {response.status}: {body[:300]}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code in {400, 422, 500} and "auth" not in body.lower():
            return True, f"HTTP {exc.code}: endpoint reached; response was not auth failure"
        return False, f"HTTP {exc.code}: {body[:300]}"
    except urllib.error.URLError as exc:
        return False, f"URL error: {exc.reason}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RunPod ComfyUI setup.")
    parser.add_argument("--test-endpoint", action="store_true", help="Call the RunPod runsync endpoint with an empty workflow.")
    args = parser.parse_args()

    failures: List[str] = []
    env = load_env(ENV_PATH)
    api_key = env.get("RUNPOD_API_KEY", "")
    endpoint_id = env.get("RUNPOD_ENDPOINT_ID", "")

    print("RunPod setup validation")
    print(f"- Env file: {ENV_PATH.relative_to(ROOT)} {'present' if ENV_PATH.exists() else 'missing'}")
    print(f"- RUNPOD_API_KEY: {'present' if api_key else 'missing'}")
    print(f"- RUNPOD_ENDPOINT_ID: {'present' if endpoint_id else 'missing'}")
    if endpoint_id:
        print(f"- Endpoint suffix: {endpoint_id[-4:]}")

    dockerfile_failures = validate_dockerfile()
    failures.extend(dockerfile_failures)
    print(f"- Dockerfile: {'ok' if not dockerfile_failures else 'failed'}")

    docker_bin = find_docker()
    print(f"- Docker CLI: {docker_bin or 'missing'}")
    daemon_ok, daemon_message = docker_daemon_status(docker_bin)
    print(f"- Docker daemon: {daemon_message}")
    if not daemon_ok:
        failures.append("Docker daemon unavailable")

    if not api_key:
        failures.append("RUNPOD_API_KEY missing")
    if not endpoint_id:
        failures.append("RUNPOD_ENDPOINT_ID missing")

    if args.test_endpoint:
        if api_key and endpoint_id:
            ok, message = test_runpod(api_key, endpoint_id)
            print(f"- RunPod endpoint test: {message}")
            if not ok:
                failures.append("RunPod endpoint test failed")
        else:
            failures.append("RunPod endpoint test skipped because credentials are missing")

    if failures:
        print("\nStatus: BLOCKED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nStatus: READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
