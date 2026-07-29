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

declare -a LORA_SPECS=(
  "AI_FILM_STYLE_LORA_URL|style_storybook_v1.safetensors"
  "AI_FILM_ALICE_LORA_URL|char_alice_v1.safetensors"
  "AI_FILM_LUDOVICO_LORA_URL|char_ludovico_v1.safetensors"
  "AI_FILM_LORI_LORA_URL|char_lori_v1.safetensors"
  "AI_FILM_EDITH_LORA_URL|char_edith_v1.safetensors"
  "AI_FILM_MIA_LORA_URL|char_mia_v1.safetensors"
)

downloaded=0
declare -a EXPECTED_PATHS=()
for spec in "${LORA_SPECS[@]}"; do
  IFS='|' read -r url_env filename <<<"$spec"
  url="${!url_env:-}"
  if [[ -z "$url" ]]; then
    continue
  fi
  "${DOWNLOADER}" "$url" "$filename" models/loras 0.02
  EXPECTED_PATHS+=("${VOLUME_ROOT}/models/loras/${filename}")
  downloaded=$((downloaded + 1))
done

if [[ "$downloaded" -eq 0 ]]; then
  echo "Configure at least one AI_FILM_*_LORA_URL with a Hugging Face resolve URL." >&2
  exit 2
fi

python3 - "${EXPECTED_PATHS[@]}" <<'PY'
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

MAX_HEADER_BYTES = 100 * 1024 * 1024
MIN_FILE_BYTES = 20 * 1024 * 1024

for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    if not path.is_file() or path.stat().st_size < MIN_FILE_BYTES:
        raise SystemExit(f"LoRA artifact is missing or too small: {path}")
    with path.open("rb") as handle:
        prefix = handle.read(8)
        if len(prefix) != 8:
            raise SystemExit(f"Invalid safetensors prefix: {path}")
        (header_size,) = struct.unpack("<Q", prefix)
        if not 2 <= header_size <= MAX_HEADER_BYTES:
            raise SystemExit(f"Invalid safetensors header size: {path}")
        try:
            header = json.loads(handle.read(header_size))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Invalid safetensors header JSON: {path}") from exc
    tensor_entries = [
        value
        for key, value in header.items()
        if key != "__metadata__" and isinstance(value, dict)
    ]
    if not tensor_entries or not all("data_offsets" in item for item in tensor_entries):
        raise SystemExit(f"Safetensors file contains no valid tensor entries: {path}")
    print(f"LoRA ready: {path.name} ({path.stat().st_size / 1024**2:.1f} MB)")

print("AI_FILM_LORA_VOLUME_READY")
PY
