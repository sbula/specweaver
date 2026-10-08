# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw usage` still reports past spend when the settings file is broken, in USD, saying why.

Proves: C-FLOW-13 FR-13

| Bucket | Case |
|---|---|
| Happy | not applicable — usage with a good file is proven by the usage command tests |
| Boundary | not applicable — the currency is the only setting `sw usage` reads |
| Degradation | a broken settings file: the report runs, in USD, and names the broken line |
| Hostile | not applicable — the file is the user's own |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration


def test_usage_with_a_broken_settings_file_reports_in_usd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    (data_dir / "settings.toml").write_text("[currency\n", encoding="utf-8")
    bootstrap_database(str(data_dir / "specweaver.db"))
    instance = Database(data_dir / "specweaver.db")
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: instance)

    result = runner.invoke(app, ["usage", "--all"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "not valid TOML")
    assert shows(result.output, "USD")
