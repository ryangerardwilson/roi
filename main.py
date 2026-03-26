#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from _version import __version__
from config import CONFIG_TEXT, config_path, load_config
from engine import OperationError, initialize_state_repo, install_from_state_repo, resolve_repo_root, run_track_once, sync_snapshot
from manifest import ManifestError, load_manifest, summarize_manifest
from rgw_cli_contract import AppSpec, resolve_install_script_path, run_app
from service import ServiceError, enable_track_timer, install_track_units, start_track_service
from state_repo import StateRepoError


APP_ROOT = Path(__file__).resolve().parent
INSTALL_SCRIPT = resolve_install_script_path(__file__)
HELP_TEXT = """roi
capture this Omarchy laptop and replay it on another one

flags:
  roi -h
    show this help
  roi -v
    print the installed version
  roi -u
    upgrade to the latest release

features:
  initialize the private roi_state repo for this account
  # roi init
  roi init

  keep roi_state updated once per day in the background
  # roi track
  roi track

  install this machine from roi_state
  # roi install
  roi install
"""


class UsageError(ValueError):
    """Raised for invalid CLI usage."""


APP_SPEC = AppSpec(
    app_name="roi",
    version=__version__,
    help_text=HELP_TEXT,
    install_script_path=INSTALL_SCRIPT,
    config_path_factory=config_path,
    config_bootstrap_text=CONFIG_TEXT,
)


def _repo_root() -> Path:
    config = load_config()
    return resolve_repo_root(config.paths.repo_root, APP_ROOT)


def _dispatch(argv: list[str]) -> int:
    config = load_config()
    repo_root = resolve_repo_root(config.paths.repo_root, APP_ROOT)

    if argv == ["init"]:
        initialize_state_repo(config, Path.home())
        return 0

    if argv == ["install"] or argv == ["apply"]:
        install_from_state_repo(config, Path.home())
        return 0

    if argv == ["track"]:
        initialize_state_repo(config, Path.home())
        timer_path = install_track_units(APP_ROOT)
        enable_track_timer()
        start_track_service()
        print(timer_path)
        return 0

    if argv == ["__track_once__"] or argv == ["tick"]:
        run_track_once(config, Path.home())
        return 0

    if argv == ["show"]:
        print(summarize_manifest(load_manifest(repo_root)))
        return 0

    if argv == ["snap"]:
        sync_snapshot(repo_root, Path.home())
        return 0

    raise UsageError("Usage: roi init|track|install")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return run_app(APP_SPEC, args, _dispatch)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (ManifestError, OperationError, ServiceError, StateRepoError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
