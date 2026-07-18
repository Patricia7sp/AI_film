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

"${DOWNLOADER}" flux2-klein-base-4b
"${DOWNLOADER}" flux2-qwen-3-4b
"${DOWNLOADER}" flux2-vae

python3 - <<'PY' "${VOLUME_ROOT}"
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    root / "models/diffusion_models/flux-2-klein-base-4b.safetensors": 6.0,
    root / "models/text_encoders/qwen_3_4b.safetensors": 7.0,
    root / "models/vae/flux2-vae.safetensors": 0.1,
}
for path, minimum_gb in required.items():
    if not path.exists():
        raise SystemExit(f"Missing required FLUX.2 asset: {path}")
    size_gb = path.stat().st_size / 1024**3
    if size_gb < minimum_gb:
        raise SystemExit(f"FLUX.2 asset too small: {path} ({size_gb:.3f} GB)")
    print(f"FLUX.2 asset ready: {path} ({size_gb:.2f} GB)")
print("AI_FILM_FLUX2_VOLUME_READY")
PY
