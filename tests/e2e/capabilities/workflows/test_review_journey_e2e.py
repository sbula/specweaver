# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw review` sends what it reviews and reports the verdict it got back.

Proves: E-INTL-03 FR-1
Proves: E-INTL-03 FR-2
Proves: E-INTL-03 FR-3

The model is doubled at the resolver (`doubled_llm`); everything from the CLI to the reviewer
runs. The double records the messages it was sent.

| Bucket | Case |
|---|---|
| Happy | a spec review sends the spec; a code review sends the spec and the code |
| Boundary | ACCEPTED exits 0 and DENIED exits 1, both with their findings |
| Degradation | a failed model call is VERDICT: ERROR and exits 1 |
| Hostile | prose that only mentions "VERDICT: ACCEPTED" is DENIED |
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

pytestmark = pytest.mark.e2e
runner = CliRunner()

_SPEC_TEXT = "Greets users by name, case kept."
_CODE_TEXT = "def greet(name):\n    return 'hello ' + name\n"


class _Model:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.sent = ""

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, _config: Any) -> LLMResponse:
        self.sent += "\n".join(m.content for m in messages)
        if isinstance(self.reply, Exception):
            raise self.reply
        return LLMResponse(text=self.reply, model="test-model")

    async def generate_with_tools(self, messages: Any, config: Any, *_a: Any, **_k: Any):
        return await self.generate(messages, config)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    assert runner.invoke(app, ["init", "review-journey", "--path", str(tmp_path)]).exit_code == 0
    spec = tmp_path / "specs" / "greeter_spec.md"
    spec.write_text(f"# Greeter\n\n## 1. Purpose\n\n{_SPEC_TEXT}\n", encoding="utf-8")
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "greeter.py").write_text(_CODE_TEXT, encoding="utf-8")
    return tmp_path


def _review(project: Path, model: _Model, *, code: bool = False):
    spec = str(project / "specs" / "greeter_spec.md")
    args = ["review", spec]
    if code:
        args = ["review", str(project / "src" / "greeter.py"), "--spec", spec]
    with doubled_llm(model):
        return runner.invoke(app, [*args, "--project", str(project)])


def test_a_spec_review_sends_the_spec_and_reports_acceptance(project: Path) -> None:
    model = _Model("VERDICT: ACCEPTED\n- add an example\nGood spec.")

    result = _review(project, model)

    assert result.exit_code == 0, result.output
    assert _SPEC_TEXT in model.sent
    assert 'Start your response with either "VERDICT: ACCEPTED"' in model.sent
    assert "VERDICT: ACCEPTED" in result.output
    assert "add an example" in result.output


def test_a_code_review_sends_the_spec_and_the_code(project: Path) -> None:
    model = _Model("VERDICT: DENIED\n- name may be None\nNeeds a guard.")

    result = _review(project, model, code=True)

    assert result.exit_code == 1, result.output
    assert _SPEC_TEXT in model.sent
    assert "return 'hello ' + name" in model.sent
    assert "VERDICT: DENIED" in result.output
    assert "name may be None" in result.output


def test_prose_that_mentions_acceptance_is_denied(project: Path) -> None:
    model = _Model('I would not say "VERDICT: ACCEPTED" here.\n- the contract is missing')

    result = _review(project, model)

    assert result.exit_code == 1, result.output
    assert "VERDICT: DENIED" in result.output


def test_a_failed_model_call_is_an_error(project: Path) -> None:
    result = _review(project, _Model(RuntimeError("provider down")))

    assert result.exit_code == 1, result.output
    assert "VERDICT: ERROR" in result.output
