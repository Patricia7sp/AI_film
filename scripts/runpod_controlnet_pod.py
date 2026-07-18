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


def audit_command() -> str:
    return r"""bash -lc 'set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends coreutils python3
rm -rf /var/lib/apt/lists/*
if [[ -d "/runpod-volume" ]]; then VOLUME_ROOT="/runpod-volume"; elif [[ -d "/workspace" ]]; then VOLUME_ROOT="/workspace"; else echo "missing RunPod volume" >&2; exit 1; fi
STATUS_DIR="/tmp/ai-film-status"
mkdir -p "${STATUS_DIR}"
python3 -m http.server 19123 --bind 0.0.0.0 --directory "${STATUS_DIR}" >/tmp/ai-film-status-server.log 2>&1 &
capacity_bytes=$(df -B1 --output=size "${VOLUME_ROOT}" | tail -n 1 | tr -d " ")
available_bytes=$(df -B1 --output=avail "${VOLUME_ROOT}" | tail -n 1 | tr -d " ")
models_bytes=0
if [[ -d "${VOLUME_ROOT}/models" ]]; then models_bytes=$(du -sb "${VOLUME_ROOT}/models" | cut -f 1); fi
python3 - "${STATUS_DIR}/status.json" "${VOLUME_ROOT}" "${capacity_bytes}" "${available_bytes}" "${models_bytes}" <<"PY"
import json
import sys

target, root, capacity, available, models = sys.argv[1:]
with open(target, "w", encoding="utf-8") as handle:
    json.dump(
        {
            "status": "ready",
            "detail": "AI_FILM_VOLUME_AUDIT_READY",
            "volume_root": root,
            "capacity_bytes": int(capacity),
            "available_bytes": int(available),
            "models_bytes": int(models),
        },
        handle,
    )
PY
find "${VOLUME_ROOT}/models" -maxdepth 2 -type f -printf "%s %p\n" 2>/dev/null | sort -nr > "${STATUS_DIR}/models.txt" || true
sleep 600'"""


def qwen2511_install_command() -> str:
    return r"""bash -lc 'set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl coreutils python3
rm -rf /var/lib/apt/lists/*
if [[ -d "/runpod-volume" ]]; then VOLUME_ROOT="/runpod-volume"; elif [[ -d "/workspace" ]]; then VOLUME_ROOT="/workspace"; else echo "missing RunPod volume" >&2; exit 1; fi
DIFFUSION_MODELS_DIR="${VOLUME_ROOT}/models/diffusion_models"
TEXT_ENCODERS_DIR="${VOLUME_ROOT}/models/text_encoders"
VAE_DIR="${VOLUME_ROOT}/models/vae"
STATUS_DIR="/tmp/ai-film-status"
mkdir -p "${STATUS_DIR}" "${DIFFUSION_MODELS_DIR}" "${TEXT_ENCODERS_DIR}" "${VAE_DIR}"
write_status() {
  status="$1"; detail="$2"
  printf "{\"status\":\"%s\",\"detail\":\"%s\",\"volume_root\":\"%s\"}\n" "${status}" "${detail}" "${VOLUME_ROOT}" > "${STATUS_DIR}/status.json"
}
handle_error() {
  write_status "failed" "Qwen 2511 download command failed"
  sleep 600
}
trap handle_error ERR
python3 -m http.server 19123 --bind 0.0.0.0 --directory "${STATUS_DIR}" >/tmp/ai-film-status-server.log 2>&1 &
download_model() {
  url="$1"; target="$2"; minimum_bytes="$3"; expected_sha256="$4"; partial="${target}.partial"
  if [[ -f "${target}" ]] && [[ "$(stat -c%s "${target}")" -ge "${minimum_bytes}" ]] && [[ "$(sha256sum "${target}" | cut -d " " -f 1)" == "${expected_sha256}" ]]; then
    echo "Already ready: ${target}"
    return
  fi
  auth_args=()
  if [[ -n "${HF_TOKEN:-}" ]]; then auth_args=(-H "Authorization: Bearer ${HF_TOKEN}"); fi
  write_status "downloading" "$(basename "${target}")"
  curl -fL --retry 5 --retry-delay 5 --continue-at - "${auth_args[@]}" -o "${partial}" "${url}"
  size_bytes=$(stat -c%s "${partial}")
  if [[ "${size_bytes}" -lt "${minimum_bytes}" ]]; then echo "file too small: ${partial} ${size_bytes}" >&2; exit 1; fi
  actual_sha256=$(sha256sum "${partial}" | cut -d " " -f 1)
  if [[ "${actual_sha256}" != "${expected_sha256}" ]]; then echo "checksum mismatch: ${partial} ${actual_sha256}" >&2; rm -f "${partial}"; exit 1; fi
  mv "${partial}" "${target}"
  write_status "downloaded" "$(basename "${target}"):${size_bytes}"
}
download_model "https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors" "${DIFFUSION_MODELS_DIR}/qwen_image_edit_2511_fp8mixed.safetensors" 20533762817 "c9fdc158e46d3b61ef75f21ae866ca2fe808bf4a53643120d1c1e87c19280a4e"
download_model "https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" "${TEXT_ENCODERS_DIR}/qwen_2.5_vl_7b_fp8_scaled.safetensors" 9384670680 "cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4"
download_model "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" "${VAE_DIR}/qwen_image_vae.safetensors" 253806246 "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f"
sha256sum \
  "${DIFFUSION_MODELS_DIR}/qwen_image_edit_2511_fp8mixed.safetensors" \
  "${TEXT_ENCODERS_DIR}/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
  "${VAE_DIR}/qwen_image_vae.safetensors" \
  > "${STATUS_DIR}/qwen2511-checksums.txt"
write_status "ready" "AI_FILM_QWEN_IMAGE_EDIT_2511_VOLUME_READY"
sleep 600'"""


def install_command() -> str:
    return r"""bash -lc 'set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl coreutils python3
rm -rf /var/lib/apt/lists/*
if [[ -d "/runpod-volume" ]]; then VOLUME_ROOT="/runpod-volume"; elif [[ -d "/workspace" ]]; then VOLUME_ROOT="/workspace"; else echo "missing RunPod volume" >&2; exit 1; fi
CONTROLNET_DIR="${VOLUME_ROOT}/models/controlnet"
IPADAPTER_DIR="${VOLUME_ROOT}/models/ipadapter"
CLIP_VISION_DIR="${VOLUME_ROOT}/models/clip_vision"
DIFFUSION_MODELS_DIR="${VOLUME_ROOT}/models/diffusion_models"
TEXT_ENCODERS_DIR="${VOLUME_ROOT}/models/text_encoders"
VAE_DIR="${VOLUME_ROOT}/models/vae"
STATUS_DIR="/tmp/ai-film-status"
mkdir -p "${STATUS_DIR}"
write_status() {
  status="$1"; detail="$2"
  printf "{\"status\":\"%s\",\"detail\":\"%s\",\"volume_root\":\"%s\"}\n" "${status}" "${detail}" "${VOLUME_ROOT}" > "${STATUS_DIR}/status.json"
}
handle_error() {
  write_status "failed" "download command failed"
  sleep 600
}
trap handle_error ERR
write_status "starting" "installing dependencies"
python3 -m http.server 19123 --bind 0.0.0.0 --directory "${STATUS_DIR}" >/tmp/ai-film-status-server.log 2>&1 &
mkdir -p "${CONTROLNET_DIR}" "${IPADAPTER_DIR}" "${CLIP_VISION_DIR}" "${DIFFUSION_MODELS_DIR}" "${TEXT_ENCODERS_DIR}" "${VAE_DIR}"
download_model() {
  url="$1"; target="$2"; minimum_bytes="$3"; expected_sha256="${4:-}"; partial="${target}.partial"
  if [[ -f "${target}" ]] && [[ "$(stat -c%s "${target}")" -ge "${minimum_bytes}" ]]; then
    if [[ -z "${expected_sha256}" ]] || [[ "$(sha256sum "${target}" | cut -d " " -f 1)" == "${expected_sha256}" ]]; then
      echo "Already ready: ${target}"
      return
    fi
    echo "Checksum mismatch, replacing: ${target}" >&2
    rm -f "${target}" "${partial}"
  fi
  auth_args=()
  if [[ -n "${HF_TOKEN:-}" ]]; then auth_args=(-H "Authorization: Bearer ${HF_TOKEN}"); fi
  echo "Downloading into ${target}"
  write_status "downloading" "$(basename "${target}")"
  curl -fL --retry 5 --retry-delay 5 --continue-at - "${auth_args[@]}" -o "${partial}" "${url}"
  mv "${partial}" "${target}"
  size_bytes=$(stat -c%s "${target}")
  if [[ "${size_bytes}" -lt "${minimum_bytes}" ]]; then echo "file too small: ${target} ${size_bytes}" >&2; exit 1; fi
  if [[ -n "${expected_sha256}" ]]; then
    actual_sha256=$(sha256sum "${target}" | cut -d " " -f 1)
    if [[ "${actual_sha256}" != "${expected_sha256}" ]]; then
      echo "checksum mismatch: ${target} ${actual_sha256}" >&2
      rm -f "${target}"
      exit 1
    fi
  fi
  echo "Visual-control asset ready: ${target} ${size_bytes} bytes"
  write_status "downloaded" "$(basename "${target}"):${size_bytes}"
}
download_model "https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" "${CONTROLNET_DIR}/controlnet-canny-sdxl-1.0.safetensors" 1073741824
download_model "https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" "${CONTROLNET_DIR}/controlnet-depth-sdxl-1.0.safetensors" 1073741824
download_model "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors" "${IPADAPTER_DIR}/ip-adapter-plus_sdxl_vit-h.safetensors" 536870912
download_model "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" "${CLIP_VISION_DIR}/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" 1073741824
download_model "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors" "${DIFFUSION_MODELS_DIR}/flux-2-klein-base-4b.safetensors" 6442450944 "9c5fed22b76baea749d88fc2abe3ad53245e7b21a0d353a762665eea00043b92"
download_model "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors" "${TEXT_ENCODERS_DIR}/qwen_3_4b.safetensors" 7516192768 "6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a"
download_model "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors" "${VAE_DIR}/flux2-vae.safetensors" 107374182 "d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5"
echo "AI_FILM_VISUAL_CONTROL_VOLUME_CONTENTS"
ls -lh "${CONTROLNET_DIR}" "${IPADAPTER_DIR}" "${CLIP_VISION_DIR}" "${DIFFUSION_MODELS_DIR}" "${TEXT_ENCODERS_DIR}" "${VAE_DIR}"
sha256sum \
  "${DIFFUSION_MODELS_DIR}/flux-2-klein-base-4b.safetensors" \
  "${TEXT_ENCODERS_DIR}/qwen_3_4b.safetensors" \
  "${VAE_DIR}/flux2-vae.safetensors" \
  > "${STATUS_DIR}/flux2-checksums.txt"
write_status "ready" "AI_FILM_VISUAL_CONTROL_AND_FLUX2_VOLUME_READY"
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


def create_pod(
    api_key: str,
    env: Dict[str, str],
    gpu_type_id: str,
    mode: str,
) -> Dict[str, Any]:
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
            "name": f"ai-film-volume-{mode}",
            "imageName": "ubuntu:22.04",
            "dockerArgs": (
                audit_command()
                if mode == "audit"
                else (
                    qwen2511_install_command()
                    if mode == "qwen2511"
                    else install_command()
                )
            ),
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
    parser.add_argument(
        "--mode",
        choices=("prepare", "audit", "qwen2511"),
        default="prepare",
        help="Prepare assets or only audit network-volume capacity and contents.",
    )
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
        print_json({"pod": create_pod(api_key, env, args.gpu_type_id, args.mode)})
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
