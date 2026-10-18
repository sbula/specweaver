# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Two `sw review` runs of one spec send one cache key and the same prompt start: the second can be
read from the provider's cache.

Proves: C-FLOW-14 FR-2, FR-3

The real CLI, the real OpenAI adapter and SDK; only HTTP is faked, and the requests are read back.

| Bucket | Case |
|---|---|
| Happy | both runs send one `prompt_cache_key` and equal text up to the run clock |
| Boundary | the run clock differs between the two runs |
| Degradation | not applicable — covered by the adapter's own tests |
| Hostile | not applicable — the command reads only the spec |
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import httpx2
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()

_MACHINE = """\
[servers.openai]
kind = "openai"
api_key_env = "OPENAI_API_KEY"
private = false
max_parallel = 1

[roles]
default = "gpt-5.6@openai"

[brake]
hosted_spend_per_run = 100
tokens_per_run = 10000000
agent_turns = 5
"""
_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-5.6",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "VERDICT: ACCEPTED\nGood spec."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
}


def _first_request(project: Path, spec: Path) -> dict:
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        result = runner.invoke(app, ["review", str(spec), "--project", str(project)])
    assert result.exit_code == 0, result.output
    return json.loads(seen[0].content)


def _text(body: dict) -> str:
    return "\n".join(m["content"] for m in body["messages"] if isinstance(m.get("content"), str))


def test_two_reviews_send_one_key_and_one_start(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    keys = _isolate_env / "keys.env"
    keys.write_text("OPENAI_API_KEY=test-key-not-real-0123456789\n", encoding="utf-8")
    os.chmod(keys, 0o600)
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "cache-demo", "--path", str(project)]).exit_code == 0
    spec = project / "specs" / "greeter_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text("# Greeter\n\n## 1. Purpose\n\nGreets the user by name.\n", encoding="utf-8")

    first = _first_request(project, spec)
    second = _first_request(project, spec)

    assert first["prompt_cache_key"] == second["prompt_cache_key"]
    assert _text(first).split("<run_clock>")[0] == _text(second).split("<run_clock>")[0]
    assert _text(first) != _text(second)
