#!/usr/bin/env bash
# Stops and removes the FinAlly container. The named data volume is left intact.
# Usage: scripts/stop_mac.sh
set -euo pipefail

CONTAINER_NAME="finally"

if [ "$(docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}')" != "$CONTAINER_NAME" ]; then
    echo "FinAlly is not running."
    exit 0
fi

docker rm -f "$CONTAINER_NAME" >/dev/null
echo "FinAlly stopped. Data volume 'finally-data' was preserved."
