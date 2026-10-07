# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real command never sends a call its limits cannot bound (US-04 S3, S4).

Proves: B-FLOW-05 FR-2, B-FLOW-05 FR-5, B-FLOW-05 FR-6, B-FLOW-05 FR-9

| Bucket | Case |
|---|---|
| Happy | a GB10 run within its token limits sends its requests |
| Boundary | a GB10 model whose own `tokens_per_run` is below one call's worst case sends nothing |
| Degradation | at a limit with a terminal, the run asks; "yes" sends the call (US-04 S1) |
| Hostile | a hosted model with no price is refused before any request, naming the key |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

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

_TOOL_CALL = {
    "id": "c0",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "t1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path": "specs/big.md"}'},
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
}

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
        assert not shows(result.output, "tests did not pass"), result.output
        assert shows(result.output, "spend brake")

    def test_a_hosted_model_with_no_price_is_refused_before_any_request(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        result, seen = _implement(tmp_path, _isolate_env, _HOSTED)

        assert seen == []
        assert result.exit_code == 1
        assert shows(result.output, 'models."mystery-model".usd_per_million_input')


_ONE_REVIEW = """\
name: one_review
version: "1.0"
steps:
  - name: review_spec
    action: review
    target: spec
"""


@pytest.mark.usefixtures("_mock_db")
class TestThePause:
    def test_at_a_limit_the_run_asks_and_yes_sends_the_call(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        machine = _GB10 + '\n[models."qwen3-coder-next"]\ntokens_per_run = 500\n'
        (_isolate_env / "settings.toml").write_text(machine, encoding="utf-8")
        project = tmp_path / "proj"
        project.mkdir()
        assert runner.invoke(app, ["init", "pause-demo", "--path", str(project)]).exit_code == 0
        assert runner.invoke(app, ["use", "pause-demo"]).exit_code == 0
        spec = project / "specs" / "a_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# A\n## 1. Purpose\nDoes A.\n", encoding="utf-8")
        pipeline = tmp_path / "one_review.yaml"
        pipeline.write_text(_ONE_REVIEW, encoding="utf-8")

        with (
            patch("specweaver.interfaces.cli._core.stdin_is_interactive", return_value=True),
            patch("rich.prompt.Prompt.ask", return_value="y") as asked,
            fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen,
        ):
            runner.invoke(app, ["run", str(pipeline), str(spec), "--project", str(project)])

        questions = [str(call.args[0]) for call in asked.call_args_list]
        assert any("tokens_per_run" in q for q in questions), questions
        assert seen, "the user said yes, but the call was never sent"

    def test_a_tool_round_that_would_cross_asks_before_its_request(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        # Round 0 fits; the file the tool reads makes round 1's prompt cross the model's limit.
        machine = _GB10 + '\n[models."qwen3-coder-next"]\ntokens_per_run = 6000\n'
        (_isolate_env / "settings.toml").write_text(machine, encoding="utf-8")
        project = tmp_path / "proj"
        project.mkdir()
        assert runner.invoke(app, ["init", "round-demo", "--path", str(project)]).exit_code == 0
        assert runner.invoke(app, ["use", "round-demo"]).exit_code == 0
        spec = project / "specs" / "a_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# A\n## 1. Purpose\nDoes A.\n", encoding="utf-8")
        (project / "specs" / "big.md").write_text("x" * 40_000, encoding="utf-8")
        pipeline = tmp_path / "one_review.yaml"
        pipeline.write_text(_ONE_REVIEW, encoding="utf-8")
        replies = iter([_TOOL_CALL, _REPLY])

        with (
            patch("specweaver.interfaces.cli._core.stdin_is_interactive", return_value=True),
            patch("rich.prompt.Prompt.ask", return_value="y") as asked,
            fake_httpx2(lambda _request: httpx2.Response(200, json=next(replies))) as seen,
        ):
            runner.invoke(app, ["run", str(pipeline), str(spec), "--project", str(project)])

        assert len(seen) == 2, "the review did not run its tool round"
        questions = [str(call.args[0]) for call in asked.call_args_list]
        assert len(questions) == 1, questions  # asked once, before round 1, not before round 0

    def test_no_parks_the_run_and_says_how_to_go_on(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        machine = _GB10 + '\n[models."qwen3-coder-next"]\ntokens_per_run = 500\n'
        (_isolate_env / "settings.toml").write_text(machine, encoding="utf-8")
        project = tmp_path / "proj"
        project.mkdir()
        assert runner.invoke(app, ["init", "no-demo", "--path", str(project)]).exit_code == 0
        assert runner.invoke(app, ["use", "no-demo"]).exit_code == 0
        spec = project / "specs" / "a_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# A\n## 1. Purpose\nDoes A.\n", encoding="utf-8")
        pipeline = tmp_path / "one_review.yaml"
        pipeline.write_text(_ONE_REVIEW, encoding="utf-8")

        with (
            patch("specweaver.interfaces.cli._core.stdin_is_interactive", return_value=True),
            patch("rich.prompt.Prompt.ask", return_value=""),  # Enter: no
            fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen,
        ):
            result = runner.invoke(
                app, ["run", str(pipeline), str(spec), "--project", str(project)]
            )

        assert seen == []
        assert result.exit_code == 0, result.output
        assert shows(result.output, 'models."qwen3-coder-next".tokens_per_run')
        assert shows(result.output, "--resume")
