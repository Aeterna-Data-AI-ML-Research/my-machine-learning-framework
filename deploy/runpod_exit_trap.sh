#!/usr/bin/env bash
# myMLFW cloud anti-waste — sync artifacts, wipe data, TERMINATE pod (not stop).
# Usage:
#   export POD_ID=... WORKSPACE=/workspace/siclink MAC_SYNC='rsync ...'
#   bash deploy/runpod_exit_trap.sh timeout 4h python train.py
set -euo pipefail

: "${POD_ID:?POD_ID required}"
: "${WORKSPACE:?WORKSPACE required}"

sync_artifacts_to_mac() {
  if [[ -n "${MAC_SYNC:-}" ]]; then
    bash -c "$MAC_SYNC" || true
  fi
}

trap 'sync_artifacts_to_mac; rm -rf "${WORKSPACE}/data"; command -v runpodctl >/dev/null && runpodctl remove pod "$POD_ID" || true' EXIT

exec "$@"
