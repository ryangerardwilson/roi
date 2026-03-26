from pathlib import Path
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
            mock.patch("engine._install_themes", side_effect=lambda *args, **kwargs: events.append("themes")) as install_themes,
            mock.patch("engine._ensure_required_dirs", side_effect=lambda *args, **kwargs: events.append("dirs")) as ensure_dirs,
            mock.patch("engine._sync_repo_group", side_effect=lambda *args, **kwargs: events.append(f"repo:{args[2]}")) as sync_repo_group,
            mock.patch("engine._sync_packages", side_effect=lambda *args, **kwargs: events.append("packages")) as sync_packages,
            mock.patch("engine._apply_keyd_km_special_cases", side_effect=lambda *args, **kwargs: events.append("special")) as apply_specials,
        ):
            engine.apply_manifest(manifest, home_dir)

        self.assertEqual(
            events,
            ["auth", "home", "env", "dirs", "packages", "themes", "repo:Apps", "repo:Libs", "repo:Work", "special"],
        )
        install_themes.assert_called_once_with(manifest, home_dir, env=runtime_env)
        ensure_dirs.assert_called_once_with(manifest, home_dir)
        self.assertEqual(sync_repo_group.call_count, 3)
        sync_repo_group.assert_any_call(manifest, home_dir, "Apps", env=runtime_env)
        sync_repo_group.assert_any_call(manifest, home_dir, "Libs", env=runtime_env)
        sync_repo_group.assert_any_call(manifest, home_dir, "Work", env=runtime_env)
        sync_packages.assert_called_once_with(manifest, env=runtime_env)
        apply_specials.assert_called_once_with(manifest, home_dir, env=runtime_env)

    def test_initialize_state_repo_loads_shell_env_and_syncs_remote_state(self):
        config = mock.Mock()
        home_dir = Path("/tmp/test-home")
        runtime_env = {"HOME": str(home_dir), "GH_TOKEN": "from-bashrc"}
        manifest = {"schema_version": 1}
        spec = mock.Mock(slug="example/roi_state", manifest_path="system_manifest.json")

        with (
            mock.patch("engine._load_home_shell_env", return_value=runtime_env),
            mock.patch("engine.capture_manifest", return_value=manifest) as capture_manifest,
            mock.patch("engine.sync_manifest", return_value=(spec, True)) as sync_manifest,
            mock.patch("engine.notify_snapshot_synced") as notify_snapshot_synced,
        ):
            changed = engine.initialize_state_repo(config, home_dir)

        self.assertTrue(changed)
        capture_manifest.assert_called_once_with(home_dir)
        sync_manifest.assert_called_once_with(config, manifest, runtime_env, allow_web_login=True)
        notify_snapshot_synced.assert_called_once_with("example/roi_state")

    def test_initialize_state_repo_skips_notification_when_manifest_is_unchanged(self):
        config = mock.Mock()
        home_dir = Path("/tmp/test-home")
        runtime_env = {"HOME": str(home_dir), "GH_TOKEN": "from-bashrc"}
        manifest = {"schema_version": 1}
        spec = mock.Mock(slug="example/roi_state", manifest_path="system_manifest.json")

        with (
            mock.patch("engine._load_home_shell_env", return_value=runtime_env),
            mock.patch("engine.capture_manifest", return_value=manifest),
            mock.patch("engine.sync_manifest", return_value=(spec, False)),
            mock.patch("engine.notify_snapshot_synced") as notify_snapshot_synced,
        ):
            changed = engine.initialize_state_repo(config, home_dir)

        self.assertFalse(changed)
        notify_snapshot_synced.assert_not_called()

    def test_install_from_state_repo_downloads_then_applies(self):
        config = mock.Mock()
        home_dir = Path("/tmp/test-home")
        env = {"HOME": str(home_dir)}
        manifest = {"schema_version": 1}

        with (
            mock.patch("engine._command_env", return_value=env) as command_env,
            mock.patch("engine.read_remote_manifest", return_value=manifest) as read_remote_manifest,
            mock.patch("engine.apply_manifest") as apply_manifest,
        ):
            engine.install_from_state_repo(config, home_dir)

        command_env.assert_called_once_with(home_dir)
        read_remote_manifest.assert_called_once_with(config, env, allow_web_login=True)
        apply_manifest.assert_called_once_with(manifest, home_dir)

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

    def test_install_themes_syncs_manifest_name_then_activates_it(self):
        manifest = {
            "themes": [
                {
                    "name": "rgwos",
                    "remote_url": "https://github.com/ryangerardwilson/omarchy-mono-dark-theme.git",
                    "branch": "main",
                }
            ],
            "active_theme": "rgwos",
        }
        home_dir = Path("/tmp/test-home")
        env = {"HOME": str(home_dir)}

        with (
            mock.patch("engine._ensure_omarchy_commands", return_value="/usr/bin/omarchy-theme-set"),
            mock.patch("engine._pull_checkout") as pull_checkout,
            mock.patch("engine._run") as run,
        ):
            engine._install_themes(manifest, home_dir, env=env)

        pull_checkout.assert_called_once_with(
            home_dir / ".config" / "omarchy" / "themes" / "rgwos",
            "https://github.com/ryangerardwilson/omarchy-mono-dark-theme.git",
            "main",
            env=env,
        )
        run.assert_called_once_with(["/usr/bin/omarchy-theme-set", "rgwos"], env=env)

    def test_apply_keyd_km_special_cases_enables_service_and_runs_km(self):
        manifest = {"packages": {"explicit": ["keyd"], "official": [], "foreign": []}}
        home_dir = Path("/tmp/test-home")
        env = {"HOME": str(home_dir)}

        with (
            mock.patch("engine._run") as run,
            mock.patch("pathlib.Path.exists", autospec=True, side_effect=lambda path: str(path) in {
                str(home_dir / ".local" / "bin" / "km"),
            }),
        ):
            engine._apply_keyd_km_special_cases(manifest, home_dir, env=env)

        run.assert_any_call(["sudo", "systemctl", "enable", "--now", "keyd.service"], env=env)
        run.assert_any_call([str(home_dir / ".local" / "bin" / "km"), "apply"], env=env)

    def test_run_track_once_syncs_remote_state(self):
        config = mock.Mock()
        home_dir = Path("/tmp/home")
        runtime_env = {"HOME": str(home_dir), "GH_TOKEN": "from-bashrc"}
        manifest = {"schema_version": 1}
        spec = mock.Mock(slug="example/roi_state", manifest_path="system_manifest.json")
        with (
            mock.patch("engine._load_home_shell_env", return_value=runtime_env),
            mock.patch("engine.capture_manifest", return_value=manifest) as capture_manifest,
            mock.patch("engine.sync_manifest", return_value=(spec, True)) as sync_manifest,
            mock.patch("engine.notify_snapshot_synced") as notify_snapshot_synced,
        ):
            changed = engine.run_track_once(config, home_dir)

        self.assertTrue(changed)
        capture_manifest.assert_called_once_with(home_dir)
        sync_manifest.assert_called_once_with(config, manifest, runtime_env, allow_web_login=False)
        notify_snapshot_synced.assert_called_once_with("example/roi_state")

    def test_run_track_once_skips_notification_when_manifest_is_unchanged(self):
        config = mock.Mock()
        home_dir = Path("/tmp/home")
        runtime_env = {"HOME": str(home_dir), "GH_TOKEN": "from-bashrc"}
        manifest = {"schema_version": 1}
        spec = mock.Mock(slug="example/roi_state", manifest_path="system_manifest.json")
        with (
            mock.patch("engine._load_home_shell_env", return_value=runtime_env),
            mock.patch("engine.capture_manifest", return_value=manifest),
            mock.patch("engine.sync_manifest", return_value=(spec, False)),
            mock.patch("engine.notify_snapshot_synced") as notify_snapshot_synced,
        ):
            changed = engine.run_track_once(config, home_dir)

        self.assertFalse(changed)
        notify_snapshot_synced.assert_not_called()


if __name__ == "__main__":
    unittest.main()
