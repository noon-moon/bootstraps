#!/bin/sh
# Deprecated entry point — replaced by the bootstraps engine.
# Kept so existing clones/notes referencing mac/setup.sh still get the new
# flow with a sensible default. Remove in a future release.
set -eu

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

printf 'NOTICE: mac/setup.sh is deprecated.\n'
printf '  Use: %s/../bootstrap.sh (interactive) or --headless --profile <p>\n' "$HERE"
printf '  Running the new flow now with the "personal" profile preview...\n\n'

if [ "${BOOTSTRAPS_DEPRECATION_EXEC:-0}" = "1" ]; then
  exec "$HERE/../bootstrap.sh" "$@"
fi
exec "$HERE/../bootstrap.sh" --dry-run --profile personal "$@"