#!/usr/bin/env bash
# Run the contest CLI image. Prefer: make cli CMD='…'  or  ./deploy/run-cli.sh version
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export MYMLFW_WORK="${MYMLFW_WORK:-$ROOT}"
export MYMLFW_UID="${MYMLFW_UID:-$(id -u)}"
export MYMLFW_GID="${MYMLFW_GID:-$(id -g)}"

args=()
if [[ $# -gt 0 ]]; then
  args=("$@")
elif [[ -n "${MYMLFW_CLI_CMD:-}" ]]; then
  # Whitespace split only — never eval (avoids Make CMD shell metacharacters).
  # shellcheck disable=SC2206
  args=($MYMLFW_CLI_CMD)
else
  args=(version)
fi

exec docker compose -f deploy/docker-compose.yml --profile cli run --rm cli "${args[@]}"
