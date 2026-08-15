# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The generated units, judged by systemd rather than by us.

Proves: TECH-049 FR-10

Asserting on the text of a unit file only proves we wrote what we meant to write. `systemd-analyze
verify` is the only thing that says whether systemd will accept it, and a unit systemd rejects is a
timer that silently never runs.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mutation", REPO_ROOT / "scripts" / "mutation.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mutation"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
class TestSystemdAcceptsTheUnits:
    """`systemd-analyze verify` on what `install_timer` writes."""

    def test_both_units_verify(self, mutation: ModuleType, tmp_path: Path) -> None:
        if shutil.which("systemd-analyze") is None:
            pytest.skip("systemd-analyze is not installed — cannot ask systemd what it thinks")

        written = mutation.install_timer(tmp_path)
        done = subprocess.run(
            ["systemd-analyze", "verify", *[str(p) for p in written]],
            capture_output=True,
            text=True,
            check=False,
        )
        # Unrelated system units on the host emit deprecation notices; only our files matter.
        ours = [
            line for line in (done.stdout + done.stderr).splitlines() if mutation.UNIT_NAME in line
        ]
        assert done.returncode == 0, done.stderr
        assert ours == [], ours

    def test_the_exec_start_binary_exists(self, mutation: ModuleType) -> None:
        """A unit that names an interpreter which is not there fails only at 03:00."""
        service = mutation.timer_units()["service"]
        exec_line = next(line for line in service.splitlines() if line.startswith("ExecStart="))
        binary = exec_line.split("=", 1)[1].split()[0]
        assert Path(binary).is_file(), binary
