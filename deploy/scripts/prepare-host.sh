#!/bin/sh
# prepare-host.sh — minimal wrapper (TASK-44.4 stage D): validates the
# root-owned source, renders runtime config from the context + deployment
# settings, and runs compose build. Compose up is a separate explicit
# stage (parent invokes Tailscale Serve afterwards).
#
# Usage (root on the host):
#   prepare-host.sh --expect-rev <sha> [--deployment /path/deployment.json]
#
# Paths are the fixed deployment contract:
#   source   /opt/bootstraps-release
#   context  /var/lib/bootstraps/context
#   env      /etc/bootstraps/runtime.env
#   rendered /var/lib/bootstraps/runtime-config
set -eu

SOURCE=/opt/bootstraps-release
CONTEXT=/var/lib/bootstraps/context
DEPLOYMENT=${DEPLOYMENT:-/var/lib/bootstraps/context/deployment.json}
OUT=/var/lib/bootstraps/runtime-config
FIXTURE=/home/agent/dev/agent-workspace/backlog-fixture
ENV=/etc/bootstraps/runtime.env

EXPECT_REV=""
while [ $# -gt 0 ]; do
  case "$1" in
    --expect-rev) EXPECT_REV="$2"; shift 2 ;;
    --deployment) DEPLOYMENT="$2"; shift 2 ;;
    --help|-h) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done
[ -n "$EXPECT_REV" ] || { echo "FATAL: --expect-rev <sha> is required (fail-closed source verification)" >&2; exit 1; }

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

echo "[prepare] stage: validate"
python3 "$SCRIPT_DIR/provision-host.py" validate \
  --source "$SOURCE" --context "$CONTEXT" --expect-rev "$EXPECT_REV"

echo "[prepare] stage: render-runtime-config"
python3 "$SCRIPT_DIR/render-runtime-config.py" \
  --context "$CONTEXT" --deployment "$DEPLOYMENT" --source "$SOURCE" \
  --out "$OUT" --backlog-fixture "$FIXTURE"

echo "[prepare] stage: compose build (pinned images from root checkout)"
docker compose --env-file "$ENV" \
  -f "$SOURCE/deploy/docker-compose.yml" \
  -f "$SOURCE/deploy/compose.gate.yml" \
  -p t444host build

echo "[prepare] done. Parent: start/recreate and verify BEFORE repointing Serve:"
echo "  docker compose --env-file $ENV -f $SOURCE/deploy/docker-compose.yml -f $SOURCE/deploy/compose.gate.yml -p t444host up -d --wait --force-recreate"
echo "  python3 $SCRIPT_DIR/verify-host.py --source $SOURCE --env-file $ENV"
echo "  Complete the RUNBOOK gate protocol checks; only after all checks pass:"
echo "  tailscale serve --bg --https=443 http://127.0.0.1:17420"
echo "  tailscale serve --bg --https=8443 http://127.0.0.1:17443"
echo "  Reconfirm access from the actual allowed and denied tailnet devices."
