# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project chooses what reaches the console: `sw config set-log-level --console`.

Proves: D-FLOW-04 FR-7
Proves: D-FLOW-04 NFR-2

Every command runs through the CLI's own start-up, which reads the project's levels.

| Bucket | Case |
|---|---|
| Happy | at INFO, a command's INFO line reaches stderr |
| Boundary | at the default WARNING, it does not; `get-log-level` shows both levels |
| Degradation | not applicable — an unreadable level is proven by the integration test |
| Hostile | a level that is not a level is refused, and the console level is unchanged |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from specweaver.telemetry_logger import teardown_logging
from tests.rendering import shows

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_CHANGED = "level changed to DEBUG"


@pytest.fixture
def project(tmp_path: Path, _isolate_env: Path) -> Iterator[None]:
    folder = tmp_path / "proj"
    folder.mkdir()
    assert runner.invoke(app, ["init", "levels", "--path", str(folder)]).exit_code == 0
    yield
    teardown_logging()


@pytest.mark.usefixtures("project")
def test_at_info_a_commands_info_line_reaches_the_console() -> None:
    assert runner.invoke(app, ["config", "set-log-level", "--console", "INFO"]).exit_code == 0

    result = runner.invoke(app, ["config", "set-log-level", "DEBUG"])

    assert result.exit_code == 0
    assert _CHANGED in result.stderr


@pytest.mark.usefixtures("project")
def test_at_the_default_warning_it_does_not() -> None:
    result = runner.invoke(app, ["config", "set-log-level", "DEBUG"])
    shown = runner.invoke(app, ["config", "get-log-level"])

    assert result.exit_code == 0
    assert _CHANGED not in result.stderr
    assert shows(shown.output, "Console level: WARNING")


@pytest.mark.usefixtures("project")
def test_a_level_that_is_not_a_level_is_refused() -> None:
    refused = runner.invoke(app, ["config", "set-log-level", "--console", "LOUD"])
    shown = runner.invoke(app, ["config", "get-log-level"])

    assert refused.exit_code == 1
    assert shows(shown.output, "Console level: WARNING")
