#!/usr/bin/env python3
"""Create or terminate a temporary RunPod Pod for visual-control assets."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "open3d_implementation" / ".env"
GRAPHQL_URL = "https://api.runpod.io/graphql"


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


def request_graphql(
    api_key: str,
    query: str,
    variables: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ai-film-runpod-control/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:  # nosec B310
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:1200]}") from exc
    result = json.loads(body or "{}")
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False)[:1200])
    return result.get("data", {})


def install_command() -> str:
    return r"""bash -lc 'set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl coreutils python3
rm -rf /var/lib/apt/lists/*
if [[ -d "/runpod-volume" ]]; then VOLUME_ROOT="/runpod-volume"; elif [[ -d "/workspace" ]]; then VOLUME_ROOT="/workspace"; else echo "missing RunPod volume" >&2; exit 1; fi
CONTROLNET_DIR="${VOLUME_ROOT}/models/controlnet"
IPADAPTER_DIR="${VOLUME_ROOT}/models/ipadapter"
CLIP_VISION_DIR="${VOLUME_ROOT}/models/clip_vision"
STATUS_DIR="/tmp/ai-film-status"
mkdir -p "${STATUS_DIR}"
write_status() {
  status="$1"; detail="$2"
  printf "{\"status\":\"%s\",\"detail\":\"%s\",\"volume_root\":\"%s\"}\n" "${status}" "${detail}" "${VOLUME_ROOT}" > "${STATUS_DIR}/status.json"
}
write_status "starting" "installing dependencies"
python3 -m http.server 19123 --bind 0.0.0.0 --directory "${STATUS_DIR}" >/tmp/ai-film-status-server.log 2>&1 &
mkdir -p "${CONTROLNET_DIR}" "${IPADAPTER_DIR}" "${CLIP_VISION_DIR}"
download_model() {
  url="$1"; target="$2"; minimum_bytes="$3"; partial="${target}.partial"
  if [[ -f "${target}" ]] && [[ "$(stat -c%s "${target}")" -ge "${minimum_bytes}" ]]; then
    echo "Already ready: ${target}"
    return
  fi
  auth_args=()
  if [[ -n "${HF_TOKEN:-}" ]]; then auth_args=(-H "Authorization: Bearer ${HF_TOKEN}"); fi
  echo "Downloading into ${target}"
  write_status "downloading" "$(basename "${target}")"
  curl -fL --retry 5 --retry-delay 5 --continue-at - "${auth_args[@]}" -o "${partial}" "${url}"
  mv "${partial}" "${target}"
  size_bytes=$(stat -c%s "${target}")
  if [[ "${size_bytes}" -lt "${minimum_bytes}" ]]; then echo "file too small: ${target} ${size_bytes}" >&2; exit 1; fi
  echo "Visual-control asset ready: ${target} ${size_bytes} bytes"
  write_status "downloaded" "$(basename "${target}"):${size_bytes}"
}
download_model "https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" "${CONTROLNET_DIR}/controlnet-canny-sdxl-1.0.safetensors" 1073741824
download_model "https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" "${CONTROLNET_DIR}/controlnet-depth-sdxl-1.0.safetensors" 1073741824
download_model "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors" "${IPADAPTER_DIR}/ip-adapter-plus_sdxl_vit-h.safetensors" 536870912
download_model "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" "${CLIP_VISION_DIR}/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" 1073741824
echo "AI_FILM_VISUAL_CONTROL_VOLUME_CONTENTS"
ls -lh "${CONTROLNET_DIR}" "${IPADAPTER_DIR}" "${CLIP_VISION_DIR}"
write_status "ready" "AI_FILM_VISUAL_CONTROL_VOLUME_READY"
sleep 600'"""


def list_pods(api_key: str) -> List[Dict[str, Any]]:
    query = """
    query {
      myself {
        pods {
          id
          name
          desiredStatus
          imageName
          runtime {
            uptimeInSeconds
            ports { ip isIpPublic privatePort publicPort type }
          }
          machine { gpuDisplayName podHostId }
        }
      }
    }
    """
    data = request_graphql(api_key, query)
    return data.get("myself", {}).get("pods", [])


def create_pod(api_key: str, env: Dict[str, str], gpu_type_id: str) -> Dict[str, Any]:
    query = """
    mutation($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id
        name
        desiredStatus
        imageName
        machine { gpuDisplayName podHostId }
      }
    }
    """
    variables = {
        "input": {
            "cloudType": "SECURE",
            "gpuTypeId": gpu_type_id,
            "gpuCount": 1,
            "name": "ai-film-visual-control-volume-prep",
            "imageName": "ubuntu:22.04",
            "dockerArgs": install_command(),
            "containerDiskInGb": 20,
            "volumeInGb": 0,
            "minVcpuCount": 2,
            "minMemoryInGb": 8,
            "networkVolumeId": env["RUNPOD_NETWORK_VOLUME_ID"],
            "dataCenterId": env.get("RUNPOD_NETWORK_VOLUME_DATACENTER", "EUR-IS-1"),
            "volumeMountPath": "/runpod-volume",
            "ports": "19123/http",
        }
    }
    data = request_graphql(api_key, query, variables)
    pod = data.get("podFindAndDeployOnDemand")
    if not pod:
        raise RuntimeError("RunPod did not return a Pod")
    return pod


def terminate_pod(api_key: str, pod_id: str) -> None:
    query = """
    mutation($input: PodTerminateInput!) {
      podTerminate(input: $input)
    }
    """
    request_graphql(api_key, query, {"input": {"podId": pod_id}})


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "list", "terminate", "watch"))
    parser.add_argument("--pod-id", default="")
    parser.add_argument("--gpu-type-id", default="NVIDIA RTX A4000")
    parser.add_argument("--watch-seconds", type=int, default=900)
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    api_key = env.get("RUNPOD_API_KEY", "")
    if not api_key:
        print("RUNPOD_API_KEY is required.", file=sys.stderr)
        return 2
    if args.command == "create" and not env.get("RUNPOD_NETWORK_VOLUME_ID"):
        print("RUNPOD_NETWORK_VOLUME_ID is required.", file=sys.stderr)
        return 2

    if args.command == "list":
        print_json({"pods": list_pods(api_key)})
        return 0
    if args.command == "create":
        print_json({"pod": create_pod(api_key, env, args.gpu_type_id)})
        return 0
    if args.command == "terminate":
        if not args.pod_id:
            print("--pod-id is required.", file=sys.stderr)
            return 2
        terminate_pod(api_key, args.pod_id)
        print_json({"terminated": args.pod_id})
        return 0
    if args.command == "watch":
        deadline = time.monotonic() + max(args.watch_seconds, 1)
        while time.monotonic() < deadline:
            pods = list_pods(api_key)
            print_json({"pods": pods})
            if not pods:
                return 0
            time.sleep(20)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
