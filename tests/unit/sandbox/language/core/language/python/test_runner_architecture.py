# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Freedom from interference: the boundary rule's findings and the boundary linter's, merged.

Proves: C-VAL-03 FR-5

FR-5 outsources cross-boundary isolation to native linters rather than reimplementing them, merged
with the per-file rule. Since TECH-082 the per-file half is the shared boundary check (every
language, every inherited `forbids`; `test_boundary_check.py`) and tach is a configured extra.
`check_architecture` merges them; a count right about one source and blind to the other reads
exactly like a clean result, so the merge is what this pins. The real-tach version is
`tests/integration/sandbox/language/test_boundary_linter_merge.py`.

| Bucket | Case |
|---|---|
| Happy | a rule violation and a tach violation both arrive, counted once each |
| Boundary | a clean file with tach configured: tach ran, nothing found |
| Degradation | tach configured and missing: the rule's verdict stands, tach is reported not run |
| Hostile | — (the inputs are a fixed project) |
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.language.core import boundary_extras
from specweaver.sandbox.language.core.boundary_check import check_architecture

if TYPE_CHECKING:
    from pathlib import Path

TACH_FINDING = (
    '[{"Located": {"file_path": "low/leak.py", "details": {"Code": {"UndeclaredDependency": '
    '{"dependency": "high.thing", "usage_module": "low", "definition_module": "high"}}}}}]'
)


class _Executor:
    def __init__(self, stdout: str) -> None:
        self._stdout = stdout

    def execute(self, cmd: list[str], *, timeout_seconds: int | None = None) -> SimpleNamespace:
        return SimpleNamespace(exit_code=1, stdout=self._stdout, stderr="", timed_out=False)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    files = {
        "tach.toml": "exact = true\n",
        "high/context.yaml": "name: high\narchetype: pure-logic\nforbids: [low]\n",
        "high/__init__.py": "",
        "low/__init__.py": "",
        "high/uses_low.py": "from low import leak\n",
        "high/clean.py": "import os\n",
    }
    for relative, text in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")
    return tmp_path


def test_both_sources_arrive_from_one_call(project: Path) -> None:
    result = check_architecture(project, "high/uses_low.py", _Executor(TACH_FINDING))

    assert sorted(v.code for v in result.violations) == [
        "BoundaryRule",
        "tach:UndeclaredDependency",
    ]
    assert result.violation_count == 2


def test_a_clean_file_with_tach_configured(project: Path) -> None:
    result = check_architecture(project, "high/clean.py", _Executor("[]"))

    assert result.violation_count == 0
    assert [(e.tool, e.ran) for e in result.extras] == [("tach", True)]


def test_a_missing_tach_leaves_the_rules_verdict_standing(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: None)

    result = check_architecture(project, "high/uses_low.py", _Executor("[]"))

    assert [v.code for v in result.violations] == ["BoundaryRule"]
    assert [(e.tool, e.ran) for e in result.extras] == [("tach", False)]
