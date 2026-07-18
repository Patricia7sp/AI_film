#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOADER="${SCRIPT_DIR}/runpod_download_hf_model.sh"

if [[ ! -x "${DOWNLOADER}" ]]; then
  echo "Missing executable downloader: ${DOWNLOADER}" >&2
  echo "Run: chmod +x scripts/runpod_download_hf_model.sh" >&2
  exit 1
fi

if [[ -d "/runpod-volume" ]]; then
  VOLUME_ROOT="/runpod-volume"
elif [[ -d "/workspace" ]]; then
  VOLUME_ROOT="/workspace"
else
  echo "Could not find /runpod-volume or /workspace. Attach the RunPod Network Volume first." >&2
  exit 1
fi

CONTROLNET_DIR="${VOLUME_ROOT}/models/controlnet"
mkdir -p "${CONTROLNET_DIR}"

echo "Preparing ControlNet SDXL models in ${CONTROLNET_DIR}"

"${DOWNLOADER}" controlnet-sdxl-canny
"${DOWNLOADER}" controlnet-sdxl-depth

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
