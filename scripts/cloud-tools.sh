#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="vixenone-cloud-tools:latest"

# Build the image if missing
if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Image '${IMAGE_NAME}' not found. Building..."
  docker build -t "${IMAGE_NAME}" -f "${REPO_ROOT}/infra/docker/tools/Dockerfile" "${REPO_ROOT}"
fi

DOCKER_FLAGS=("-i")
if [ -t 0 ] && [ -t 1 ]; then
  DOCKER_FLAGS+=("-t")
fi

if [ "$#" -eq 0 ]; then
  set -- /bin/bash
fi

exec docker run --rm "${DOCKER_FLAGS[@]}" \
  -v "${REPO_ROOT}:/workspace" \
  -w /workspace \
  -v vixenone_gcloud_config:/root/.config/gcloud \
  -v vixenone_firebase_config:/root/.config/configstore \
  -v vixenone_firebase_home:/root/.firebase \
  "${IMAGE_NAME}" "$@"
