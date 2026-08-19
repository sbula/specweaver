# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The native boundary linter really runs, and its findings really merge with `forbids`.

Proves: C-VAL-03 FR-5

FR-5 outsources cross-boundary isolation to *"the native boundary linter through the QA runner,
merged with per-file `forbids`"*. Its citation, `test_tach_and_forbids_merged`, patches
`_run_tach_check` and hands the merge a hand-built `ArchitectureRunResult` — so the merge is proven
against a fake linter and the outsourcing is proven against nothing.

A seam FR proven by a unit test with the other side mocked proves the mock, which is `TECH-041`'s
finding for this capability: *proven link by link, never as a chain*. Here the missing link is the
linter itself.

So this runs real `tach` over a real project with a real `tach.toml`, alongside a real
`context.yaml` `forbids` entry, and asserts both kinds of finding come back from one call.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.language.core.python.runner import PythonQARunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

needs_tach = pytest.mark.skipif(shutil.which("tach") is None, reason="tach is not on PATH")

#: Two modules, and `low` may depend on nothing. `high` importing it is the violation tach reports.
TACH_TOML = """\
source_roots = ["."]

[[modules]]
path = "high"
depends_on = ["low"]

[[modules]]
path = "low"
depends_on = []
"""


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "high").mkdir(parents=True)
    (root / "low").mkdir()
    (root / "tach.toml").write_text(TACH_TOML, encoding="utf-8")
    for package in ("high", "low"):
        (root / package / "__init__.py").write_text("", encoding="utf-8")

    # `low` importing `high` inverts the declared direction — tach's own finding.
    (root / "low" / "leak.py").write_text("from high import thing\n", encoding="utf-8")
    (root / "high" / "thing.py").write_text("value = 1\n", encoding="utf-8")

    # And a per-file `forbids`, which is the other half of the merge.
    (root / "high" / "context.yaml").write_text(
        "name: high\npurpose: Upper layer.\narchetype: pure-logic\nforbids:\n  - low/*\n",
        encoding="utf-8",
    )
    # `from low.leak import ...`, not `from low import leak`: the checker converts the MODULE path
    # to a glob target, so a bare `low` never matches a `low/*` pattern.
    (root / "high" / "uses_low.py").write_text("from low.leak import thing\n", encoding="utf-8")
    return root


@needs_tach
def test_the_real_linter_is_actually_invoked(tmp_path: Path) -> None:
    """Nothing is patched: if tach were absent the runner reports that, and this would say so."""
    root = _project(tmp_path)
    runner = PythonQARunner(cwd=root)

    result = runner.run_architecture_check(target="high/uses_low.py")

    messages = " ".join(v.message for v in result.violations)
    assert "not installed" not in messages, messages


@needs_tach
def test_a_forbids_violation_is_reported(tmp_path: Path) -> None:
    """The half that needs no external tool, asserted separately so a failure says which broke."""
    root = _project(tmp_path)
    runner = PythonQARunner(cwd=root)

    result = runner.run_architecture_check(target="high/uses_low.py")

    assert "ForbiddenImport" in [v.code for v in result.violations], result.violations


@needs_tach
def test_both_sources_arrive_from_one_call(tmp_path: Path) -> None:
    """FR-5's actual claim: the linter's findings and the per-file ones are merged, not chosen."""
    root = _project(tmp_path)
    runner = PythonQARunner(cwd=root)

    result = runner.run_architecture_check(target="high/uses_low.py")

    codes = [v.code for v in result.violations]
    assert "ForbiddenImport" in codes, codes
    assert any(code != "ForbiddenImport" for code in codes), (
        f"only forbids findings came back, so the linter contributed nothing: {result.violations}"
    )
    assert result.violation_count == len(result.violations)
