import os
import tempfile
from pathlib import Path
from unittest import mock
import unittest

import service


class TrackTimerTests(unittest.TestCase):
    def test_render_track_units_reference_daily_runner(self):
        source_root = Path("/tmp/rgw_omarchy_installer")

        service_text = service.render_track_service_unit(source_root)
        timer_text = service.render_track_timer_unit()

        self.assertIn("ExecStart=/usr/bin/bash /tmp/rgw_omarchy_installer/run_track_once.sh", service_text)
        self.assertIn("OnCalendar=daily", timer_text)
        self.assertIn(f"Unit={service.TRACK_SERVICE_NAME}", timer_text)

    def test_install_track_units_writes_service_and_timer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path("/tmp/rgw_omarchy_installer")
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False),
                mock.patch("service._run") as run_command,
            ):
                timer_path = service.install_track_units(source_root)

            service_path = Path(temp_dir) / "systemd" / "user" / service.TRACK_SERVICE_NAME
            self.assertTrue(service_path.exists())
            self.assertTrue(timer_path.exists())
            run_command.assert_called_once_with(["systemctl", "--user", "daemon-reload"])


if __name__ == "__main__":
    unittest.main()
