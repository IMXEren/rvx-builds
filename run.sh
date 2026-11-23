#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_root"

if [[ -t 1 ]]; then
  export COMPOSE_TTY=true
else
  export COMPOSE_TTY=false
fi

scripts/prepare-prowl.sh

# Shared by Prowl and the builder for reserved tabs.
if [[ ! -s .prowl-cdp-token ]]; then
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n' > .prowl-cdp-token
fi

compose_file="${COMPOSE_FILE:-docker-compose.yml}"
exec docker compose --progress plain -f "$compose_file" up --build \
  --remove-orphans --abort-on-container-exit --exit-code-from revanced
