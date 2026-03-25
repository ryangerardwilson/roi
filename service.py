from __future__ import annotations

import subprocess
import time
from pathlib import Path

from config import APP_NAME, InstallerConfig, launcher_path, service_unit_path
from engine import run_tick, resolve_repo_root


class ServiceError(RuntimeError):
    """Raised when service installation or control fails."""


def _run(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise ServiceError(f"command failed ({result.returncode}): {' '.join(command)}")


def render_service_unit(source_root: Path, config: InstallerConfig) -> str:
    template_path = source_root / "assets" / f"{APP_NAME}.service.tpl"
    template = template_path.read_text(encoding="utf-8")
    repo_root = resolve_repo_root(config.paths.repo_root, source_root)
    workdir = str(repo_root if repo_root.exists() else source_root)
    exec_start = str(launcher_path()) + " loop"
    return template.replace("__WORKDIR__", workdir).replace("__EXEC_START__", exec_start)


def install_service(source_root: Path, config: InstallerConfig) -> Path:
    target = service_unit_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_service_unit(source_root, config), encoding="utf-8")
    _run(["systemctl", "--user", "daemon-reload"])
    return target


def enable_service() -> None:
    _run(["systemctl", "--user", "enable", "--now", f"{APP_NAME}.service"])


def disable_service() -> None:
    _run(["systemctl", "--user", "disable", "--now", f"{APP_NAME}.service"])


def show_status() -> int:
    result = subprocess.run(
        ["systemctl", "--user", "status", f"{APP_NAME}.service", "--no-pager", "--lines=20"],
        check=False,
    )
    return result.returncode


def run_loop(source_root: Path, config: InstallerConfig) -> int:
    while True:
        try:
            run_tick(config, source_root)
        except Exception as exc:  # pragma: no cover - the service should keep running
            print(str(exc))
        time.sleep(config.daemon.poll_seconds)
