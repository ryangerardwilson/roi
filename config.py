from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "roi"
CONFIG_TEXT = (Path(__file__).resolve().parent / "assets" / "default_config.toml").read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class DaemonConfig:
    mode: str
    poll_seconds: int
    auto_commit: bool
    auto_push: bool
    auto_apply: bool


@dataclass(frozen=True, slots=True)
class PathsConfig:
    repo_root: Path


@dataclass(frozen=True, slots=True)
class InstallerConfig:
    daemon: DaemonConfig
    paths: PathsConfig


def _xdg_path(env_name: str, default_suffix: str) -> Path:
    base = os.environ.get(env_name)
    if base:
        return Path(base)
    return Path.home() / default_suffix


def config_dir() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", ".config") / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.toml"


def state_dir() -> Path:
    return _xdg_path("XDG_STATE_HOME", ".local/state") / APP_NAME


def state_path() -> Path:
    return state_dir() / "daemon_state.json"


def systemd_user_dir() -> Path:
    return config_dir().parent / "systemd" / "user"


def service_unit_path() -> Path:
    return systemd_user_dir() / f"{APP_NAME}.service"


def install_home() -> Path:
    return Path.home() / f".{APP_NAME}"


def launcher_path() -> Path:
    return Path.home() / ".local" / "bin" / APP_NAME


def ensure_config_file() -> Path:
    target = config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(CONFIG_TEXT, encoding="utf-8")
    return target


def _expand_home(value: str) -> Path:
    return Path(value.replace("$HOME", str(Path.home()))).expanduser()


def load_config() -> InstallerConfig:
    target = ensure_config_file()
    data = tomllib.loads(target.read_text(encoding="utf-8"))

    daemon_table = data.get("daemon", {})
    if not isinstance(daemon_table, dict):
        raise ValueError("[daemon] must be a table")
    paths_table = data.get("paths", {})
    if not isinstance(paths_table, dict):
        raise ValueError("[paths] must be a table")

    mode = str(daemon_table.get("mode", "source")).strip().lower()
    if mode not in {"source", "follower"}:
        raise ValueError("daemon.mode must be 'source' or 'follower'")

    poll_seconds = int(daemon_table.get("poll_seconds", 300))
    if poll_seconds <= 0:
        raise ValueError("daemon.poll_seconds must be positive")

    repo_root_raw = str(paths_table.get("repo_root", f"$HOME/Apps/{APP_NAME}"))

    return InstallerConfig(
        daemon=DaemonConfig(
            mode=mode,
            poll_seconds=poll_seconds,
            auto_commit=bool(daemon_table.get("auto_commit", True)),
            auto_push=bool(daemon_table.get("auto_push", True)),
            auto_apply=bool(daemon_table.get("auto_apply", True)),
        ),
        paths=PathsConfig(repo_root=_expand_home(repo_root_raw)),
    )
