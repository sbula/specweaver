# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check --level code` on a real project: real pytest, real coverage, any path form.

Proves: D-VAL-05 FR-3
Proves: D-VAL-05 FR-4
Proves: D-VAL-05 FR-5

The audit of 2026-10-07 found C04 never reported coverage, a relative path broke C02, C04 and
C05, and C03 and C05 passed when their check never ran. Only the test runner's own subprocess is
real here; nothing is mocked.

| Bucket | Case |
|---|---|
| Happy | an absolute path: C03 passes, C04 reports the file's own coverage |
| Boundary | a relative path gives the same results as an absolute one |
| Degradation | a check whose tool could not run fails, naming why, never passes |
| Hostile | not applicable — the path is the user's own file |
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.assurance.validation.interfaces import cli as check_cli
from specweaver.assurance.validation.models import Status

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("python") is None, reason="python must be on PATH"),
]

_SOURCE = """def add(a, b):
    return a + b


def unused(x):
    if x:
        return 1
    return 2
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "foo.py").write_text(_SOURCE, encoding="utf-8")
    (root / "tests" / "test_foo.py").write_text(
        "from foo import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "foo"\nversion = "0.1"\n\n'
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
        encoding="utf-8",
    )
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(root)
    return root


def _check(target: str, root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    seen: dict[str, object] = {}

    def capture(results, _title):
        seen.update({r.rule_id: r for r in results})

    monkeypatch.setattr(check_cli, "_display_results", capture)
    CliRunner().invoke(
        check_cli.validation_cli, ["check", target, "--level", "code", "--project", str(root)]
    )
    return seen


@pytest.mark.parametrize("form", ["absolute", "relative"])
def test_coverage_and_tests_are_measured_for_either_path_form(
    project: Path, monkeypatch: pytest.MonkeyPatch, form: str
) -> None:
    target = str(project / "src" / "foo.py") if form == "absolute" else "src/foo.py"

    results = _check(target, project, monkeypatch)

    assert results["C02"].status is Status.PASS, results["C02"].message
    assert results["C03"].status is Status.PASS, results["C03"].message
    assert "%" in results["C04"].message, results["C04"].message
    assert "50%" in results["C04"].message, results["C04"].message


def test_a_check_that_could_not_run_does_not_pass(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project / "tests" / "test_foo.py").write_text("import nowhere_to_be_found\n", encoding="utf-8")

    results = _check("src/foo.py", project, monkeypatch)

    assert results["C03"].status is Status.FAIL, results["C03"].message
    assert results["C05"].status is not Status.PASS, results["C05"].message
