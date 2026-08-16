# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project registered by one process is the active project in the next. TECH-054 CB-2.

Proves: TECH-054 FR-2

`E-FLOW-01` — the config DB — is the second of the two capabilities `TECH-054` picked out of
`TECH-053`'s nineteen, and like `D-FLOW-01` its whole written record is a topic-entry sentence. Every
`sw` command that resolves an active project goes through it, which is why it is here and why
seventeen others are not.

**The claim is a round trip, and it needs real processes to be one.** `sw init`, `sw use` and
`sw projects` each write or read `workspace_projects` and `workspace_active_state` and then exit;
in-process the same objects could satisfy every assertion below without SQLite being consulted once.

**The second claim is that the round trip is quiet.** `sw run --json` documents its output as
*"NDJSON event stream (machine-readable)"*, and bootstrapping the config DB used to `print()` three
schema dumps straight to **stdout** — twelve non-JSON lines ahead of the first event, on every
invocation, so anything piping the stream to a parser failed on line 1. That is the config DB
speaking over the command's own output channel, so it belongs to this journey rather than to the
runner whose contract it broke.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _sw(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """One `sw` invocation in its own process, on the isolated `SPECWEAVER_DATA_DIR`."""
    return subprocess.run(
        [sys.executable, "-m", "specweaver.interfaces.cli.main", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env={**os.environ, "COLUMNS": "200"},
        check=False,
        timeout=300,
    )


def _row(output: str, name: str) -> str:
    """The `sw projects` table row for one project, stripped of colour."""
    plain = _ANSI.sub("", output)
    rows = [line for line in plain.splitlines() if f" {name} " in line and "│" in line]
    assert len(rows) == 1, f"expected exactly one row for {name!r}, got {rows}"
    return rows[0]


def _is_active(output: str, name: str) -> bool:
    return "*" in _row(output, name).split("│")[1]


class TestTheActiveProjectSurvivesTheProcessBoundary:
    """The round trip: written by one process, read by the next, through SQLite in between."""

    def test_a_project_registered_by_one_process_is_active_in_the_next(
        self, tmp_path: Path
    ) -> None:
        """[Happy] the whole claim in two commands — the shortest journey `E-FLOW-01` has."""
        root = tmp_path / "alpha"
        root.mkdir()
        assert _sw("init", "alpha", "--path", str(root), cwd=tmp_path).returncode == 0

        listed = _sw("projects", cwd=tmp_path)

        assert listed.returncode == 0, listed.stdout + listed.stderr
        assert _is_active(listed.stdout, "alpha"), listed.stdout

    def test_switching_between_two_projects_survives_into_a_later_process(
        self, tmp_path: Path
    ) -> None:
        """[Boundary] four processes, and the second registration must not win by being last.

        `sw init beta` makes beta active; `sw use alpha` must move it back and that must be what a
        fifth process sees. A cache that outlived a single command would pass the test above and
        fail here.
        """
        for name in ("alpha", "beta"):
            (tmp_path / name).mkdir()
            assert _sw("init", name, "--path", str(tmp_path / name), cwd=tmp_path).returncode == 0

        assert _is_active(_sw("projects", cwd=tmp_path).stdout, "beta")
        assert _sw("use", "alpha", cwd=tmp_path).returncode == 0

        listed = _sw("projects", cwd=tmp_path)

        assert _is_active(listed.stdout, "alpha"), listed.stdout
        assert not _is_active(listed.stdout, "beta"), listed.stdout


class TestTheConfigDbDoesNotSpeakOverTheCommand:
    """`sw run --json` promises NDJSON. Bootstrapping the config DB used to break that promise."""

    def test_every_line_of_the_json_event_stream_parses(self, tmp_path: Path) -> None:
        """[Hostile] the assertion a consumer makes: pipe it to a parser and it must not fail.

        Deliberately not `"Base tables" not in stdout`. Naming the string that used to be printed
        would pass the moment somebody changed the wording of the debug print, while the stream
        stayed unparseable; asking whether the output is what it claims to be cannot be satisfied
        that way.
        """
        root = tmp_path / "quiet"
        root.mkdir()
        assert _sw("init", "quiet", "--path", str(root), cwd=tmp_path).returncode == 0
        (root / "specs").mkdir(exist_ok=True)
        (root / "specs" / "subject.md").write_text("# Subject\n", encoding="utf-8")

        streamed = _sw("run", "validate_only", "specs/subject.md", "--json", cwd=root)

        lines = [line for line in streamed.stdout.splitlines() if line.strip()]
        assert lines, "no output at all — the stream must exist before it can be parseable"
        unparseable = [line for line in lines if not _parses_as_json(line)]
        assert not unparseable, (
            f"{len(unparseable)} of {len(lines)} lines are not JSON, so the documented NDJSON "
            f"stream cannot be consumed. First: {unparseable[0][:120]!r}"
        )


def _parses_as_json(line: str) -> bool:
    try:
        json.loads(line)
    except ValueError:
        return False
    return True
