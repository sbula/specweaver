# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A command whose cost ledger refuses writes still finishes, and ends saying what is missing.

Proves: C-FLOW-01 FR-5

US-16 path P5. `sw implement` on a GB10 model, only HTTP faked; the ledger refuses to open rows.

| Bucket | Case |
|---|---|
| Happy | a ledger that writes: the run ends without the line |
| Boundary | not applicable — the singular and the count of 0 are proven by the integration test |
| Degradation | a ledger that refuses every row: the run passes, and ends naming its 2 missing calls |
| Hostile | not applicable — the line never reaches stdout, proven by the integration test |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 1000 }

[brake]
hosted_spend_per_run = 100
tokens_per_run = 100000000
agent_turns = 10
"""

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

_LINE = "calls of this command are missing from the cost ledger"


def _implement(tmp_path: Path, home: Path) -> Any:
    (home / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "missing-demo", "--path", str(project)]).exit_code == 0
    spec = project / "specs" / "greeter_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)):
        return runner.invoke(app, ["implement", str(spec), "--project", str(project)])


@pytest.mark.usefixtures("_mock_db", "stub_implement_qa")
def test_a_ledger_that_writes_leaves_no_line(tmp_path: Path, _isolate_env: Path) -> None:
    done = _implement(tmp_path, _isolate_env)

    assert done.exit_code == 0, done.output
    assert "cost ledger" not in done.output


@pytest.mark.usefixtures("_mock_db", "stub_implement_qa")
def test_a_ledger_that_refuses_rows_is_named_at_the_end(
    tmp_path: Path, _isolate_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _refused(*_args: Any) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(LlmRepository, "open_call", _refused)

    done = _implement(tmp_path, _isolate_env)

    assert done.exit_code == 0, done.output
    assert shows(done.stderr, f"2 {_LINE}")
