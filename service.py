from __future__ import annotations

import subprocess
from pathlib import Path

from config import APP_NAME, systemd_user_dir


class ServiceError(RuntimeError):
    """Raised when service installation or control fails."""


TRACK_SERVICE_NAME = f"{APP_NAME}-track.service"
TRACK_TIMER_NAME = f"{APP_NAME}-track.timer"


def _run(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise ServiceError(f"command failed ({result.returncode}): {' '.join(command)}")


def track_service_unit_path() -> Path:
    return systemd_user_dir() / TRACK_SERVICE_NAME


def track_timer_unit_path() -> Path:
    return systemd_user_dir() / TRACK_TIMER_NAME


def render_track_service_unit(source_root: Path) -> str:
    runner_path = source_root / "run_track_once.sh"
    return (
        "[Unit]\n"
        "Description=ROI State Daily Tracker\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={source_root}\n"
        f"ExecStart=/usr/bin/bash {runner_path}\n"
    )


def render_track_timer_unit() -> str:
    return (
        "[Unit]\n"
        "Description=Run ROI State Daily Tracker\n\n"
        "[Timer]\n"
        "OnCalendar=daily\n"
        "Persistent=true\n"
        f"Unit={TRACK_SERVICE_NAME}\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def install_track_units(source_root: Path) -> Path:
    user_dir = systemd_user_dir()
    user_dir.mkdir(parents=True, exist_ok=True)
    service_path = track_service_unit_path()
    timer_path = track_timer_unit_path()
    service_path.write_text(render_track_service_unit(source_root), encoding="utf-8")
    timer_path.write_text(render_track_timer_unit(), encoding="utf-8")
    _run(["systemctl", "--user", "daemon-reload"])
    return timer_path


def enable_track_timer() -> None:
    _run(["systemctl", "--user", "enable", "--now", TRACK_TIMER_NAME])


def start_track_service() -> None:
    _run(["systemctl", "--user", "start", TRACK_SERVICE_NAME])
