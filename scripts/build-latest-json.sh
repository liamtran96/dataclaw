#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?VERSION is required}"
: "${RELEASE_TAG:?RELEASE_TAG is required}"
: "${ARM64_TARBALL:?ARM64_TARBALL is required}"
: "${ARM64_SIG:?ARM64_SIG is required}"

require_file_nonempty() {
  local path="$1"
  local label="$2"
  if [[ ! -s "$path" ]]; then
    echo "$label is missing or empty: $path" >&2
    exit 1
  fi
}

require_file_nonempty "$ARM64_TARBALL" "ARM64_TARBALL"
require_file_nonempty "$ARM64_SIG" "ARM64_SIG"
if [[ -n "${X86_TARBALL:-}" || -n "${X86_SIG:-}" ]]; then
  require_file_nonempty "${X86_TARBALL:-}" "X86_TARBALL"
  require_file_nonempty "${X86_SIG:-}" "X86_SIG"
fi

export ARM64_SIGNATURE
export X86_SIGNATURE
export ARM64_ASSET
export X86_ASSET

ARM64_SIGNATURE="$(cat "$ARM64_SIG")"
ARM64_ASSET="$(basename "$ARM64_TARBALL")"
X86_SIGNATURE=""
X86_ASSET=""
if [[ -n "${X86_TARBALL:-}" && -n "${X86_SIG:-}" ]]; then
  X86_SIGNATURE="$(cat "$X86_SIG")"
  X86_ASSET="$(basename "$X86_TARBALL")"
fi

python - <<'PY'
import json
import os
from datetime import datetime, timezone

version = os.environ["VERSION"]
if version.startswith("v"):
    version = version[1:]
release_tag = os.environ["RELEASE_TAG"]
pub_date = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
base_url = f"https://github.com/peteromallet/dataclaw/releases/download/{release_tag}"

platforms = {
    "darwin-aarch64": {
        "signature": os.environ["ARM64_SIGNATURE"],
        "url": f"{base_url}/{os.environ['ARM64_ASSET']}",
    },
}

if os.environ.get("X86_ASSET") and os.environ.get("X86_SIGNATURE"):
    platforms["darwin-x86_64"] = {
        "signature": os.environ["X86_SIGNATURE"],
        "url": f"{base_url}/{os.environ['X86_ASSET']}",
    }

payload = {
    "version": version,
    "pub_date": pub_date,
    "notes": os.environ.get("NOTES", ""),
    "platforms": platforms,
}

print(json.dumps(payload, indent=2, sort_keys=True))
PY
