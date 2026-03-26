#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="$(cd -- "$ROOT_DIR/../.." && pwd)"
INSTALLED_LAUNCHER="$APP_HOME/bin/roi"
INSTALLED_VENV_PYTHON="$APP_HOME/venv/bin/python"
CONTRACT_SRC="$HOME/Libs/rgw_cli_contract/src"

if [[ -f "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc" >/dev/null 2>&1 || true
fi

if [[ -x "$INSTALLED_LAUNCHER" ]]; then
  exec "$INSTALLED_LAUNCHER" __track_once__
fi

if [[ -x "$INSTALLED_VENV_PYTHON" ]]; then
  exec "$INSTALLED_VENV_PYTHON" "$ROOT_DIR/main.py" __track_once__
fi

if command -v roi >/dev/null 2>&1; then
  exec roi __track_once__
fi

if [[ -d "$CONTRACT_SRC" ]]; then
  export PYTHONPATH="$CONTRACT_SRC${PYTHONPATH:+:$PYTHONPATH}"
fi

exec /usr/bin/python3 "$ROOT_DIR/main.py" __track_once__
