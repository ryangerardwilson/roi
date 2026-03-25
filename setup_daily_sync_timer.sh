#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="rgw_omarchy_installer-daily.service"
TIMER_NAME="rgw_omarchy_installer-daily.timer"
SERVICE_PATH="$SYSTEMD_DIR/$SERVICE_NAME"
TIMER_PATH="$SYSTEMD_DIR/$TIMER_NAME"
RUNNER_PATH="$ROOT_DIR/run_daily_sync.sh"

mkdir -p "$SYSTEMD_DIR"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=RGW Omarchy Installer Daily Snapshot Sync

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
ExecStart=/usr/bin/bash $RUNNER_PATH
EOF

cat > "$TIMER_PATH" <<EOF
[Unit]
Description=Run RGW Omarchy Installer Daily Snapshot Sync

[Timer]
OnCalendar=daily
Persistent=true
Unit=$SERVICE_NAME

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$TIMER_NAME"
systemctl --user status "$TIMER_NAME" --no-pager --lines=10
