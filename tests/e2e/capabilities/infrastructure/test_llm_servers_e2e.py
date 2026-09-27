# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real command follows the settings file: to the GB10, or not at all (US-16 P2, P3).

Proves: C-FLOW-13 FR-7, FR-9

Both are red until `sw draft` takes its model from the settings file (C-FLOW-13 SF-03).

| Bucket | Case |
|---|---|
| Happy | `sw draft` with its role on the GB10 → the request goes to the GB10 |
| Boundary | not applicable — one server, one role |
| Degradation | not applicable — a broken file is proven by `sw config show` |
| Hostile | a private-only project with a role on a hosted server → refused before any request |
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
private = false
max_parallel = 3

[roles]
draft = "qwen3-coder-next@gb10"
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


@pytest.mark.xfail(
    strict=True, reason="blocked on C-FLOW-13 SF-03: sw draft does not read the settings file yet"
)
def test_a_draft_on_the_gb10_is_sent_to_the_gb10(
    tmp_path: Path, _mock_db, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = _project(tmp_path)

    with fake_httpx2(lambda request: httpx2.Response(200, json=_REPLY)) as seen:
        _draft(project)

    assert [str(request.url) for request in seen] == ["http://gb10:8000/v1/chat/completions"]


@pytest.mark.xfail(
    strict=True, reason="blocked on C-FLOW-13 SF-03: sw draft does not read the settings file yet"
)
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
