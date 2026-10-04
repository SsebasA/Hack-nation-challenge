#!/usr/bin/env bash
# Container entrypoint (Railway or any Docker host): sparklab.api + Omnigent in one service.
#
# The code lives in the image (/app/backend); the lab's records live on the volume (SPARKLAB_HOME, default
# /data/lab): board, ledger, prereg (a git repository of its own), NHANES data and studies. Omnigent keeps its
# sessions in OMNIGENT_DATA_DIR (/data/omnigent). Safe to run on every start: each step is skipped once done.
set -euo pipefail

export SPARKLAB_HOME="${SPARKLAB_HOME:-/data/lab}"
export SPARK_API_HOST="${SPARK_API_HOST:-0.0.0.0}"
export SPARK_API_PORT="${PORT:-${SPARK_API_PORT:-8787}}"   # Railway sets PORT
LAB="$SPARKLAB_HOME"
APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # backend/ (/app/backend in the image)
log() { echo "[start] $*"; }

mkdir -p "$LAB/board" "$LAB/ledger" "$LAB/prereg" "$LAB/studies" "${OMNIGENT_DATA_DIR:-/data/omnigent}"

# 1. Board: the repository is the source of truth (citations, seeded control), so refresh it on every start.
cp "$APP"/board/*.json "$LAB/board/"

# 2. Pre-registrations are git-committed (hash + commit): the hosted lab gets its own repository.
if [ ! -d "$LAB/.git" ]; then
  git -C "$LAB" init -q
  git -C "$LAB" -c user.name=sparklab -c user.email=sparklab@localhost commit -q --allow-empty -m "hosted SPARK lab"
  log "initialised the lab repository in $LAB"
fi

# 3. Data, once (a few minutes on the first start). Cycle J is processed; cycle I is zipped and sealed, not processed.
if [ ! -f "$LAB/data/processed/nhanes_J.pkl" ]; then
  log "preparing discovery data (NHANES 2017-2018)..."
  python -m sparklab.data --cycle J || log "WARNING: discovery data failed; retried on the next start"
fi
if [ ! -f "$LAB/data/sealed/nhanes_I.zip" ]; then
  log "sealing the hold-out (NHANES 2015-2016)..."
  python -m sparklab.data --cycle I --seal --by deploy || log "WARNING: sealing failed; retried on the next start"
fi

# 4. Model credentials for the agents. Omnigent's Claude executor does not pass ANTHROPIC_API_KEY through the
#    environment; it reads the key from the `auth:` block of its global config (what `omnigent setup` writes).
#    Written inside the container only, never to the image or the volume. CLAUDE_CODE_OAUTH_TOKEN, if set instead,
#    is forwarded by Omnigent as is.
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  CFG_DIR="${OMNIGENT_CONFIG_HOME:-$HOME/.omnigent}"
  mkdir -p "$CFG_DIR"
  ( umask 077; python - "$CFG_DIR/config.yaml" <<'PY'
import os, sys, yaml
path = sys.argv[1]
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
cfg["auth"] = {"type": "api_key", "api_key": os.environ["ANTHROPIC_API_KEY"]}
with open(path, "w") as f:
    yaml.safe_dump(cfg, f)
PY
  )
  log "Omnigent will use ANTHROPIC_API_KEY for the agents"
elif [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  log "WARNING: neither ANTHROPIC_API_KEY nor CLAUDE_CODE_OAUTH_TOKEN is set; the agents cannot call the model"
fi

# 5. Omnigent (server on 127.0.0.1:6767 + this container as its host), in the background.
log "starting Omnigent..."
if ! omnigent start --no-open --non-interactive; then
  log "WARNING: Omnigent did not start; the API runs without agents (see the output above)"
fi

# 6. The API in the foreground: Railway routes $PORT to it and health-checks /health.
log "starting the SPARK Lab API on $SPARK_API_HOST:$SPARK_API_PORT (lab: $LAB)"
cd "$APP"
exec python -m sparklab.api
