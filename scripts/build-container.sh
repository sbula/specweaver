#!/bin/sh
# Build the SpecWeaver container image.
# Usage: ./scripts/build-container.sh [tag]
#   tag  — image tag (default: "specweaver:latest")
set -e

TAG="${1:-specweaver:latest}"

# Detect container engine (prefer podman)
if command -v podman >/dev/null 2>&1; then
    ENGINE=podman
elif command -v docker >/dev/null 2>&1; then
    ENGINE=docker
else
    echo "Error: neither podman nor docker found in PATH" >&2
    exit 1
fi

echo "Building $TAG with $ENGINE ..."
$ENGINE build -t "$TAG" -f Containerfile .
echo "Done. Run with:"
echo "  $ENGINE run --env-file .env -v ./my-project:/projects -p 8000:8000 $TAG"
