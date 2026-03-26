#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONTRACT_SRC="$HOME/Libs/rgw_cli_contract/src"

if [[ -f "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc" >/dev/null 2>&1 || true
fi

if command -v rgw_omarchy_installer >/dev/null 2>&1; then
  exec rgw_omarchy_installer __track_once__
fi

if [[ -d "$CONTRACT_SRC" ]]; then
  export PYTHONPATH="$CONTRACT_SRC${PYTHONPATH:+:$PYTHONPATH}"
fi

exec /usr/bin/python3 "$ROOT_DIR/main.py" __track_once__
