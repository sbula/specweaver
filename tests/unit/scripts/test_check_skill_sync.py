# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the skill-tree sync guard (`scripts/check_skill_sync.py`).

The guard shipped with no tests, which is its own finding: it was only ever exercised against the
live trees, where the Claude Code harness mirrors both sides in real time and silently repairs any
drift. A rule that stopped firing there would look exactly like a clean tree.

The symlink case is the one that mattered in practice. `.claude/skills/grill-me` was replaced by a
symlink to `.agents/skills/grill-me` — the two sides could no longer drift at all — and the guard
reported both files MISSING, because `Path.rglob` does not descend into symlinked directories. A
symlink is a STRONGER guarantee than a copy, so reporting it as drift inverts the rule.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def css() -> ModuleType:
    return _load("check_skill_sync")


def _trees(root: Path) -> tuple[Path, Path]:
    """Two skill trees holding one identical skill."""
    left, right = root / "claude" / "skills", root / "agents" / "skills"
    for side in (left, right):
        (side / "demo").mkdir(parents=True)
        (side / "demo" / "SKILL.md").write_text("same\n", encoding="utf-8")
    return left, right


class TestPlainTrees:
    """The behaviour the guard already had, pinned so the symlink fix cannot regress it."""

    def test_identical_trees_pass(self, css: ModuleType, tmp_path: Path) -> None:
        left, right = _trees(tmp_path)
        assert css.main([str(left), str(right)]) == 0

    def test_a_file_missing_on_one_side_is_reported(
        self, css: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        left, right = _trees(tmp_path)
        (right / "demo" / "extra.md").write_text("only here\n", encoding="utf-8")

        assert css.main([str(left), str(right)]) == 1
        assert "extra.md" in capsys.readouterr().out

    def test_differing_content_is_reported(
        self, css: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        left, right = _trees(tmp_path)
        (left / "demo" / "SKILL.md").write_text("drifted\n", encoding="utf-8")

        assert css.main([str(left), str(right)]) == 1
        assert "DIFFERS" in capsys.readouterr().out

    def test_neither_tree_present_is_not_a_failure(self, css: ModuleType, tmp_path: Path) -> None:
        assert css.main([str(tmp_path / "a"), str(tmp_path / "b")]) == 0


class TestSymlinkedSkill:
    """A skill directory replaced by a symlink to the other tree cannot drift, so it is in sync."""

    def test_a_symlinked_skill_directory_is_in_sync(self, css: ModuleType, tmp_path: Path) -> None:
        left, right = _trees(tmp_path)
        linked = left / "linked"
        (right / "linked").mkdir()
        (right / "linked" / "SKILL.md").write_text("pointer\n", encoding="utf-8")
        linked.symlink_to(right / "linked", target_is_directory=True)

        assert css.main([str(left), str(right)]) == 0

    def test_a_symlink_to_different_content_is_still_reported(
        self, css: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The fix must not become a blanket pass for anything behind a symlink."""
        left, right = _trees(tmp_path)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "SKILL.md").write_text("wrong\n", encoding="utf-8")
        (right / "linked").mkdir()
        (right / "linked" / "SKILL.md").write_text("right\n", encoding="utf-8")
        (left / "linked").symlink_to(elsewhere, target_is_directory=True)

        assert css.main([str(left), str(right)]) == 1
        assert "DIFFERS" in capsys.readouterr().out

    def test_a_symlinked_file_is_read_through(self, css: ModuleType, tmp_path: Path) -> None:
        left, right = _trees(tmp_path)
        (left / "demo" / "SKILL.md").unlink()
        (left / "demo" / "SKILL.md").symlink_to(right / "demo" / "SKILL.md")

        assert css.main([str(left), str(right)]) == 0

    def test_a_symlink_cycle_terminates(self, css: ModuleType, tmp_path: Path) -> None:
        """`followlinks` walks into a self-referential link forever without a visited set."""
        left, right = _trees(tmp_path)
        (left / "demo" / "loop").symlink_to(left / "demo", target_is_directory=True)
        (right / "demo" / "loop").symlink_to(right / "demo", target_is_directory=True)

        assert css.main([str(left), str(right)]) in (0, 1)
