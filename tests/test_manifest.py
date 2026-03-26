import subprocess
import tempfile
from pathlib import Path
from unittest import mock
import unittest

from manifest import capture_manifest


def init_repo(path: Path, remote_url: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "README.md"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


class ManifestCaptureTests(unittest.TestCase):
    def test_capture_manifest_discovers_home_repo_themes_repos_and_packages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            init_repo(home_dir, "https://github.com/example/home.git")

            app_repo = home_dir / "Apps" / "demo"
            init_repo(app_repo, "https://github.com/example/demo.git")
            (app_repo / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            self_repo = home_dir / "Apps" / "roi"
            init_repo(self_repo, "https://github.com/example/roi.git")
            (self_repo / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            lib_repo = home_dir / "Libs" / "libdemo"
            init_repo(lib_repo, "https://github.com/example/libdemo.git")

            work_repo = home_dir / "Work" / "workdemo"
            init_repo(work_repo, "https://github.com/example/workdemo.git")

            theme_repo = home_dir / ".config" / "omarchy" / "themes" / "rgwos"
            init_repo(theme_repo, "https://github.com/example/rgwos.git")
            active_theme_path = home_dir / ".config" / "omarchy" / "current"
            active_theme_path.mkdir(parents=True, exist_ok=True)
            (active_theme_path / "theme.name").write_text("rgwos\n", encoding="utf-8")

            with mock.patch(
                "manifest.discover_packages",
                return_value={"manager": "yay", "official": ["git"], "foreign": [], "explicit": ["git"]},
            ), mock.patch(
                "manifest.discover_mise_state",
                return_value={
                    "tools": [{"name": "node", "version": "25.8.0"}],
                    "npm_globals": [{"name": "@openai/codex", "version": "0.116.0"}],
                },
            ):
                manifest = capture_manifest(home_dir)

            self.assertEqual(manifest["home_repo"]["remote_url"], "https://github.com/example/home.git")
            self.assertEqual(manifest["active_theme"], "rgwos")
            self.assertEqual(len(manifest["themes"]), 1)
            self.assertEqual(len(manifest["repos"]["Apps"]), 2)
            demo_spec = next(spec for spec in manifest["repos"]["Apps"] if spec["name"] == "demo")
            self.assertTrue(demo_spec["install_via_script"])
            self_spec = next(spec for spec in manifest["repos"]["Apps"] if spec["name"] == "roi")
            self.assertFalse(self_spec["install_via_script"])
            self.assertEqual(manifest["packages"]["explicit"], ["git"])
            self.assertEqual(manifest["mise"]["tools"][0]["name"], "node")
            self.assertEqual(manifest["mise"]["npm_globals"][0]["name"], "@openai/codex")

    def test_capture_manifest_ignores_directories_that_only_live_inside_home_repo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            init_repo(home_dir, "https://github.com/example/home.git")

            nested_app = home_dir / "Apps" / "nested-only"
            nested_app.mkdir(parents=True, exist_ok=True)
            (nested_app / "README.md").write_text("nested\n", encoding="utf-8")

            with mock.patch(
                "manifest.discover_packages",
                return_value={"manager": "yay", "official": ["git"], "foreign": [], "explicit": ["git"]},
            ), mock.patch(
                "manifest.discover_mise_state",
                return_value={"tools": [], "npm_globals": []},
            ):
                manifest = capture_manifest(home_dir)

            self.assertEqual(manifest["repos"]["Apps"], [])


if __name__ == "__main__":
    unittest.main()
