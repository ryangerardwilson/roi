from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import InstallerConfig


class StateRepoError(RuntimeError):
    """Raised when roi_state access or sync fails."""


@dataclass(frozen=True, slots=True)
class StateRepoSpec:
    owner: str
    name: str
    manifest_path: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


def _run_capture(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        env=env,
    )


def _gh_json(command: list[str], env: dict[str, str]) -> Any:
    result = _run_capture(command, env)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or f"command failed: {' '.join(command)}"
        raise StateRepoError(stderr)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise StateRepoError(f"Invalid JSON from GitHub CLI: {exc}") from exc


def _is_not_found(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stderr}\n{result.stdout}"
    return "404" in text or "Not Found" in text


def ensure_github_auth(
    env: dict[str, str],
    *,
    allow_web_login: bool,
) -> None:
    if not shutil.which("gh"):
        raise StateRepoError("Expected 'gh' for roi_state operations. Install GitHub CLI first.")

    if env.get("GH_TOKEN") or env.get("GITHUB_TOKEN"):
        return

    status = _run_capture(["gh", "auth", "status"], env)
    if status.returncode == 0:
        return

    if not allow_web_login:
        raise StateRepoError(
            "GitHub auth is required for roi_state. Export GH_TOKEN in ~/.bashrc or run 'gh auth login' first."
        )

    login = subprocess.run(
        ["gh", "auth", "login", "--web", "--git-protocol", "https", "--skip-ssh-key"],
        check=False,
        env=env,
    )
    if login.returncode != 0:
        raise StateRepoError("GitHub web login failed.")


def _github_login(env: dict[str, str]) -> str:
    result = _run_capture(["gh", "api", "user", "--jq", ".login"], env)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "Unable to determine GitHub username."
        raise StateRepoError(stderr)
    login = result.stdout.strip()
    if not login:
        raise StateRepoError("Unable to determine GitHub username.")
    return login


def resolve_state_repo(
    config: InstallerConfig,
    env: dict[str, str],
    *,
    allow_web_login: bool,
) -> StateRepoSpec:
    ensure_github_auth(env, allow_web_login=allow_web_login)
    owner = config.state.repo_owner or _github_login(env)
    return StateRepoSpec(
        owner=owner,
        name=config.state.repo_name,
        manifest_path=config.state.manifest_path,
    )


def ensure_state_repo(
    config: InstallerConfig,
    env: dict[str, str],
    *,
    allow_web_login: bool,
) -> StateRepoSpec:
    spec = resolve_state_repo(config, env, allow_web_login=allow_web_login)
    lookup = _run_capture(["gh", "api", f"repos/{spec.slug}"], env)
    if lookup.returncode == 0:
        data = json.loads(lookup.stdout)
        if not bool(data.get("private")):
            raise StateRepoError(f"{spec.slug} exists but is not private.")
        return spec

    if not _is_not_found(lookup):
        stderr = lookup.stderr.strip() or lookup.stdout.strip() or f"Unable to inspect {spec.slug}"
        raise StateRepoError(stderr)

    auth_owner = _github_login(env)
    if spec.owner != auth_owner:
        raise StateRepoError(f"{spec.slug} does not exist and cannot be created with auth for {auth_owner}.")

    body = {
        "name": spec.name,
        "description": "Private ROI state snapshots",
        "private": True,
        "auto_init": True,
        "has_issues": False,
        "has_wiki": False,
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        json.dump(body, handle)
        payload_path = handle.name
    try:
        result = _run_capture(["gh", "api", "--method", "POST", "user/repos", "--input", payload_path], env)
    finally:
        Path(payload_path).unlink(missing_ok=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or f"Unable to create {spec.slug}"
        raise StateRepoError(stderr)
    return spec


def _manifest_endpoint(spec: StateRepoSpec) -> str:
    return f"repos/{spec.slug}/contents/{spec.manifest_path}"


def read_remote_manifest(
    config: InstallerConfig,
    env: dict[str, str],
    *,
    allow_web_login: bool,
) -> dict[str, Any]:
    spec = resolve_state_repo(config, env, allow_web_login=allow_web_login)
    entry = _run_capture(["gh", "api", _manifest_endpoint(spec)], env)
    if entry.returncode != 0:
        stderr = entry.stderr.strip() or entry.stdout.strip() or f"Unable to read {spec.slug}/{spec.manifest_path}"
        raise StateRepoError(stderr)
    data = json.loads(entry.stdout)
    if data.get("encoding") != "base64":
        raise StateRepoError(f"Unsupported manifest encoding for {spec.slug}/{spec.manifest_path}")
    payload = base64.b64decode(str(data.get("content", "")).encode("utf-8")).decode("utf-8")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise StateRepoError(f"Invalid manifest JSON in {spec.slug}/{spec.manifest_path}: {exc}") from exc


def sync_manifest(
    config: InstallerConfig,
    manifest: dict[str, Any],
    env: dict[str, str],
    *,
    allow_web_login: bool,
) -> tuple[StateRepoSpec, bool]:
    spec = ensure_state_repo(config, env, allow_web_login=allow_web_login)
    endpoint = _manifest_endpoint(spec)
    target_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    existing = _run_capture(["gh", "api", endpoint], env)
    existing_text: str | None = None
    existing_sha: str | None = None
    if existing.returncode == 0:
        data = json.loads(existing.stdout)
        if data.get("encoding") != "base64":
            raise StateRepoError(f"Unsupported manifest encoding for {spec.slug}/{spec.manifest_path}")
        existing_text = base64.b64decode(str(data.get("content", "")).encode("utf-8")).decode("utf-8")
        existing_sha = str(data.get("sha", "")).strip() or None
    elif not _is_not_found(existing):
        stderr = existing.stderr.strip() or existing.stdout.strip() or f"Unable to inspect {spec.slug}/{spec.manifest_path}"
        raise StateRepoError(stderr)

    if existing_text == target_text:
        return spec, False

    body: dict[str, Any] = {
        "message": "sync roi state",
        "content": base64.b64encode(target_text.encode("utf-8")).decode("ascii"),
        "branch": "main",
    }
    if existing_sha:
        body["sha"] = existing_sha

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        json.dump(body, handle)
        payload_path = handle.name
    try:
        update = _run_capture(["gh", "api", "--method", "PUT", endpoint, "--input", payload_path], env)
    finally:
        Path(payload_path).unlink(missing_ok=True)
    if update.returncode != 0:
        stderr = update.stderr.strip() or update.stdout.strip() or f"Unable to update {spec.slug}/{spec.manifest_path}"
        raise StateRepoError(stderr)
    return spec, True
