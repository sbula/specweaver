# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check --level code` reads a Python file saved with a byte order mark (BOM), as Python does.

Proves: TECH-079 FR-18

The CLI, the hydrator, the executor and the rules are all real; only the database is a temporary
one. Before, C01 failed such a file with "invalid non-printable character U+FEFF", and C06 and C08
skipped it.

| Bucket | Case |
|---|---|
| Happy | a typed, clean file with a BOM passes C01, C06 and C08 |
| Boundary | a BOM that is not the first character is still a syntax error, on its line |
| Degradation | a file with a BOM and a real syntax error fails C01 on that error |
| Hostile | a file with a BOM and a bare `except` gets C06's warning: the rule judged it, never skipped it |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_BOM = b"\xef\xbb\xbf"


@pytest.fixture(autouse=True)
def _db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))


def _check(tmp_path: Path, content: bytes) -> str:
    code = tmp_path / "shop.py"
    code.write_bytes(content)
    return CliRunner().invoke(app, ["check", "--level", "code", str(code)]).output


def _row(output: str, rule_id: str) -> str:
    return next(line for line in output.splitlines() if f" {rule_id} " in line)


def test_a_clean_file_with_a_bom_passes(tmp_path: Path) -> None:
    output = _check(tmp_path, _BOM + b"def total(n: int) -> int:\n    return n\n")

    for rule_id in ("C01", "C06", "C08"):
        assert "PASS" in _row(output, rule_id), _row(output, rule_id)
    assert not shows(output, "U+FEFF")


def test_a_bom_inside_the_file_is_a_syntax_error(tmp_path: Path) -> None:
    output = _check(tmp_path, b"x = 1\n" + _BOM + b"y = 2\n")

    row = _row(output, "C01")
    assert "FAIL" in row, row
    assert shows(output, "line 2")


def test_a_real_syntax_error_after_a_bom_still_fails(tmp_path: Path) -> None:
    output = _check(tmp_path, _BOM + b"def total(:\n    pass\n")

    row = _row(output, "C01")
    assert "FAIL" in row, row
    assert not shows(output, "U+FEFF")


def test_a_bare_except_after_a_bom_is_judged(tmp_path: Path) -> None:
    output = _check(
        tmp_path, _BOM + b"def run() -> None:\n    try:\n        pass\n    except:\n        pass\n"
    )

    row = _row(output, "C06")
    assert "WARN" in row, row
    assert shows(row, "bare except"), row
