from __future__ import annotations

import json
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_NAME = "rgw_omarchy_installer"
MANIFEST_REL_PATH = Path("snapshot/system_manifest.json")
MANAGED_DIR_NAMES = ("Work", "Infra", "Music", "Apps", "Libs")
REPO_GROUPS = ("Apps", "Libs", "Work")


class ManifestError(RuntimeError):
    """Raised when snapshot capture or load fails."""


def manifest_path(repo_root: Path) -> Path:
    return repo_root / MANIFEST_REL_PATH


def _run_capture(command: list[str], cwd: Path | None = None, allow_failure: bool = False) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if allow_failure:
            return ""
        stderr = result.stderr.strip() or result.stdout.strip() or f"command failed: {' '.join(command)}"
        raise ManifestError(stderr)
    return result.stdout.strip()


def _capture_lines(command: list[str]) -> list[str]:
    output = _run_capture(command, allow_failure=True)
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _git_top_level(path: Path) -> Path | None:
    if not path.exists():
        return None
    top_level = _run_capture(["git", "-C", str(path), "rev-parse", "--show-toplevel"], allow_failure=True)
    if not top_level:
        return None
    return Path(top_level).resolve()


def _is_git_repo_root(path: Path) -> bool:
    top_level = _git_top_level(path)
    if top_level is None:
        return False
    return top_level == path.resolve()


def _git_remote(path: Path) -> str:
    return _run_capture(["git", "-C", str(path), "remote", "get-url", "origin"], allow_failure=True)


def _git_branch(path: Path) -> str:
    branch = _run_capture(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"], allow_failure=True)
    return branch or "main"


def _repo_spec(path: Path, relative_path: str, install_via_script: bool) -> dict[str, Any] | None:
    if not _is_git_repo_root(path):
        return None
    remote_url = _git_remote(path)
    if not remote_url:
        return None
    return {
        "name": path.name,
        "relative_path": relative_path,
        "remote_url": remote_url,
        "branch": _git_branch(path),
        "has_install_script": (path / "install.sh").exists(),
        "install_via_script": install_via_script and path.name != APP_NAME and (path / "install.sh").exists(),
    }


def discover_repo_specs(home_dir: Path, group: str) -> list[dict[str, Any]]:
    root = home_dir / group
    if not root.exists():
        return []
    specs: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        spec = _repo_spec(
            child,
            f"{group}/{child.name}",
            install_via_script=(group == "Apps"),
        )
        if spec is not None:
            specs.append(spec)
    return specs


def discover_theme_specs(home_dir: Path) -> list[dict[str, Any]]:
    themes_root = home_dir / ".config" / "omarchy" / "themes"
    if not themes_root.exists():
        return []
    specs: list[dict[str, Any]] = []
    for child in sorted(themes_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        spec = _repo_spec(
            child,
            f".config/omarchy/themes/{child.name}",
            install_via_script=False,
        )
        if spec is None:
            continue
        specs.append(
            {
                "name": child.name,
                "remote_url": spec["remote_url"],
                "branch": spec["branch"],
            }
        )
    return specs


def read_active_theme_name(home_dir: Path) -> str:
    theme_name_path = home_dir / ".config" / "omarchy" / "current" / "theme.name"
    if not theme_name_path.exists():
        return ""
    return theme_name_path.read_text(encoding="utf-8").strip()


def discover_packages() -> dict[str, Any]:
    if shutil.which("yay"):
        manager = "yay"
    elif shutil.which("paru"):
        manager = "paru"
    elif shutil.which("pacman"):
        manager = "pacman"
    else:
        raise ManifestError("Expected pacman, yay, or paru on this system.")

    official = _capture_lines(["pacman", "-Qqen"])
    foreign = _capture_lines(["pacman", "-Qqem"])
    explicit = sorted(dict.fromkeys([*official, *foreign]))
    return {
        "manager": manager,
        "official": official,
        "foreign": foreign,
        "explicit": explicit,
    }


def capture_manifest(home_dir: Path) -> dict[str, Any]:
    home_repo = _repo_spec(home_dir, ".", install_via_script=False)
    if home_repo is None:
        raise ManifestError(f"{home_dir} is not a git repo with an origin remote.")

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_hostname": socket.gethostname(),
        "required_dirs": [f"$HOME/{name}" for name in MANAGED_DIR_NAMES],
        "home_repo": {
            "remote_url": home_repo["remote_url"],
            "branch": home_repo["branch"],
        },
        "themes": discover_theme_specs(home_dir),
        "active_theme": read_active_theme_name(home_dir),
        "repos": {
            group: discover_repo_specs(home_dir, group)
            for group in REPO_GROUPS
        },
        "packages": discover_packages(),
    }


def _normalized_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(manifest))
    normalized.pop("generated_at", None)
    return normalized


def manifest_digest(manifest: dict[str, Any]) -> str:
    normalized = _normalized_manifest(manifest)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def save_manifest(repo_root: Path, manifest: dict[str, Any]) -> bool:
    target = manifest_path(repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        current = json.loads(target.read_text(encoding="utf-8"))
        if _normalized_manifest(current) == _normalized_manifest(manifest):
            return False

    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def load_manifest(repo_root: Path) -> dict[str, Any]:
    target = manifest_path(repo_root)
    if not target.exists():
        raise ManifestError(f"Snapshot file not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


def summarize_manifest(manifest: dict[str, Any]) -> str:
    repos = manifest.get("repos", {})
    packages = manifest.get("packages", {})
    lines = [
        "rgw_omarchy_installer",
        "",
        f"generated: {manifest.get('generated_at', 'unknown')}",
        f"source: {manifest.get('source_hostname', 'unknown')}",
        f"active theme: {manifest.get('active_theme', '') or 'unset'}",
        f"themes: {len(manifest.get('themes', []))}",
        f"apps: {len(repos.get('Apps', []))}",
        f"libs: {len(repos.get('Libs', []))}",
        f"work repos: {len(repos.get('Work', []))}",
        f"packages: {len(packages.get('explicit', []))}",
    ]
    return "\n".join(lines)
