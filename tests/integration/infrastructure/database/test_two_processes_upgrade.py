# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Two processes that open a new file at the same moment apply each schema step once.

Proves: TECH-090 FR-3

Real processes, not threads: only separate processes prove the file lock (plan Q4). Each child
waits for a start file, so both reach `upgrade` together; step 1 sleeps inside its transaction so
the second process must wait for the lock and then find the step done.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
import time
from contextlib import closing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_CHILD = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from specweaver.infrastructure.database import Step, upgrade

    db, go = Path(sys.argv[1]), Path(sys.argv[2])
    while not go.exists():
        time.sleep(0.01)

    def one(conn):
        conn.execute("CREATE TABLE applied (step TEXT)")
        conn.execute("INSERT INTO applied VALUES ('one')")
        time.sleep(0.5)

    def two(conn):
        conn.execute("INSERT INTO applied VALUES ('two')")

    upgrade(db, [Step(1, "one", one), Step(2, "two", two)])
    """
)


def test_each_step_runs_once_when_two_processes_start_together(tmp_path: Path) -> None:
    db, go = tmp_path / "shared.db", tmp_path / "go"
    children = [
        subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(db), str(go)], stderr=subprocess.PIPE, text=True
        )
        for _ in range(2)
    ]
    time.sleep(0.5)
    go.touch()

    errors = [child.communicate(timeout=60)[1] for child in children]

    assert [child.returncode for child in children] == [0, 0], errors
    with closing(sqlite3.connect(db)) as conn:
        steps = [row[0] for row in conn.execute("SELECT step FROM applied ORDER BY rowid")]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert steps == ["one", "two"]
    assert version == 2
