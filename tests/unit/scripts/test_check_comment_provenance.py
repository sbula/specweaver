# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the comment-provenance guard (`scripts/check_comment_provenance.py`).

Code is a document of the present. A comment naming the ticket that paid for a line adds nothing at
the point of reading — git already holds that — and it rots independently of the code beside it:
`ADR-004` changed what every `INT-US` entry means, which stranded 104 references in `src/` naming a
scope their authors did not intend.

`TECH-059` removed 256 such references across ~130 files. Without a gate the next commit citing a
ticket in a comment puts the debt straight back, which is the documented failure mode of every
discipline-only clause in this repo.

Zero-tolerance rather than ratcheted: the sweep reached zero, so there is no legacy set to carry.

The `Proves:` carve-out is load-bearing in the other direction — those tags live in `tests/` and are
read by `check_fr_coverage.py`, so this guard is scoped to `src/` and never sees them. Setting two
gates against each other is exactly what R5 in `check_conventions.py` warns about.

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
def ccp() -> ModuleType:
    return _load("check_comment_provenance")


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sample.py"
    path.write_text(body, encoding="utf-8")
    return path


class TestOffendingProse:
    """One finding per comment or docstring line naming a registry ID."""

    @pytest.mark.parametrize(
        "ident",
        ["INT-US-24", "INT-US-01-SF02", "INT-US-21-SUB", "TECH-059", "C-EXEC-06", "B-FLOW-05"],
    )
    def test_every_id_family_is_caught_in_a_comment(
        self, ccp: ModuleType, tmp_path: Path, ident: str
    ) -> None:
        path = _write(tmp_path, f"# {ident}: why this line exists\nx = 1\n")
        assert len(ccp.offending_prose(path)) == 1

    def test_an_id_in_a_docstring_is_caught(self, ccp: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, '"""Module.\n\nSplit out by `TECH-015`.\n"""\nx = 1\n')
        assert len(ccp.offending_prose(path)) == 1

    def test_an_id_in_a_function_docstring_is_caught(self, ccp: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, 'def f() -> None:\n    """Do it (C-EXEC-06)."""\n')
        assert len(ccp.offending_prose(path)) == 1

    def test_the_message_names_the_line_and_the_id(self, ccp: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, "x = 1\n# TECH-041 is why\ny = 2\n")
        (message,) = ccp.offending_prose(path)
        assert ":2" in message
        assert "TECH-041" in message

    def test_clean_prose_passes(self, ccp: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, '"""Real docs."""\n# a present-tense explanation\nx = 1\n')
        assert ccp.offending_prose(path) == []

    def test_an_id_in_live_code_is_not_a_comment(self, ccp: ModuleType, tmp_path: Path) -> None:
        """The guard judges prose. A string literal is behaviour, and rewriting it is a code change.

        `engine/session.py` puts `C-EXEC-06` in four user-facing error messages and
        `mcp/interfaces/tool.py` holds `"protocolVersion": "2024-11-05"`. Both are out of scope.
        """
        path = _write(tmp_path, 'MSG = "C-EXEC-06 session isolation failed"\nV = "2024-11-05"\n')
        assert ccp.offending_prose(path) == []

    def test_validation_rule_ids_are_not_registry_ids(
        self, ccp: ModuleType, tmp_path: Path
    ) -> None:
        """`C01`..`C13`, `S07` name validation rules — domain vocabulary, not tickets.

        R5 in `check_conventions.py` records the same trap: a looser `[A-Z]\\d{2}` pattern flags ten
        legitimate names and the reflex fix is a fresh allowlist.
        """
        path = _write(tmp_path, "# C09 @trace tags and S07 sections are required\nx = 1\n")
        assert ccp.offending_prose(path) == []

    def test_multiple_ids_on_one_line_report_once(self, ccp: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, "# TECH-012 and TECH-021 both\nx = 1\n")
        assert len(ccp.offending_prose(path)) == 1


class TestMain:
    """The CLI contract `quality.py` depends on: 0 clean, 1 on any finding."""

    def test_exits_one_and_names_the_offender(
        self, ccp: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write(tmp_path, "# TECH-059 did this\nx = 1\n")
        assert ccp.main([str(path)]) == 1
        assert "TECH-059" in capsys.readouterr().out

    def test_exits_zero_on_clean_paths(self, ccp: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, "# clean\nx = 1\n")
        assert ccp.main([str(path)]) == 0

    def test_a_syntactically_broken_file_is_not_a_silent_pass(
        self, ccp: ModuleType, tmp_path: Path
    ) -> None:
        """`TECH-032`'s lesson: a checker that cannot read its subject must say so, never pass."""
        path = _write(tmp_path, "def (:\n")
        assert ccp.main([str(path)]) == 1

    def test_the_live_src_tree_is_clean(self, ccp: ModuleType) -> None:
        """Ratcheted at zero because `TECH-059` reached zero. This is what holds it there."""
        assert ccp.main([str(REPO_ROOT / "src")]) == 0
