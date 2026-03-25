#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from _version import __version__
from config import CONFIG_TEXT, config_path, load_config
from engine import OperationError, apply_saved_snapshot, resolve_repo_root, run_tick, sync_snapshot
from manifest import ManifestError, load_manifest, summarize_manifest
from rgw_cli_contract import AppSpec, resolve_install_script_path, run_app
from service import ServiceError, disable_service, enable_service, install_service, run_loop, show_status


APP_ROOT = Path(__file__).resolve().parent
INSTALL_SCRIPT = resolve_install_script_path(__file__)
HELP_TEXT = """rgw_omarchy_installer
capture this Omarchy laptop and replay it on another one

flags:
  rgw_omarchy_installer -h
    show this help
  rgw_omarchy_installer -v
    print the installed version
  rgw_omarchy_installer -u
    upgrade to the latest release

features:
  refresh the checked-in machine snapshot from this laptop
  # rgw_omarchy_installer snap
  rgw_omarchy_installer snap

  apply the saved snapshot in the required order
  # rgw_omarchy_installer apply
  rgw_omarchy_installer apply

  run one daemon cycle from the configured mode
  # rgw_omarchy_installer tick
  rgw_omarchy_installer tick

  install or control the user service
  # rgw_omarchy_installer svc i|on|off|st
  rgw_omarchy_installer svc i
  rgw_omarchy_installer svc on

  inspect the currently saved snapshot
  # rgw_omarchy_installer show
  rgw_omarchy_installer show

  run the long-lived daemon loop used by the user service
  # rgw_omarchy_installer loop
  rgw_omarchy_installer loop

  edit the daemon config
  # rgw_omarchy_installer conf
  rgw_omarchy_installer conf
"""


class UsageError(ValueError):
    """Raised for invalid CLI usage."""


APP_SPEC = AppSpec(
    app_name="rgw_omarchy_installer",
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

    if argv == ["snap"]:
        sync_snapshot(repo_root, Path.home())
        return 0

    if argv == ["apply"]:
        apply_saved_snapshot(repo_root, Path.home())
        return 0

    if argv == ["show"]:
        print(summarize_manifest(load_manifest(repo_root)))
        return 0

    if argv == ["tick"]:
        run_tick(config, APP_ROOT)
        return 0

    if argv == ["loop"]:
        return run_loop(APP_ROOT, config)

    if len(argv) == 2 and argv[0] == "svc":
        action = argv[1]
        if action == "i":
            unit_path = install_service(APP_ROOT, config)
            print(unit_path)
            return 0
        if action == "on":
            enable_service()
            return 0
        if action == "off":
            disable_service()
            return 0
        if action == "st":
            return show_status()
        raise UsageError("Usage: rgw_omarchy_installer svc i|on|off|st")

    raise UsageError("Usage: rgw_omarchy_installer snap|apply|show|tick|loop|svc i|on|off|st|conf")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return run_app(APP_SPEC, args, _dispatch)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (ManifestError, OperationError, ServiceError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
