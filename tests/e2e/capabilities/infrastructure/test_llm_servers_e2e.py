# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real command follows the settings file: to the GB10, or not at all (US-16 P2, P3).

Proves: C-FLOW-13 FR-7, FR-9

| Bucket | Case |
|---|---|
| Happy | `sw draft` with its role on the GB10 → the request goes to the GB10 |
| Boundary | not applicable — one server, one role |
| Degradation | not applicable — a broken file is proven by `sw config show` |
| Hostile | a private-only project with a role on a hosted server → refused before any request, also when it is named with `--project` while another project is active |
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

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[servers.anthropic]
kind = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"
private = false
max_parallel = 3

[roles]
draft = "qwen3-coder-next@gb10"
default = "qwen3-coder-next@gb10"   # sw draft also reviews what it drafted

[brake]
hosted_spend_per_run = 1000
tokens_per_run = 100000000
agent_turns = 10
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "qwen3-coder-next",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "# Spec"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


def _project(tmp_path: Path, llm_section: str = "") -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    if llm_section:
        (project / "specweaver.toml").write_text(llm_section, encoding="utf-8")
    result = runner.invoke(app, ["init", "servers-demo", "--path", str(project)])
    assert result.exit_code == 0, result.output
    return project


def _draft(project: Path):
    with (
        patch("rich.prompt.Confirm.ask", return_value=True),
        patch("rich.prompt.Prompt.ask", return_value="looks good"),
    ):
        return runner.invoke(app, ["draft", "Greeter", "--project", str(project)])


def test_a_draft_on_the_gb10_is_sent_to_the_gb10(
    tmp_path: Path, _mock_db, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = _project(tmp_path)

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        _draft(project)

    urls = {str(request.url) for request in seen}
    assert seen, "sw draft sent no request at all"
    assert urls == {"http://gb10:8000/v1/chat/completions"}  # every request, none elsewhere


def test_a_private_project_refuses_a_hosted_role_before_any_request(
    tmp_path: Path, _mock_db, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = _project(
        tmp_path, '[llm]\nprivate_only = true\n\n[llm.roles]\ndraft = "claude-opus@anthropic"\n'
    )

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        result = _draft(project)

    assert seen == []
    assert result.exit_code != 0
    assert shows(result.output, "private servers only")


_ONE_REVIEW = (
    'name: one_review\nversion: "1.0"\nsteps:\n  - name: r\n    action: review\n    target: spec\n'
)

_HOSTED_DEFAULT = (
    _MACHINE.replace('default = "qwen3-coder-next@gb10"', 'default = "qwen3-coder-next@hosted"')
    .replace('draft = "qwen3-coder-next@gb10"\n', "")
    .replace(
        "[servers.anthropic]",
        '[servers.hosted]\nkind = "openai-compatible"\nbase_url = "http://hosted.example/v1"\n'
        'private = false\nmax_parallel = 2\n\n[models."qwen3-coder-next"]\n'
        "usd_per_million_input = 1\nusd_per_million_output = 1\nthinking_in_output_cap = true\n\n"
        "[servers.anthropic]",
    )
)


@pytest.mark.parametrize("command", ["review", "run", "implement"])
def test_the_target_projects_private_rule_holds_while_another_project_is_active(
    tmp_path: Path, _mock_db, _isolate_env: Path, command: str
) -> None:
    (_isolate_env / "settings.toml").write_text(_HOSTED_DEFAULT, encoding="utf-8")
    private = tmp_path / "priv"
    private.mkdir()
    (private / "specweaver.toml").write_text("[llm]\nprivate_only = true\n", encoding="utf-8")
    assert runner.invoke(app, ["init", "priv", "--path", str(private)]).exit_code == 0
    other = tmp_path / "other"
    other.mkdir()
    assert runner.invoke(app, ["init", "other", "--path", str(other)]).exit_code == 0
    assert runner.invoke(app, ["use", "other"]).exit_code == 0
    spec = private / "specs" / "g_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# G\n## 1. Purpose\nGreets.\n", encoding="utf-8")
    pipeline = tmp_path / "one.yaml"
    pipeline.write_text(_ONE_REVIEW, encoding="utf-8")
    args = {
        "review": ["review", str(spec), "--project", str(private)],
        "run": ["run", str(pipeline), str(spec), "--project", str(private)],
        "implement": ["implement", str(spec), "--project", str(private)],
    }[command]

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        result = runner.invoke(app, args)

    assert seen == [], [str(request.url) for request in seen]
    assert result.exit_code != 0
    assert shows(result.output, "private servers only")
    assert "Sending to LLM" not in result.output  # nothing is sent, so nothing says so
