# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw standards scan` still scans when no `[brake]` is set, and says why no model was used.

Proves: C-FLOW-13 FR-17

Model enrichment is optional for a scan. A missing limit must not stop the scan, and it must not be
silent either: the user learns which key would turn enrichment on.

| Bucket | Case |
|---|---|
| Happy | not applicable — enrichment with a model is proven by the standards handler tests |
| Boundary | a role is set, the `[brake]` section is missing |
| Degradation | the scan finishes, exit 0, and names `brake.hosted_spend_per_run` |
| Hostile | not applicable — no input crosses a trust boundary here |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_NO_BRAKE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = "qwen3-coder-next@gb10"
"""


@pytest.mark.usefixtures("_mock_db")
def test_a_scan_without_brake_values_scans_and_says_why_no_model_was_used(
    tmp_path: Path, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_NO_BRAKE, encoding="utf-8")
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "src" / "greet.py").write_text(
        'def greet_user(name: str) -> str:\n    """Greet."""\n    return name\n',
        encoding="utf-8",
    )
    assert runner.invoke(app, ["init", "scan-demo", "--path", str(project)]).exit_code == 0
    assert runner.invoke(app, ["use", "scan-demo"]).exit_code == 0

    with fake_httpx2(lambda _request: None) as seen:
        result = runner.invoke(app, ["standards", "scan", "--no-review"])

    assert result.exit_code == 0, result.output
    assert seen == []
    assert shows(result.output, "No model used")
    assert shows(result.output, "brake.hosted_spend_per_run")
