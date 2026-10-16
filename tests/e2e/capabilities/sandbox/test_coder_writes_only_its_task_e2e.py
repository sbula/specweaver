# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An agentic coder writes its task's file, and its write to `README.md` is refused.

Proves: E-SENS-03 FR-1
Proves: E-SENS-03 FR-3

US-5 paths P1 and P2: `sw run` with an `agentic` generate step; only the model is doubled, and it
asks for two writes through its tools. No production path gives the coder tools yet — `C-FLOW-11`
wires them — so this journey is expected to fail until it does.

| Bucket | Case |
|---|---|
| Happy | the coder's `src/greeter.py` lands |
| Boundary | not applicable — the task list's shapes are proven by the integration tests |
| Degradation | not applicable — a grant that cannot be built is proven by the integration tests |
| Hostile | the coder's write to `README.md` is refused, named, and the file is unchanged |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_PIPELINE = """\
name: agentic_generate
steps:
  - name: generate_code
    action: generate
    target: code
    mode: agentic
"""
_CODE = "def greet() -> str:\n    return 'hi'\n"


class _Coder:
    """A model that writes through its tools and keeps what each write answered."""

    provider_name = "scripted"

    def __init__(self) -> None:
        self.answers: dict[str, Any] = {}

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        return LLMResponse(text=_CODE, model="test-model")

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any, **_k: Any
    ) -> LLMResponse:
        for path in ("README.md", "src/greeter.py"):
            self.answers[path] = await tool_executor.execute(
                "create_module", {"path": path, "code": _CODE}
            )
        return LLMResponse(text=_CODE, model="test-model")


@pytest.mark.xfail(strict=True, reason="blocked on C-FLOW-11: no step gives the coder its tools")
@pytest.mark.usefixtures("_mock_db")
def test_an_agentic_coder_writes_its_task_and_not_the_readme(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "task-grant", "--path", str(project)]).exit_code == 0
    (project / "specs").mkdir(exist_ok=True)
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    (project / "agentic.yaml").write_text(_PIPELINE, encoding="utf-8")
    readme = "Greeter.\n"
    (project / "README.md").write_text(readme, encoding="utf-8")
    coder = _Coder()

    with doubled_llm(coder):
        runner.invoke(
            app, ["run", str(project / "agentic.yaml"), "greeter", "--project", str(project)]
        )

    assert "README.md" in coder.answers["README.md"]["error"]
    assert "error" not in coder.answers["src/greeter.py"]
    assert (project / "README.md").read_text(encoding="utf-8") == readme
