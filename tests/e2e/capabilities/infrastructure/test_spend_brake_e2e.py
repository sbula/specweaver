# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real command never sends a call its limits cannot bound (US-04 S3, S4).

Proves: B-FLOW-05 FR-2, B-FLOW-05 FR-5, B-FLOW-05 FR-9

| Bucket | Case |
|---|---|
| Happy | a GB10 run within its token limits sends its requests |
| Boundary | a GB10 model whose own `tokens_per_run` is below one call's worst case sends nothing |
| Degradation | not applicable — a pause instead of the stop is SF-02 |
| Hostile | a hosted model with no price is refused before any request, naming the key |
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

_BRAKE = """
[brake]
hosted_spend_per_run = 100
tokens_per_run = 100000000
agent_turns = 10
"""

_GB10 = (
    """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 1000 }
"""
    + _BRAKE
)

_HOSTED = (
    """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[roles]
default = { model = "mystery-model@hosted", max_output_tokens = 1000 }
"""
    + _BRAKE
)

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "def greet():\n    pass\n"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
}


def _implement(tmp_path: Path, isolate_env: Path, machine: str):
    (isolate_env / "settings.toml").write_text(machine, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "brake-demo", "--path", str(project)]).exit_code == 0
    spec = project / "specs" / "greeter_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        result = runner.invoke(app, ["implement", str(spec), "--project", str(project)])
    return result, seen


@pytest.mark.usefixtures("_mock_db", "stub_implement_qa")
class TestSpendBrakeOnARealCommand:
    def test_a_gb10_run_within_its_limits_sends_its_requests(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        _result, seen = _implement(tmp_path, _isolate_env, _GB10)

        assert seen

    def test_a_model_limit_below_one_calls_worst_case_sends_nothing(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        machine = _GB10 + '\n[models."qwen3-coder-next"]\ntokens_per_run = 500\n'

        result, seen = _implement(tmp_path, _isolate_env, machine)

        assert seen == []
        assert result.exit_code != 0
        assert shows(result.output, 'models."qwen3-coder-next".tokens_per_run')

    def test_a_hosted_model_with_no_price_is_refused_before_any_request(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        result, seen = _implement(tmp_path, _isolate_env, _HOSTED)

        assert seen == []
        assert result.exit_code == 1
        assert shows(result.output, 'models."mystery-model".usd_per_million_input')
