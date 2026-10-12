# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check --level code` on a project as `sw init` leaves it: each rule catches its mistake.

Proves: D-VAL-05 FR-1
Proves: D-VAL-05 FR-2
Proves: D-VAL-05 FR-3
Proves: D-VAL-05 FR-4
Proves: D-VAL-05 FR-5
Proves: D-VAL-05 FR-6
Proves: D-VAL-05 FR-7
Proves: D-VAL-05 FR-8

No `pyproject.toml`, no `tach.toml` until `sw scan`, tests importing their module by name —
as SpecWeaver writes them. Real pytest, real coverage, real tach.

| Bucket | Case |
|---|---|
| Happy | a correct, fully tested file passes C01 to C08 |
| Boundary | before `sw scan` C05 fails and says to run it |
| Degradation | a test that cannot import its module fails C03, never passes |
| Hostile | one file per mistake: each fails or warns on its own rule |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.assurance.validation.interfaces import cli as check_cli
from specweaver.assurance.validation.models import Status
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e
runner = CliRunner()

_GOOD = "def add(a: int, b: int) -> int:\n    return a + b\n"
_LOWCOV = (
    "def a(x: int) -> int:\n    if x > 0:\n        return 1\n    if x < -5:\n        return 2\n"
    "    if x < -9:\n        return 3\n    return 4\n"
)
_CASES = {
    "syntax": ("def add(a: int -> int:\n    return a\n", "C01", Status.FAIL),
    "failing": ("def add(a: int, b: int) -> int:\n    return a - b\n", "C03", Status.FAIL),
    "lowcov": (_LOWCOV, "C04", Status.FAIL),
    "imports": (
        "import specweaver.sandbox.base\n\n\ndef f() -> int:\n    return 1\n",
        "C05",
        Status.FAIL,
    ),
    "bare": (
        "def f() -> int:\n    try:\n        return 1\n    except:\n        return 2\n",
        "C06",
        Status.WARN,
    ),
    "todo": ("def f() -> int:\n    # TODO fix this\n    return 1\n", "C07", Status.WARN),
    "hints": ("def f(x):\n    return x\n", "C08", Status.FAIL),
}
_TESTS = {
    "good": "from good import add\n\n\ndef test_add() -> None:\n    assert add(1, 2) == 3\n",
    "failing": "from failing import add\n\n\ndef test_add() -> None:\n    assert add(1, 2) == 3\n",
    "lowcov": "from lowcov import a\n\n\ndef test_a() -> None:\n    assert a(1) == 1\n",
}


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    assert runner.invoke(app, ["init", "fresh-code", "--path", str(tmp_path)]).exit_code == 0
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src" / "good.py").write_text(_GOOD, encoding="utf-8")
    for name, (code, _rule, _status) in _CASES.items():
        (tmp_path / "src" / f"{name}.py").write_text(code, encoding="utf-8")
    for name, test in _TESTS.items():
        (tmp_path / "tests" / f"test_{name}.py").write_text(test, encoding="utf-8")
    return tmp_path


def _check(project: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> dict:
    seen: dict = {}
    monkeypatch.setattr(
        check_cli, "_display_results", lambda r, _t: seen.update({x.rule_id: x for x in r})
    )
    runner.invoke(app, ["check", f"src/{name}.py", "--level", "code", "--project", str(project)])
    return seen


def test_before_sw_scan_c05_says_to_run_it(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c05 = _check(project, "good", monkeypatch)["C05"]

    assert c05.status is Status.FAIL
    assert any("sw scan" in f.message for f in c05.findings), [f.message for f in c05.findings]


def test_a_correct_tested_file_passes_every_rule(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert runner.invoke(app, ["scan"]).exit_code == 0

    results = _check(project, "good", monkeypatch)

    for rule in ("C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"):
        assert results[rule].status is Status.PASS, (rule, results[rule].message)
    assert "100%" in results["C04"].message


@pytest.mark.parametrize("name", sorted(_CASES))
def test_each_mistake_is_caught_by_its_rule(
    project: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    assert runner.invoke(app, ["scan"]).exit_code == 0
    _code, rule, status = _CASES[name]

    result = _check(project, name, monkeypatch)[rule]

    assert result.status is status, (rule, result.status, result.message)


def test_a_file_without_a_test_fails_c02(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _check(project, "syntax", monkeypatch)["C02"].status is Status.FAIL
