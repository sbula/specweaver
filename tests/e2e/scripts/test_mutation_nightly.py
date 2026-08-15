# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The journey a timer performs at 03:00, run as a command.

Proves: TECH-049 FR-10

The seam between the timer and the session is a **command line**, so this runs that exact line as a
subprocess: discover every corpus under `docs/roadmap/features`, build a sandbox, judge, write a
report, exit. Nothing here mocks anything — if the corpus, the runner, the verdicts or the report
disagree, this is where it shows.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.e2e
class TestNightlySession:
    """What the machine does while nobody is watching."""

    def test_the_timers_command_line_runs_the_real_corpus(self, tmp_path: Path) -> None:
        import sys

        out = tmp_path / "mutation_report.json"
        done = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "mutation.py"),
                "--corpus-dir",
                "docs/roadmap/features",
                "--out",
                str(out),
                "--no-baseline",
            ],
            cwd=REPO_ROOT,
            env={"PY_COLORS": "0", "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode in {0, 1}, done.stderr
        assert out.is_file(), "the nightly run must leave a report behind"

        report = json.loads(out.read_text(encoding="utf-8"))
        features = {c["feature"] for c in report["campaigns"]}
        assert "TECH-049" in features, "the corpus discovered its own first campaign"
        assert report["summary"]["declared"] == report["summary"]["returned"], (
            "accounting: every declared mutant returned a verdict"
        )
        assert "/tmp/" not in out.read_text(encoding="utf-8")
