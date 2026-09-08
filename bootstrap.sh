#!/bin/sh
# bootstraps entry point. Thin shim: ensures Python 3 exists, then execs the
# Python engine. All real logic lives in bootstrap/ (stdlib-only).
# Exit codes: 0 success, 2 unsupported platform, 3 invalid context,
# 4 component failure(s), 5 unmanaged-file conflict, 1 usage/other error.
set -eu

resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  # Minimal-shell fallback for fresh Ubuntu where python3 is absent but apt
  # works (root). The Ubuntu adapter owns installing python3 properly; this
  # shim only covers the pre-engine stage.
  if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
    apt-get update -qq >/dev/null 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 >/dev/null 2>&1 || true
    command -v python3 && return 0
  fi
  return 1
}

PY="$(resolve_python)" || {
  echo "bootstrap: python3 is required but was not found and could not be" >&2
  echo "  installed automatically. Install python3 and rerun." >&2
  exit 1
}

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$PY" "$HERE/bootstrap/__main__.py" "$@"