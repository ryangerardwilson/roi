[Unit]
Description=RGW Omarchy Installer Sync Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=__WORKDIR__
ExecStart=__EXEC_START__
Restart=always
RestartSec=60

[Install]
WantedBy=default.target
