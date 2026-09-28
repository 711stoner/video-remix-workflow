#!/bin/zsh
set -a
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/.env.local" ]]; then
  source "$SCRIPT_DIR/.env.local"
fi
set +a
cd "$SCRIPT_DIR"
PORT="${VIDEO_WORKFLOW_PORT:-8788}"
if lsof -iTCP:$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  open "http://127.0.0.1:$PORT"
  exit 0
fi
nohup /usr/bin/python3 app.py > workflow-control-panel.log 2>&1 &
sleep 1
open "http://127.0.0.1:$PORT"
