from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from config import APP_NAME, InstallerConfig
from manifest import MANIFEST_REL_PATH, capture_manifest, save_manifest
from notifications import notify_snapshot_synced
from state_repo import read_remote_manifest, sync_manifest


class OperationError(RuntimeError):
    """Raised when apply or daemon actions fail."""


def resolve_repo_root(configured_root: Path, source_root: Path) -> Path:
    if configured_root.exists():
        return configured_root
    return source_root


def _command_env(home_dir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if home_dir is not None:
        env["HOME"] = str(home_dir)
        if "GH_TOKEN" not in env and "GITHUB_TOKEN" not in env:
            token_path = home_dir / ".config" / APP_NAME / "github_token"
            if token_path.exists():
                token = token_path.read_text(encoding="utf-8").strip()
                if token:
                    env["GH_TOKEN"] = token
    return env


def _load_home_shell_env(home_dir: Path) -> dict[str, str]:
    env = _command_env(home_dir)
    bashrc_path = home_dir / ".bashrc"
    if not bashrc_path.exists():
        return env

    result = subprocess.run(
        [
            "/usr/bin/bash",
            "-lc",
            f"source {shlex.quote(str(bashrc_path))} >/dev/null 2>&1 || true; env -0",
        ],
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise OperationError(f"Failed to load shell environment from {bashrc_path}")

    loaded: dict[str, str] = {}
    for chunk in result.stdout.split(b"\0"):
        if not chunk:
            continue
        key, sep, value = chunk.partition(b"=")
        if not sep:
            continue
        loaded[key.decode("utf-8", "ignore")] = value.decode("utf-8", "ignore")
    loaded["HOME"] = str(home_dir)
    return loaded


def _run(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, check=False, env=env)
    if result.returncode != 0:
        raise OperationError(f"command failed ({result.returncode}): {' '.join(command)}")


def _capture(
    command: list[str],
    cwd: Path | None = None,
    allow_failure: bool = False,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        if allow_failure:
            return ""
        stderr = result.stderr.strip() or result.stdout.strip() or f"command failed: {' '.join(command)}"
        raise OperationError(stderr)
    return result.stdout.strip()


def _github_repo_slug(remote_url: str) -> str | None:
    normalized = remote_url.strip()
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if normalized.startswith(prefix):
            slug = normalized[len(prefix):]
            return slug[:-4] if slug.endswith(".git") else slug
    return None


def _ensure_github_auth(remote_url: str, home_dir: Path) -> None:
    if _github_repo_slug(remote_url) is None:
        return
    if not shutil.which("gh"):
        raise OperationError("Expected 'gh' to bootstrap GitHub-hosted repos. Install GitHub CLI first.")

    env = _command_env(home_dir)
    status = _capture(["gh", "auth", "status"], allow_failure=True, env=env)
    if not status:
        print("github: start web auth")
        _run(["gh", "auth", "login", "--web", "--git-protocol", "https", "--skip-ssh-key"], env=env)
    _run(["gh", "auth", "setup-git"], env=env)


def _ensure_origin(path: Path, remote_url: str, env: dict[str, str] | None = None) -> None:
    current = _capture(["git", "-C", str(path), "remote", "get-url", "origin"], allow_failure=True, env=env)
    if not current:
        _run(["git", "-C", str(path), "remote", "add", "origin", remote_url], env=env)
        return
    if current != remote_url:
        raise OperationError(f"{path} already points at {current}, not {remote_url}")


def _pull_checkout(path: Path, remote_url: str, branch: str, env: dict[str, str] | None = None) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--branch", branch, "--single-branch", remote_url, str(path)], env=env)
        return

    if not (path / ".git").exists():
        if any(path.iterdir()):
            raise OperationError(f"{path} exists but is not a git checkout")
        _run(["git", "clone", "--branch", branch, "--single-branch", remote_url, str(path)], env=env)
        return

    _ensure_origin(path, remote_url, env=env)
    _run(["git", "-C", str(path), "fetch", "origin"], env=env)
    _run(["git", "-C", str(path), "checkout", branch], env=env)
    _run(["git", "-C", str(path), "pull", "--ff-only", "origin", branch], env=env)


def _bootstrap_home_repo(home_dir: Path, remote_url: str, branch: str, env: dict[str, str] | None = None) -> None:
    if (home_dir / ".git").exists():
        _ensure_origin(home_dir, remote_url, env=env)
        _run(["git", "-C", str(home_dir), "fetch", "origin"], env=env)
        _run(["git", "-C", str(home_dir), "checkout", branch], env=env)
        _run(["git", "-C", str(home_dir), "pull", "--ff-only", "origin", branch], env=env)
        return

    _run(["git", "-C", str(home_dir), "init"], env=env)
    _run(["git", "-C", str(home_dir), "remote", "add", "origin", remote_url], env=env)
    _run(["git", "-C", str(home_dir), "fetch", "origin"], env=env)
    _run(["git", "-C", str(home_dir), "checkout", "-f", "-B", branch, f"origin/{branch}"], env=env)
    _run(["git", "-C", str(home_dir), "branch", "--set-upstream-to", f"origin/{branch}", branch], env=env)


def _expand_home(path_value: str, home_dir: Path) -> Path:
    return Path(path_value.replace("$HOME", str(home_dir)))


def _ensure_omarchy_commands() -> str:
    set_cmd = shutil.which("omarchy-theme-set")
    if not set_cmd:
        raise OperationError(
            "Expected omarchy-theme-set. Install the base Omarchy tooling first."
        )
    return set_cmd


def _install_themes(manifest: dict[str, Any], home_dir: Path, env: dict[str, str] | None = None) -> None:
    set_cmd = _ensure_omarchy_commands()
    themes = [theme for theme in manifest.get("themes", []) if str(theme.get("name", "")).strip() == "rgwos"]
    for theme in themes:
        theme_name = str(theme.get("name", "")).strip()
        remote_url = str(theme.get("remote_url", "")).strip()
        branch = str(theme.get("branch", "main")).strip() or "main"
        if not theme_name or not remote_url:
            continue
        target = home_dir / ".config" / "omarchy" / "themes" / theme_name
        print(f"theme {theme_name}: sync")
        _pull_checkout(target, remote_url, branch, env=env)
    active_theme = str(manifest.get("active_theme", "")).strip()
    if not active_theme and themes:
        active_theme = "rgwos"
    if active_theme:
        print(f"theme {active_theme}: activate")
        _run([set_cmd, active_theme], env=env)


def _ensure_required_dirs(manifest: dict[str, Any], home_dir: Path) -> None:
    for item in manifest.get("required_dirs", []):
        target = _expand_home(str(item), home_dir)
        target.mkdir(parents=True, exist_ok=True)
        print(f"dir {target}: ok")


def _sync_repo_group(manifest: dict[str, Any], home_dir: Path, group: str, env: dict[str, str] | None = None) -> None:
    repos = list(manifest.get("repos", {}).get(group, []))
    repos.sort(key=lambda repo: (repo.get("name") == APP_NAME, str(repo.get("name"))))
    for repo in repos:
        relative_path = str(repo.get("relative_path", "")).strip()
        if not relative_path:
            continue
        target = home_dir / relative_path
        remote_url = str(repo.get("remote_url", "")).strip()
        branch = str(repo.get("branch", "main")).strip() or "main"
        print(f"repo {relative_path}: sync")
        _pull_checkout(target, remote_url, branch, env=env)
        if repo.get("install_via_script"):
            install_script = target / "install.sh"
            if install_script.exists():
                print(f"repo {relative_path}: install")
                _run(["/usr/bin/bash", str(install_script), "-u"], cwd=target, env=env)


def _sync_packages(manifest: dict[str, Any], env: dict[str, str] | None = None) -> None:
    packages = manifest.get("packages", {})
    preferred = str(packages.get("manager", "yay"))
    explicit = list(packages.get("explicit", []))
    official = list(packages.get("official", []))
    foreign = list(packages.get("foreign", []))

    manager = None
    for candidate in (preferred, "yay", "paru", "pacman"):
        if candidate and shutil.which(candidate):
            manager = candidate
            break

    if manager is None:
        raise OperationError("Expected pacman, yay, or paru to install packages.")

    if manager in {"yay", "paru"}:
        command = [manager, "-Syu", "--needed", "--noconfirm", *explicit]
    else:
        if foreign:
            raise OperationError("Snapshot includes foreign packages but no AUR helper is installed.")
        command = ["sudo", "pacman", "-Syu", "--needed", "--noconfirm", *official]

    print(f"packages: sync via {manager}")
    _run(command, env=env)


def apply_manifest(manifest: dict[str, Any], home_dir: Path) -> None:
    home_repo = manifest.get("home_repo", {})
    remote_url = str(home_repo.get("remote_url", "")).strip()
    branch = str(home_repo.get("branch", "main")).strip() or "main"
    if not remote_url:
        raise OperationError("Manifest is missing home_repo.remote_url")

    _ensure_github_auth(remote_url, home_dir)
    bootstrap_env = _command_env(home_dir)
    print("home repo: sync")
    _bootstrap_home_repo(home_dir, remote_url, branch, env=bootstrap_env)
    runtime_env = _load_home_shell_env(home_dir)
    _install_themes(manifest, home_dir, env=runtime_env)
    _ensure_required_dirs(manifest, home_dir)
    for group in ("Apps", "Libs", "Work"):
        _sync_repo_group(manifest, home_dir, group, env=runtime_env)
    _sync_packages(manifest, env=runtime_env)


def initialize_state_repo(config: InstallerConfig, home_dir: Path) -> bool:
    runtime_env = _load_home_shell_env(home_dir)
    manifest = capture_manifest(home_dir)
    spec, changed = sync_manifest(
        config,
        manifest,
        runtime_env,
        allow_web_login=True,
    )
    print(f"state repo: {spec.slug}")
    if changed:
        print(f"state manifest: updated {spec.manifest_path}")
        notify_snapshot_synced(spec.slug)
    else:
        print(f"state manifest: unchanged {spec.manifest_path}")
    return changed


def install_from_state_repo(config: InstallerConfig, home_dir: Path) -> None:
    manifest = read_remote_manifest(
        config,
        _command_env(home_dir),
        allow_web_login=True,
    )
    apply_manifest(manifest, home_dir)


def sync_snapshot(repo_root: Path, home_dir: Path) -> bool:
    manifest = capture_manifest(home_dir)
    changed = save_manifest(repo_root, manifest)
    target = repo_root / MANIFEST_REL_PATH
    if changed:
        print(f"snapshot updated: {target}")
    else:
        print(f"snapshot unchanged: {target}")
    return changed


def run_track_once(
    config: InstallerConfig,
    home_dir: Path,
) -> bool:
    runtime_env = _load_home_shell_env(home_dir)
    manifest = capture_manifest(home_dir)
    spec, changed = sync_manifest(
        config,
        manifest,
        runtime_env,
        allow_web_login=False,
    )
    print(f"state repo: {spec.slug}")
    if changed:
        print(f"state manifest: updated {spec.manifest_path}")
        notify_snapshot_synced(spec.slug)
    else:
        print(f"state manifest: unchanged {spec.manifest_path}")
    return changed
