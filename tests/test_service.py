import os
import subprocess
import tempfile
from pathlib import Path
from unittest import mock
import unittest

import service


class TrackTimerTests(unittest.TestCase):
    def test_render_track_units_reference_daily_runner(self):
        source_root = Path("/tmp/roi")

        service_text = service.render_track_service_unit(source_root)
        timer_text = service.render_track_timer_unit()

        self.assertIn("ExecStart=/usr/bin/bash /tmp/roi/run_track_once.sh", service_text)
        self.assertIn("OnCalendar=daily", timer_text)
        self.assertIn(f"Unit={service.TRACK_SERVICE_NAME}", timer_text)

    def test_install_track_units_writes_service_and_timer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path("/tmp/roi")
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False),
                mock.patch("service._run") as run_command,
            ):
                timer_path = service.install_track_units(source_root)

            service_path = Path(temp_dir) / "systemd" / "user" / service.TRACK_SERVICE_NAME
            self.assertTrue(service_path.exists())
            self.assertTrue(timer_path.exists())
            run_command.assert_called_once_with(["systemctl", "--user", "daemon-reload"])

    def test_stop_track_timer_disables_timer(self):
        with mock.patch("service._run") as run_command:
            service.stop_track_timer()

        run_command.assert_called_once_with(["systemctl", "--user", "disable", "--now", service.TRACK_TIMER_NAME])

    def test_runner_uses_installed_launcher_without_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_root = temp_path / ".roi" / "app" / "source"
            bin_dir = temp_path / ".roi" / "bin"
            source_root.mkdir(parents=True)
            bin_dir.mkdir(parents=True)
            runner_src = Path(__file__).resolve().parents[1] / "run_track_once.sh"
            runner_dest = source_root / "run_track_once.sh"
            runner_dest.write_text(runner_src.read_text(encoding="utf-8"), encoding="utf-8")
            runner_dest.chmod(0o755)

            launcher = bin_dir / "roi"
            launcher.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf '%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            launcher.chmod(0o755)

            result = subprocess.run(
                ["/usr/bin/bash", str(runner_dest)],
                env={"HOME": str(temp_path), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "__track_once__")


if __name__ == "__main__":
    unittest.main()
