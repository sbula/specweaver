# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check --level code` on a Kotlin file shows C01, C06 and C08 as skipped, never failed.

Proves: TECH-093 FR-3

The CLI, the hydrator, the executor and the rules are all real; only the database is a temporary
one. Before TECH-093 the same command printed "C01 Syntax Valid FAIL Syntax error at line 1".
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


@pytest.fixture(autouse=True)
def _db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))


def _row(output: str, rule_id: str) -> str:
    return next(line for line in output.splitlines() if f" {rule_id} " in line)


def test_a_kotlin_file_skips_the_python_checks(tmp_path: Path) -> None:
    code = tmp_path / "src" / "main" / "kotlin" / "shop" / "Cart.kt"
    code.parent.mkdir(parents=True)
    code.write_text("package shop\n\nclass Cart { fun total(): Int = 0 }\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["check", "--level", "code", str(code)])

    for rule_id in ("C01", "C06", "C08"):
        row = _row(result.output, rule_id)
        assert "SKIP" in row, row
        assert shows(row, "kotlin"), row
    assert not shows(result.output, "Syntax error")
