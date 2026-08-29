#!/usr/bin/env bash
# Builds (if needed) and runs the FinAlly Docker container.
# Usage: scripts/start_mac.sh [--build]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="finally"
CONTAINER_NAME="finally"
PORT=8000

cd "$REPO_ROOT"

if [ ! -f .env ]; then
    echo "No .env file found. Copy .env.example to .env and add your OPENROUTER_API_KEY."
    exit 1
fi

if [ "${1:-}" = "--build" ] || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "Building Docker image..."
    docker build -t "$IMAGE_NAME" .
fi

if [ "$(docker ps --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}')" = "$CONTAINER_NAME" ]; then
    echo "FinAlly is already running at http://localhost:${PORT}"
    exit 0
fi

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

is_container_running() {
    [ "$(docker ps --filter "name=^/${CONTAINER_NAME}$" --filter "status=running" --format '{{.Names}}')" = "$CONTAINER_NAME" ]
}

echo "Starting FinAlly container..."
if ! docker run -d --name "$CONTAINER_NAME" -v finally-data:/app/db -p "${PORT}:8000" --env-file .env "$IMAGE_NAME" >/dev/null; then
    echo "docker run failed -- see the error above."
    if command -v lsof >/dev/null 2>&1 && lsof -i ":${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "Port ${PORT} is already in use by another process. Stop it and try again."
    fi
    exit 1
fi

sleep 1
if ! is_container_running; then
    echo "FinAlly container exited immediately after starting. Check: docker logs ${CONTAINER_NAME}"
    exit 1
fi

echo "Waiting for FinAlly to become healthy..."
deadline=$((SECONDS + 60))
healthy=false
while [ $SECONDS -lt $deadline ]; do
    if ! is_container_running; then
        echo "FinAlly container stopped while waiting for it to become healthy. Check: docker logs ${CONTAINER_NAME}"
        exit 1
    fi
    if curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1; then
        healthy=true
        break
    fi
    sleep 2
done

if [ "$healthy" != true ]; then
    echo "FinAlly did not become healthy in time. Check logs with: docker logs ${CONTAINER_NAME}"
    exit 1
fi

echo "FinAlly is running at http://localhost:${PORT}"
if command -v open >/dev/null 2>&1; then
    open "http://localhost:${PORT}"
fi
