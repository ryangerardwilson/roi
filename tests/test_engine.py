from pathlib import Path
import tempfile
from unittest import mock
import unittest

import engine


class EngineBootstrapTests(unittest.TestCase):
    def test_apply_manifest_authenticates_then_loads_shell_env_for_follow_on_steps(self):
        manifest = {
            "home_repo": {
                "remote_url": "https://github.com/example/home.git",
                "branch": "main",
            },
            "repos": {"Apps": [], "Libs": [], "Work": []},
            "themes": [],
            "packages": {"explicit": [], "official": [], "foreign": [], "manager": "yay"},
        }
        home_dir = Path("/tmp/test-home")
        runtime_env = {"HOME": str(home_dir), "GH_TOKEN": "from-bashrc"}
        events: list[str] = []

        with (
            mock.patch("engine._ensure_github_auth", side_effect=lambda *args, **kwargs: events.append("auth")),
            mock.patch("engine._bootstrap_home_repo", side_effect=lambda *args, **kwargs: events.append("home")),
            mock.patch("engine._load_home_shell_env", side_effect=lambda *args, **kwargs: events.append("env") or runtime_env),
            mock.patch("engine._install_themes") as install_themes,
            mock.patch("engine._ensure_required_dirs") as ensure_dirs,
            mock.patch("engine._sync_repo_group") as sync_repo_group,
            mock.patch("engine._sync_packages") as sync_packages,
        ):
            engine.apply_manifest(manifest, home_dir)

        self.assertEqual(events[:3], ["auth", "home", "env"])
        install_themes.assert_called_once_with(manifest, env=runtime_env)
        ensure_dirs.assert_called_once_with(manifest, home_dir)
        self.assertEqual(sync_repo_group.call_count, 3)
        sync_repo_group.assert_any_call(manifest, home_dir, "Apps", env=runtime_env)
        sync_repo_group.assert_any_call(manifest, home_dir, "Libs", env=runtime_env)
        sync_repo_group.assert_any_call(manifest, home_dir, "Work", env=runtime_env)
        sync_packages.assert_called_once_with(manifest, env=runtime_env)

    def test_ensure_github_auth_uses_web_login_when_no_auth_exists(self):
        home_dir = Path("/tmp/test-home")
        with (
            mock.patch("engine.shutil.which", return_value="/usr/bin/gh"),
            mock.patch("engine._capture", return_value="") as capture,
            mock.patch("engine._run") as run,
        ):
            engine._ensure_github_auth("https://github.com/example/private.git", home_dir)

        capture.assert_called_once()
        run.assert_has_calls(
            [
                mock.call(
                    ["gh", "auth", "login", "--web", "--git-protocol", "https", "--skip-ssh-key"],
                    env=mock.ANY,
                ),
                mock.call(["gh", "auth", "setup-git"], env=mock.ANY),
            ]
        )

    def test_run_track_once_commits_only_when_snapshot_changes(self):
        repo_root = Path("/tmp/repo")
        home_dir = Path("/tmp/home")
        with (
            mock.patch("engine._pull_self_repo_if_safe") as pull_self,
            mock.patch("engine.sync_snapshot", return_value=True) as sync_snapshot,
            mock.patch("engine.maybe_commit_snapshot") as commit_snapshot,
        ):
            changed = engine.run_track_once(
                repo_root,
                home_dir,
                auto_commit=True,
                auto_push=True,
            )

        self.assertTrue(changed)
        pull_self.assert_called_once_with(repo_root)
        sync_snapshot.assert_called_once_with(repo_root, home_dir)
        commit_snapshot.assert_called_once_with(repo_root, auto_push=True)

    def test_maybe_commit_snapshot_pushes_origin_main(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / ".git").mkdir()
            with (
                mock.patch("engine._track_branch_ready", return_value=True),
                mock.patch("engine._git_status_paths", return_value=["snapshot/system_manifest.json"]),
                mock.patch("engine._run") as run,
            ):
                committed = engine.maybe_commit_snapshot(repo_root, auto_push=True)

        self.assertTrue(committed)
        self.assertIn(
            mock.call(["git", "-C", str(repo_root), "push", "origin", "main"]),
            run.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
