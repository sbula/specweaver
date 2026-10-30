# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Standards discovery finds the files git would, without running git.

Proves: TECH-087 FR-16
Proves: TECH-087 NFR-4

The expected set comes from real git on the fixture. Discovery runs on a copy with no `.git`: before
FR-16, a `.git` made discovery call `git ls-files`, which would make the equality true by
construction.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.standards.discovery import discover_files
from specweaver.workspace.analyzers.factory import AnalyzerFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")

_FIXTURE = {
    ".gitignore": "*.log\nscratch/\n/top_only.py\n",
    "src/app.py": "pass\n",
    "src/app.log": "noise\n",
    "src/top_only.py": "pass\n",
    "top_only.py": "pass\n",
    "scratch/note.py": "pass\n",
    "pkg/.gitignore": "generated.py\n!keep.log\n/local.py\n",
    "pkg/mod.py": "pass\n",
    "pkg/generated.py": "pass\n",
    "pkg/keep.log": "kept\n",
    "pkg/local.py": "pass\n",
    "pkg/sub/local.py": "pass\n",
    "pkg/sub/generated.py": "pass\n",
    "untracked.py": "pass\n",
}


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel, body in _FIXTURE.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding="utf-8")
    _git(root, "init", "-q")
    tracked = [".gitignore", "pkg/.gitignore", "src/app.py", "pkg/mod.py", "pkg/keep.log"]
    _git(root, "add", *tracked)
    assert set(_git(root, "ls-files", "--cached").split()) == set(tracked)
    return root


def test_discovery_finds_exactly_what_git_lists(repo: Path, tmp_path: Path) -> None:
    expected = set(_git(repo, "ls-files", "--cached", "--others", "--exclude-standard").split())
    copy = tmp_path / "copy"
    shutil.copytree(repo, copy, ignore=shutil.ignore_patterns(".git"))

    found = {
        p.relative_to(copy.resolve()).as_posix() for p in discover_files(copy, AnalyzerFactory)
    }

    assert found == expected
    # The fixture is only worth its equality if git really dropped something at each level.
    assert {"src/app.log", "scratch/note.py", "pkg/generated.py", "pkg/local.py"}.isdisjoint(found)
    assert {"pkg/keep.log", "pkg/sub/local.py", "src/top_only.py"} <= found
