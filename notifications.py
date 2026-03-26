from __future__ import annotations

import shutil
import subprocess


def notify_snapshot_synced(repo_slug: str) -> None:
    if not shutil.which("notify-send"):
        return

    subprocess.run(
        [
            "notify-send",
            "-t",
            "5000",
            "roi",
            f"Snapshot synced to {repo_slug}",
        ],
        check=False,
    )
