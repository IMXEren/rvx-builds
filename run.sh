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
# uBO Lite for Prowl's browser. Prowl still works without it, so a failed download only warns.
docker compose -f "$compose_file" run --rm prowl-extensions || echo "warning: uBO Lite download failed" >&2
exec docker compose --progress plain -f "$compose_file" up --build \
  --remove-orphans --abort-on-container-exit --exit-code-from revanced
