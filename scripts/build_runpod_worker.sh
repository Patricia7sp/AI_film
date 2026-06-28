#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <registry/image:tag>"
  echo "Example: $0 seu_usuario/comfyui-ai-film-pipeline:latest"
  exit 2
fi

IMAGE="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKER_DIR="$ROOT_DIR/runpod_worker"

if command -v docker >/dev/null 2>&1; then
  DOCKER_BIN="docker"
elif [[ -x "/Applications/Docker.app/Contents/Resources/bin/docker" ]]; then
  DOCKER_BIN="/Applications/Docker.app/Contents/Resources/bin/docker"
else
  echo "Docker CLI not found."
  exit 1
fi

"$DOCKER_BIN" info >/dev/null

cd "$WORKER_DIR"
"$DOCKER_BIN" build -t "$IMAGE" .
"$DOCKER_BIN" push "$IMAGE"

echo "Pushed $IMAGE"
