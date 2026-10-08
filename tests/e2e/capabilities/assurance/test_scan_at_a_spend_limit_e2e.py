# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw standards scan` at a spend limit keeps what it found and says why enrichment stopped.

Proves: B-FLOW-05 FR-7

Enrichment is optional for a scan: a brake stop ends the model calls, not the scan.

| Bucket | Case |
|---|---|
| Happy | not applicable — a scan within its limits is proven by the standards tests |
| Boundary | the very first enrichment call would cross the token limit |
| Degradation | every scope's findings are kept, without enrichment, and the stop is named once |
| Hostile | not applicable — no input crosses a trust boundary here |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_TINY_LIMIT = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 100 }

[brake]
hosted_spend_per_run = 10
tokens_per_run = 50
agent_turns = 5
"""

_MODULE = (
    'def get_value_{i}(x: int) -> int:\n    """Doc."""\n    return x\n\n\n'
    'def get_other_{i}(y: int) -> int:\n    """Doc."""\n    return y\n'
)


def _scan(tmp_path: Path, data_dir: Path, folders: tuple[str, ...]):
    (data_dir / "settings.toml").write_text(_TINY_LIMIT, encoding="utf-8")
    project = tmp_path / "proj"
    for folder in folders:
        (project / folder).mkdir(parents=True)
        for i in range(4):
            (project / folder / f"m{i}.py").write_text(_MODULE.format(i=i), encoding="utf-8")
    assert runner.invoke(app, ["init", "brake-scan", "--path", str(project)]).exit_code == 0
    assert runner.invoke(app, ["use", "brake-scan"]).exit_code == 0

    with fake_httpx2(lambda _request: httpx2.Response(500)) as seen:
        result = runner.invoke(app, ["standards", "scan", "--no-review", "--compare"])
    return result, seen


@pytest.mark.usefixtures("_mock_db")
def test_a_scan_at_a_spend_limit_names_the_stop_once(tmp_path: Path, _isolate_env: Path) -> None:
    result, seen = _scan(tmp_path, _isolate_env, ("alpha", "beta"))

    assert result.exit_code == 0, result.output
    assert seen == []
    assert not shows(result.output, "No standards discovered")
    assert shows(result.output, "brake.tokens_per_run")
    assert " ".join(result.output.split()).count("stopped by the spend brake") == 1


@pytest.mark.usefixtures("_mock_db")
def test_the_stopped_scope_keeps_its_findings(tmp_path: Path, _isolate_env: Path) -> None:
    result, _seen = _scan(tmp_path, _isolate_env, (".",))

    assert result.exit_code == 0, result.output
    assert not shows(result.output, "No standards discovered")
