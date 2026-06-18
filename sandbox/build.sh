#!/usr/bin/env bash
# DataMind Sandbox Builder
# Build the Docker sandbox image for secure Python code execution
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="${IMAGE_NAME:-datamind-sandbox}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "==> Building DataMind Sandbox image: ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  --platform linux/amd64 \
  -f "${SCRIPT_DIR}/Dockerfile" \
  "${SCRIPT_DIR}"

echo "==> Verify image..."
docker run --rm "${IMAGE_NAME}:${IMAGE_TAG}" python -c "
import pandas, numpy, scipy, matplotlib
print(f'pandas={pandas.__version__} numpy={numpy.__version__} scipy={scipy.__version__}')
print('Sandbox image OK')
"

echo "==> Done! Image ${IMAGE_NAME}:${IMAGE_TAG} ready"
