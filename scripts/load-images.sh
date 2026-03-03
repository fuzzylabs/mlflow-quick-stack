#!/usr/bin/env bash
# ============================================================================
# Load and tag Docker images from saved .tar files for offline use
# ============================================================================
# Usage:  ./scripts/load-images.sh
#
# Loads all .tar files from the images/ directory into the local Docker daemon
# so that `docker compose up -d` works without network access.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGES_DIR="${PROJECT_DIR}/images"

if [[ ! -d "$IMAGES_DIR" ]] || [[ -z "$(ls -A "$IMAGES_DIR"/*.tar 2>/dev/null)" ]]; then
  echo "Error: No .tar files found in ${IMAGES_DIR}/"
  echo "Run ./scripts/save-images.sh first (while online)."
  exit 1
fi

echo "==> Loading images from ${IMAGES_DIR}/"
echo ""

for tarfile in "$IMAGES_DIR"/*.tar; do
  filename=$(basename "$tarfile")
  echo "--- Loading ${filename}"
  docker load -i "$tarfile"
  echo ""
done

echo "==> All images loaded. Verifying..."
echo ""

# Expected images from docker-compose.yml
EXPECTED=(
  "traefik:v3.6"
  "postgres:18"
  "quay.io/minio/minio:latest"
  "quay.io/minio/mc:latest"
  "localai/localai:latest-cpu"
  "ghcr.io/open-webui/open-webui:main"
  "mlflow-quick-stack:latest"
)

all_ok=true
for image in "${EXPECTED[@]}"; do
  if docker image inspect "$image" &>/dev/null; then
    echo "  ✓ ${image}"
  else
    echo "  ✗ ${image} (MISSING)"
    all_ok=false
  fi
done

echo ""
if $all_ok; then
  echo "All images present. Ready to run:"
  echo "  docker compose up -d"
else
  echo "Warning: Some images are missing. Check the output above."
  exit 1
fi
