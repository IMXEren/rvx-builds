#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

read_dotenv() {
  local key="$1"
  local line
  local value

  [[ -f "$repo_root/.env" ]] || return 1
  while IFS= read -r line; do
    if [[ "$line" == "$key="* ]]; then
      value="${line#*=}"
      value="${value%$'\r'}"
      value="${value#\"}"
      value="${value%\"}"
      printf '%s' "$value"
      return 0
    fi
  done < "$repo_root/.env"
  return 1
}

if [[ ! -v PROWL_IMAGE ]] && dotenv_value="$(read_dotenv PROWL_IMAGE)"; then
  PROWL_IMAGE="$dotenv_value"
fi
if [[ ! -v PROWL_BUILD_CONTEXT ]] && dotenv_value="$(read_dotenv PROWL_BUILD_CONTEXT)"; then
  PROWL_BUILD_CONTEXT="$dotenv_value"
fi
if [[ ! -v PROWL_FONTS_CONTEXT ]] && dotenv_value="$(read_dotenv PROWL_FONTS_CONTEXT)"; then
  PROWL_FONTS_CONTEXT="$dotenv_value"
fi
if [[ ! -v PROWL_GHCR_TOKEN ]]; then
  if dotenv_value="$(read_dotenv PROWL_GHCR_TOKEN)"; then
    PROWL_GHCR_TOKEN="$dotenv_value"
  elif dotenv_value="$(read_dotenv GITHUB_PAT)"; then
    PROWL_GHCR_TOKEN="$dotenv_value"
  fi
fi

# The pinned Prowl ref lives in one file so a version bump is a one-line change.
# PROWL_REF overrides the ref for a one-off run, and PROWL_BUILD_CONTEXT
# overrides the whole source location, which also covers a local checkout.
pinned_ref="$(head -n1 "$repo_root/.prowl-version" 2>/dev/null || true)"
[[ -n "$pinned_ref" ]] || pinned_ref="main"

source_image="${PROWL_IMAGE:-ghcr.io/imxeren/prowl:latest}"
build_context="${PROWL_BUILD_CONTEXT:-https://github.com/IMXEren/prowl.git#${PROWL_REF:-$pinned_ref}}"
fonts_context="${PROWL_FONTS_CONTEXT:-}"
target_image="prowl:local"

if [[ -n "${PROWL_GHCR_TOKEN:-}" ]]; then
  if ! printf '%s' "$PROWL_GHCR_TOKEN" | docker login ghcr.io \
    --username "${PROWL_GHCR_USERNAME:-IMXEren}" --password-stdin; then
    echo "Prowl registry login failed; continuing with the public source fallback." >&2
  fi
fi

if docker pull "$source_image"; then
  docker tag "$source_image" "$target_image"
  exit 0
fi

echo "Unable to pull $source_image; building $target_image from $build_context." >&2
cd "$repo_root"

build_args=(--progress plain --tag "$target_image")
if [[ -n "$fonts_context" ]]; then
  if [[ ! -d "$fonts_context" ]]; then
    echo "PROWL_FONTS_CONTEXT is not a directory: $fonts_context" >&2
    exit 1
  fi
  if [[ -f "$fonts_context/fonts.zip" ]]; then
    build_args+=(--build-context "windows_fonts=$fonts_context")
    echo "Installing the extra Windows font set from $fonts_context." >&2
  else
    echo "No fonts.zip in $fonts_context; building without the extra Windows font set." >&2
  fi
fi

docker build "${build_args[@]}" "$build_context"
