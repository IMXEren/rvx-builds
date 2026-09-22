#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${COMPOSE_FILE:-docker-compose.yml}"
fonts_context="${PROWL_FONTS_CONTEXT:-$repo_root/resources}"
fonts_archive="$fonts_context/fonts.zip"
temporary_dir=""
downloaded_archive="false"

cleanup() {
  if [[ "$downloaded_archive" == "true" ]]; then
    rm -f "$fonts_archive"
  fi
  if [[ -n "$temporary_dir" ]]; then
    rm -rf "$temporary_dir"
  fi
}
trap cleanup EXIT

font_size=0
if [[ -f "$fonts_archive" ]]; then
  font_size="$(wc -c < "$fonts_archive")"
fi

if (( font_size < 1000000 )); then
  command -v gh >/dev/null || {
    echo "gh is required to obtain the private fingerprint fonts" >&2
    exit 1
  }
  command -v git-lfs >/dev/null || {
    echo "Git LFS is required to obtain the private fingerprint fonts" >&2
    exit 1
  }
  gh auth status >/dev/null
  git lfs version >/dev/null

  temporary_dir="$(mktemp -d)"
  gh repo clone IMXEren/extra-fonts "$temporary_dir/extra-fonts" -- --depth 1
  mkdir -p "$fonts_context"
  cp "$temporary_dir/extra-fonts/fonts.zip" "$fonts_archive"
  downloaded_archive="true"
fi

if (( $(wc -c < "$fonts_archive") < 1000000 )); then
  echo "fonts.zip is only a Git LFS pointer: $fonts_archive" >&2
  exit 1
fi

cd "$repo_root"
PROWL_FONTS_CONTEXT="$fonts_context" docker compose -f "$compose_file" build prowl
