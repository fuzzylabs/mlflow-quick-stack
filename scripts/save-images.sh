#!/usr/bin/env bash
# ============================================================================
# Pull and save all Docker images used by the stack for offline use
# ============================================================================
# Usage:  ./scripts/save-images.sh
#
# Images are saved as .tar files in the images/ directory.
# Transfer that folder to an air-gapped machine, then run load-images.sh
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGES_DIR="${PROJECT_DIR}/images"

# All images referenced in docker-compose.yml
# The mlflow image is built locally — build it first if it doesn't exist
IMAGES=(
  "traefik:v3.6"
  "postgres:18"
  "quay.io/minio/minio:latest"
  "quay.io/minio/mc:latest"
  "mlflow-quick-stack:latest"
)

mkdir -p "$IMAGES_DIR"

# Ensure the custom MLflow image is built
if ! docker image inspect mlflow-quick-stack:latest &>/dev/null; then
  echo "==> Building mlflow-quick-stack:latest image first..."
  docker compose build mlflow
  echo ""
fi

echo "==> Pulling and saving ${#IMAGES[@]} images to ${IMAGES_DIR}/"
echo ""

for image in "${IMAGES[@]}"; do
  # Create a safe filename: replace / : with -
  filename=$(echo "$image" | tr '/:' '--').tar
  filepath="${IMAGES_DIR}/${filename}"

  echo "--- ${image}"

  # Pull remote images (skip locally built ones)
  if [[ "$image" != mlflow-quick-stack:* ]]; then
    echo "    Pulling..."
    docker pull "$image"
  else
    echo "    Local image (skipping pull)"
  fi

  # Save to tar
  echo "    Saving → ${filename}"
  docker save -o "$filepath" "$image"

  # Show size
  size=$(du -h "$filepath" | cut -f1)
  echo "    Done (${size})"
  echo ""
done

echo "==> All images saved to ${IMAGES_DIR}/"
echo ""
ls -lh "$IMAGES_DIR"/*.tar
echo ""
echo "Transfer the images/ folder to the offline machine, then run:"
echo "  ./scripts/load-images.sh"
