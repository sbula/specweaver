# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Shared fixtures for integration tests.

Provides a standard sample project that multiple test files can run against.
Each test gets an isolated copy in ``tmp_path`` — auto-cleaned by pytest
even on abort.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.config.database import Database

# Path to the static fixture project (relative to repo root)
_FIXTURE_ROOT = (
    __import__("pathlib").Path(__file__).resolve().parent.parent / "fixtures" / "sample_project"
)


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Copy the sample project fixture into an isolated tmp_path.

    Returns the root Path of the copied project. The copy is fully
    independent — tests can modify files freely without affecting
    the static fixture or other tests.

    Layout of the returned project:
        <tmp_path>/sample_project/
            pyproject.toml
            specs/calculator.md
            src/greeter/          ← clean module
            src/broken/           ← lint errors + high complexity
            src/no_context/       ← no context.yaml (for inference)
    """
    dest = tmp_path / "sample_project"
    shutil.copytree(_FIXTURE_ROOT, dest)
    return dest


@pytest.fixture()
def sample_db(tmp_path: Path, sample_project: Path) -> Database:
    """Create a Database with the sample project registered.

    Returns a Database instance backed by SQLite in ``tmp_path``.
    The sample project is pre-registered as ``"sample"``.
    """
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver" / "specweaver.db")
    db.register_project("sample", str(sample_project))
    return db
