from pathlib import Path
import unittest


class ReleaseBundleTests(unittest.TestCase):
    def test_release_workflow_includes_notifications_module(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("notifications.py", workflow)


if __name__ == "__main__":
    unittest.main()
