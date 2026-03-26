import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
MAIN = APP_ROOT / "main.py"
CONTRACT_SRC = Path.home() / "Libs" / "rgw_cli_contract" / "src"


def run_app(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base_env = os.environ.copy()
    current_pythonpath = base_env.get("PYTHONPATH", "")
    base_env["PYTHONPATH"] = str(CONTRACT_SRC) if not current_pythonpath else f"{CONTRACT_SRC}:{current_pythonpath}"
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        capture_output=True,
        text=True,
        check=False,
        env=base_env,
    )


class MainContractTests(unittest.TestCase):
    def test_no_args_matches_dash_h(self):
        no_args = run_app()
        help_args = run_app("-h")
        self.assertEqual(no_args.returncode, 0)
        self.assertEqual(no_args.stdout, help_args.stdout)

    def test_version_is_single_line(self):
        result = run_app("-v")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "0.0.0")

    def test_help_mentions_init_track_and_install(self):
        result = run_app("-h")
        self.assertEqual(result.returncode, 0)
        self.assertIn("roi init", result.stdout)
        self.assertIn("roi track", result.stdout)
        self.assertIn("roi install", result.stdout)

    def test_conf_seeds_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {"XDG_CONFIG_HOME": temp_dir, "EDITOR": "/usr/bin/true"}
            result = run_app("conf", env=env)
            self.assertEqual(result.returncode, 0)
            target = Path(temp_dir) / "roi" / "config.toml"
            self.assertTrue(target.exists())
            self.assertIn('mode = "source"', target.read_text(encoding="utf-8"))

    def test_show_reads_snapshot_from_configured_repo_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_home = temp_path / "cfg"
            repo_root = temp_path / "repo"
            snapshot_dir = repo_root / "snapshot"
            snapshot_dir.mkdir(parents=True)
            (config_home / "roi").mkdir(parents=True)
            (config_home / "roi" / "config.toml").write_text(
                "[daemon]\n"
                'mode = "source"\n'
                "poll_seconds = 300\n"
                "auto_commit = true\n"
                "auto_push = true\n"
                "auto_apply = true\n\n"
                "[paths]\n"
                f'repo_root = "{repo_root}"\n',
                encoding="utf-8",
            )
            (snapshot_dir / "system_manifest.json").write_text(
                "{\n"
                '  "active_theme": "rgwos",\n'
                '  "generated_at": "2026-03-25T00:00:00+00:00",\n'
                '  "packages": {"explicit": ["git"]},\n'
                '  "repos": {"Apps": [], "Libs": [], "Work": []},\n'
                '  "source_hostname": "test",\n'
                '  "themes": []\n'
                "}\n",
                encoding="utf-8",
            )

            result = run_app("show", env={"XDG_CONFIG_HOME": str(config_home)})

            self.assertEqual(result.returncode, 0)
            self.assertIn("active theme: rgwos", result.stdout)


if __name__ == "__main__":
    unittest.main()
