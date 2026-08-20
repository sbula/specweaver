# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The corpus maintenance command, run the way a person runs it.

Proves: TECH-049 FR-13

`main()` is exercised in-process by the unit tests, which proves the argument wiring and nothing
about whether the file is executable, whether its imports resolve outside a test harness, or what
a shell actually sees on stdout and stderr. This runs the real command as a subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "_corpus.py"

_SOURCE = '''\
"""Module docstring."""


def apply_session_policy(policy):
    """Decide whether the run is isolated."""
    return policy.enabled
'''


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "isolation.py").write_text(_SOURCE, encoding="utf-8")
    body = {
        "schema": 2,
        "feature": "C-EXEC-06",
        "campaigns": [
            {
                "requirement": "FR-98",
                "scope": ["tests/e2e/x.py"],
                "mutants": [
                    {
                        "id": "isolation-off",
                        "origin": "authored",
                        "file": "isolation.py",
                        "symbol": "apply_session_policy",
                        "old": "return policy.enabled",
                        "new": "return False",
                        "breaks": "isolation never engages",
                    }
                ],
            }
        ],
    }
    path = tmp_path / "C-EXEC-06_mutants.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path, tmp_path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


@pytest.mark.e2e
class TestCorpusCli:
    """Exit codes and streams, as a shell would see them."""

    def test_refresh_pins_and_prints_the_hash(self, workspace: tuple[Path, Path]) -> None:
        path, root = workspace
        done = _run(
            "--corpus", str(path), "--root", str(root), "--refresh", "C-EXEC-06 FR-98 isolation-off"
        )
        assert done.returncode == 0, done.stderr
        assert "sha256:" in done.stdout
        assert "symbol_sha" in path.read_text(encoding="utf-8")

    def test_retire_marks_the_campaign(self, workspace: tuple[Path, Path]) -> None:
        path, _ = workspace
        done = _run("--corpus", str(path), "--retire", "FR-98", "--reason", "descoped")
        assert done.returncode == 0, done.stderr
        assert "retired" in done.stdout
        assert "descoped" in path.read_text(encoding="utf-8")

    def test_an_unknown_mutant_exits_two_on_stderr(self, workspace: tuple[Path, Path]) -> None:
        path, root = workspace
        done = _run("--corpus", str(path), "--root", str(root), "--refresh", "C-EXEC-06 FR-98 nope")
        assert done.returncode == 2
        assert "nope" in done.stderr
        assert done.stdout == ""

    def test_no_action_is_a_usage_error(self, workspace: tuple[Path, Path]) -> None:
        path, _ = workspace
        done = _run("--corpus", str(path))
        assert done.returncode == 2
        assert "one of the arguments" in done.stderr
