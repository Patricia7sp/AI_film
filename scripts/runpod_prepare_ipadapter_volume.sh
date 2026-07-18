#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOADER="${SCRIPT_DIR}/runpod_download_hf_model.sh"

if [[ -d /runpod-volume ]]; then
  VOLUME_ROOT=/runpod-volume
elif [[ -d /workspace ]]; then
  VOLUME_ROOT=/workspace
else
  echo "Attach a RunPod Network Volume at /runpod-volume or /workspace." >&2
  exit 1
fi

"${DOWNLOADER}" ipadapter-plus-sdxl
"${DOWNLOADER}" clip-vision-vit-h

python3 - <<'PY' "${VOLUME_ROOT}"
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    root / "models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors": 0.5,
    root / "models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors": 1.0,
}
for path, minimum_gb in required.items():
    if not path.exists():
        raise SystemExit(f"Missing required IP-Adapter asset: {path}")
    size_gb = path.stat().st_size / 1024**3
    if size_gb < minimum_gb:
        raise SystemExit(f"IP-Adapter asset too small: {path} ({size_gb:.3f} GB)")
    print(f"IP-Adapter asset ready: {path} ({size_gb:.2f} GB)")
print("AI_FILM_IPADAPTER_VOLUME_READY")
PY
