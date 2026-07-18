#!/usr/bin/env python3
"""Print a standalone RunPod Pod command to prepare ControlNet models.

The temporary RunPod Pod usually does not have this repository cloned. This
helper prints one pasteable shell command that can run directly in the Pod web
terminal, detect the attached Network Volume, download SDXL Canny/Depth
ControlNet models, validate sizes, and list the final files.
"""

from __future__ import annotations

import shlex
import textwrap

INSTALL_SCRIPT = r"""
set -euo pipefail

if [[ -d "/runpod-volume" ]]; then
  VOLUME_ROOT="/runpod-volume"
elif [[ -d "/workspace" ]]; then
  VOLUME_ROOT="/workspace"
else
  echo "Could not find /runpod-volume or /workspace. Attach the Network Volume first." >&2
  exit 1
fi

CONTROLNET_DIR="${VOLUME_ROOT}/models/controlnet"
mkdir -p "${CONTROLNET_DIR}"

download_model() {
  local url="$1"
  local output="$2"
  local target="${CONTROLNET_DIR}/${output}"
  local partial="${target}.partial"
  local auth_header=()
  if [[ -n "${HF_TOKEN:-}" ]]; then
    auth_header=(-H "Authorization: Bearer ${HF_TOKEN}")
  fi
  echo "Downloading ${output} into ${target}"
  curl -fL --retry 5 --retry-delay 5 --continue-at - "${auth_header[@]}" \
    -o "${partial}" "${url}"
  mv "${partial}" "${target}"
}

download_model \
  "https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" \
  "controlnet-canny-sdxl-1.0.safetensors"

download_model \
  "https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" \
  "controlnet-depth-sdxl-1.0.safetensors"

python3 - <<'PY' "${CONTROLNET_DIR}"
from pathlib import Path
import sys

directory = Path(sys.argv[1])
required = {
    "controlnet-canny-sdxl-1.0.safetensors": 1.0,
    "controlnet-depth-sdxl-1.0.safetensors": 1.0,
}

for filename, min_gb in required.items():
    path = directory / filename
    if not path.exists():
        raise SystemExit(f"Missing required ControlNet model: {path}")
    size_gb = path.stat().st_size / 1024 / 1024 / 1024
    if size_gb < min_gb:
        raise SystemExit(f"ControlNet model too small: {path} ({size_gb:.3f} GB)")
    print(f"ControlNet ready: {path} ({size_gb:.2f} GB)")
PY

echo "AI_FILM_CONTROLNET_VOLUME_CONTENTS"
ls -lh "${CONTROLNET_DIR}"
"""


def main() -> int:
    compact_script = "\n".join(
        line.rstrip() for line in textwrap.dedent(INSTALL_SCRIPT).strip().splitlines()
    )
    print("bash -lc " + shlex.quote(compact_script))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
