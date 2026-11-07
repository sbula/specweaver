# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""On a fresh machine, help opens no database, and the first real command makes a current one.

Each step is its own `sw` process, as a user types it, on an empty data dir.

Proves: TECH-090 FR-7, FR-8 (paths P-1, P-5)
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e


def _sw(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "SPECWEAVER_DATA_DIR": str(data_dir)}
    return subprocess.run(
        [sys.executable, "-m", "specweaver.interfaces.cli.main", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )


def test_a_fresh_machine_gets_help_without_a_database_then_a_current_one(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    root = tmp_path / "demo"
    root.mkdir()

    helped = _sw(data_dir, "run", "--help")

    assert helped.returncode == 0, helped.stderr
    assert "Usage" in helped.stdout
    assert sorted(data_dir.glob("*.db")) == []

    made = _sw(data_dir, "init", "demo", "--path", str(root))

    assert made.returncode == 0, made.stdout + made.stderr
    with closing(sqlite3.connect(data_dir / "specweaver.db")) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("SELECT name FROM workspace_projects").fetchall() == [("demo",)]
