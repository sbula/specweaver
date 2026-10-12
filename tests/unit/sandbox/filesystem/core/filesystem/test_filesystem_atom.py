# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.sandbox.filesystem.core.atom — TDD.

FileSystemAtom is the engine-level counterpart (EngineFileExecutor, no protected
patterns). Its one intent, symlink, links caches into a worktree.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.filesystem.core.atom import FileSystemAtom

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with some existing structure."""
    (tmp_path / "src" / "domain" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "domain" / "billing" / "calc.py").write_text(
        "def total(a, b): return a + b",
        encoding="utf-8",
    )
    (tmp_path / "src" / "domain" / "billing" / "context.yaml").write_text(
        "name: billing\nlevel: module\npurpose: Billing logic\narchetype: pure-logic\n",
        encoding="utf-8",
    )
    (tmp_path / "context.yaml").write_text(
        "name: test-project\nlevel: system\npurpose: Test project\narchetype: orchestrator\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def atom(project: Path) -> FileSystemAtom:
    return FileSystemAtom(cwd=project)


# ===========================================================================
# Dispatch
# ===========================================================================


class TestDispatch:
    """Atom.run() dispatches to the correct intent."""

    def test_missing_intent_fails(self, atom: FileSystemAtom) -> None:
        result = atom.run({})
        assert result.status == AtomStatus.FAILED
        assert "intent" in result.message.lower()

    def test_unknown_intent_fails(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "explode"})
        assert result.status == AtomStatus.FAILED
        assert "explode" in result.message

    def test_known_intents(self, atom: FileSystemAtom) -> None:
        """symlink is the only intent."""
        assert atom._known_intents() == {"symlink"}


# ===========================================================================
# Symlink Intent
# ===========================================================================


class TestSymlinkIntent:
    """symlink intent routes correctly to file executor."""

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_valid(self, atom: FileSystemAtom, project: Path) -> None:
        """A symlink is created when its destination directory exists.

        The setup previously created only the target and left `.worktrees/agent/` absent, so
        `os.symlink` failed with ENOENT on the link's parent and the atom correctly reported
        FAILED. Combined with `skipif(os.name == "nt")` that meant this test was skipped on Windows
        and broken on Linux — it had never run to a meaningful conclusion.

        The real caller creates the worktree before linking into it, so creating the parent here is
        what makes the test match its subject. The absent-parent case is pinned separately below
        rather than left as an accident of this setup.
        """
        (project / "node_modules").mkdir()
        (project / ".worktrees" / "agent").mkdir(parents=True)

        result = atom.run(
            {
                "intent": "symlink",
                "target": "node_modules",
                "link_name": ".worktrees/agent/node_modules",
            }
        )

        assert result.status == AtomStatus.SUCCESS, result.message
        link = project / ".worktrees" / "agent" / "node_modules"
        assert link.is_symlink()
        assert link.resolve() == (project / "node_modules").resolve(), (
            "a symlink that does not point at the target would still satisfy is_symlink()"
        )

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_fails_cleanly_when_the_destination_directory_is_absent(
        self, atom: FileSystemAtom, project: Path
    ) -> None:
        """A missing parent for the link is reported, not raised.

        This is the state the test above was accidentally exercising. Pinned deliberately so the
        atom's behaviour is a decision rather than a side effect of someone's fixture.
        """
        (project / "node_modules").mkdir()

        result = atom.run(
            {
                "intent": "symlink",
                "target": "node_modules",
                "link_name": ".worktrees/agent/node_modules",
            }
        )

        assert result.status == AtomStatus.FAILED
        assert "Symlink failed" in result.message

    def test_symlink_missing_keys(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "symlink"})
        assert result.status == AtomStatus.FAILED
        assert "Missing" in result.message
