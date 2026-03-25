from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import APP_NAME, InstallerConfig, state_path
from manifest import MANIFEST_REL_PATH, ManifestError, capture_manifest, load_manifest, manifest_digest, save_manifest


class OperationError(RuntimeError):
    """Raised when apply or daemon actions fail."""


def resolve_repo_root(configured_root: Path, source_root: Path) -> Path:
    if configured_root.exists():
        return configured_root
    return source_root


def _run(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise OperationError(f"command failed ({result.returncode}): {' '.join(command)}")


def _capture(command: list[str], cwd: Path | None = None, allow_failure: bool = False) -> str:
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
        raise OperationError(stderr)
    return result.stdout.strip()


def _ensure_origin(path: Path, remote_url: str) -> None:
    current = _capture(["git", "-C", str(path), "remote", "get-url", "origin"], allow_failure=True)
    if not current:
        _run(["git", "-C", str(path), "remote", "add", "origin", remote_url])
        return
    if current != remote_url:
        raise OperationError(f"{path} already points at {current}, not {remote_url}")


def _pull_checkout(path: Path, remote_url: str, branch: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--branch", branch, "--single-branch", remote_url, str(path)])
        return

    if not (path / ".git").exists():
        if any(path.iterdir()):
            raise OperationError(f"{path} exists but is not a git checkout")
        _run(["git", "clone", "--branch", branch, "--single-branch", remote_url, str(path)])
        return

    _ensure_origin(path, remote_url)
    _run(["git", "-C", str(path), "fetch", "origin"])
    _run(["git", "-C", str(path), "checkout", branch])
    _run(["git", "-C", str(path), "pull", "--ff-only", "origin", branch])


def _bootstrap_home_repo(home_dir: Path, remote_url: str, branch: str) -> None:
    if (home_dir / ".git").exists():
        _ensure_origin(home_dir, remote_url)
        _run(["git", "-C", str(home_dir), "fetch", "origin"])
        _run(["git", "-C", str(home_dir), "checkout", branch])
        _run(["git", "-C", str(home_dir), "pull", "--ff-only", "origin", branch])
        return

    _run(["git", "-C", str(home_dir), "init"])
    _run(["git", "-C", str(home_dir), "remote", "add", "origin", remote_url])
    _run(["git", "-C", str(home_dir), "fetch", "origin"])
    _run(["git", "-C", str(home_dir), "checkout", "-f", "-B", branch, f"origin/{branch}"])
    _run(["git", "-C", str(home_dir), "branch", "--set-upstream-to", f"origin/{branch}", branch])


def _expand_home(path_value: str, home_dir: Path) -> Path:
    return Path(path_value.replace("$HOME", str(home_dir)))


def _ensure_omarchy_commands() -> tuple[str, str]:
    install_cmd = shutil.which("omarchy-theme-install")
    set_cmd = shutil.which("omarchy-theme-set")
    if not install_cmd or not set_cmd:
        raise OperationError(
            "Expected omarchy-theme-install and omarchy-theme-set. Install the base Omarchy tooling first."
        )
    return install_cmd, set_cmd


def _install_themes(manifest: dict[str, Any]) -> None:
    install_cmd, set_cmd = _ensure_omarchy_commands()
    for theme in manifest.get("themes", []):
        remote_url = str(theme.get("remote_url", "")).strip()
        if not remote_url:
            continue
        print(f"theme {theme['name']}: install")
        _run([install_cmd, remote_url])

    active_theme = str(manifest.get("active_theme", "")).strip()
    if active_theme:
        print(f"theme {active_theme}: activate")
        _run([set_cmd, active_theme])


def _ensure_required_dirs(manifest: dict[str, Any], home_dir: Path) -> None:
    for item in manifest.get("required_dirs", []):
        target = _expand_home(str(item), home_dir)
        target.mkdir(parents=True, exist_ok=True)
        print(f"dir {target}: ok")


def _sync_repo_group(manifest: dict[str, Any], home_dir: Path, group: str) -> None:
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
        _pull_checkout(target, remote_url, branch)
        if repo.get("install_via_script"):
            install_script = target / "install.sh"
            if install_script.exists():
                print(f"repo {relative_path}: install")
                _run(["/usr/bin/bash", str(install_script), "-u"], cwd=target)


def _sync_packages(manifest: dict[str, Any]) -> None:
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
    _run(command)


def apply_manifest(manifest: dict[str, Any], home_dir: Path) -> None:
    home_repo = manifest.get("home_repo", {})
    remote_url = str(home_repo.get("remote_url", "")).strip()
    branch = str(home_repo.get("branch", "main")).strip() or "main"
    if not remote_url:
        raise OperationError("Manifest is missing home_repo.remote_url")

    print("home repo: sync")
    _bootstrap_home_repo(home_dir, remote_url, branch)
    _install_themes(manifest)
    _ensure_required_dirs(manifest, home_dir)
    for group in ("Apps", "Libs", "Work"):
        _sync_repo_group(manifest, home_dir, group)
    _sync_packages(manifest)


def sync_snapshot(repo_root: Path, home_dir: Path) -> bool:
    manifest = capture_manifest(home_dir)
    changed = save_manifest(repo_root, manifest)
    target = repo_root / MANIFEST_REL_PATH
    if changed:
        print(f"snapshot updated: {target}")
    else:
        print(f"snapshot unchanged: {target}")
    return changed


def _git_status_paths(repo_root: Path) -> list[str]:
    output = _capture(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
        allow_failure=True,
    )
    if not output:
        return []
    paths: list[str] = []
    for line in output.splitlines():
        entry = line[3:]
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        paths.append(entry)
    return paths


def _pull_self_repo_if_safe(repo_root: Path) -> None:
    if not (repo_root / ".git").exists():
        return
    paths = _git_status_paths(repo_root)
    allowed = {str(MANIFEST_REL_PATH)}
    if any(path not in allowed for path in paths):
        print("self repo: skip pull because unrelated local changes exist")
        return
    print("self repo: pull")
    _run(["git", "-C", str(repo_root), "pull", "--ff-only"])


def maybe_commit_snapshot(repo_root: Path, auto_push: bool) -> bool:
    if not (repo_root / ".git").exists():
        return False
    paths = _git_status_paths(repo_root)
    if not paths:
        return False
    manifest_rel = str(MANIFEST_REL_PATH)
    if any(path != manifest_rel for path in paths):
        print("self repo: skip auto-commit because unrelated changes exist")
        return False
    _run(["git", "-C", str(repo_root), "add", manifest_rel])
    _run(
        [
            "git",
            "-C",
            str(repo_root),
            "commit",
            "-m",
            f"sync snapshot {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        ]
    )
    if auto_push:
        print("self repo: push")
        _run(["git", "-C", str(repo_root), "push"])
    return True


def _load_state() -> dict[str, Any]:
    target = state_path()
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _save_state(state: dict[str, Any]) -> None:
    target = state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_saved_snapshot(repo_root: Path, home_dir: Path) -> None:
    manifest = load_manifest(repo_root)
    apply_manifest(manifest, home_dir)


def run_tick(config: InstallerConfig, source_root: Path, home_dir: Path | None = None) -> None:
    home_dir = Path.home() if home_dir is None else home_dir
    repo_root = resolve_repo_root(config.paths.repo_root, source_root)

    if config.daemon.mode == "source":
        _pull_self_repo_if_safe(repo_root)
        changed = sync_snapshot(repo_root, home_dir)
        if changed and config.daemon.auto_commit:
            maybe_commit_snapshot(repo_root, auto_push=config.daemon.auto_push)
        return

    if config.daemon.mode == "follower":
        _pull_self_repo_if_safe(repo_root)
        if not config.daemon.auto_apply:
            return
        manifest = load_manifest(repo_root)
        digest = manifest_digest(manifest)
        state = _load_state()
        if state.get("last_applied_digest") == digest:
            print("snapshot already applied")
            return
        apply_manifest(manifest, home_dir)
        state["last_applied_digest"] = digest
        state["last_applied_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _save_state(state)
        return

    raise OperationError(f"Unsupported daemon mode: {config.daemon.mode}")
