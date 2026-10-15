# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw review` denies a spec that contradicts another spec of the project, and shows both quotes.

Proves: B-FLOW-01 FR-20

The model is doubled at the resolver; it reads the other spec with its real file tool.

| Bucket | Case |
|---|---|
| Happy | a behaviour conflict: DENIED, exit 1, the conflict with both quotes on screen |
| Boundary | the same spec with the other spec agreeing: ACCEPTED, exit 0 |
| Degradation | not applicable here: an unproven conflict is covered at the integration tier |
| Hostile | the model says ACCEPTED while naming the conflict: still DENIED |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e
runner = CliRunner()

_GREET = "# Greet\n\n## 1. Purpose\n\nGreets a person.\n\n| FR-91 | Empty name | an empty name raises ValueError |\n"
_WELCOME = "# Welcome\n\n## 1. Purpose\n\nThe banner.\n\n| FR-91 | Empty name | an empty name returns an empty string |\n"


class _Reviewer:
    def __init__(self) -> None:
        self.read = ""

    async def generate(self, messages: Any, _config: Any) -> LLMResponse:
        if "an empty name returns an empty string" in self.read:
            text = (
                'VERDICT: ACCEPTED\n- CONFLICT: specs/welcome_spec.md says "an empty name returns '
                'an empty string", this spec says "an empty name raises ValueError"\nFine otherwise.'
            )
        else:
            text = "VERDICT: ACCEPTED\nFine."
        return LLMResponse(text=text, model="test-model")

    async def generate_with_tools(
        self, messages: Any, config: Any, dispatcher: Any, **_: Any
    ) -> LLMResponse:
        self.read = str(await dispatcher.execute("read_file", {"path": "specs/welcome_spec.md"}))
        return await self.generate(messages, config)


def _project(tmp_path: Path, welcome: str) -> Path:
    assert runner.invoke(app, ["init", "conflicts", "--path", str(tmp_path)]).exit_code == 0
    (tmp_path / "specs" / "greet_spec.md").write_text(_GREET, encoding="utf-8")
    (tmp_path / "specs" / "welcome_spec.md").write_text(welcome, encoding="utf-8")
    return tmp_path


def _review(project: Path) -> Any:
    with doubled_llm(_Reviewer()):
        return runner.invoke(
            app, ["review", str(project / "specs" / "greet_spec.md"), "--project", str(project)]
        )


def test_a_contradicting_spec_is_denied_with_both_quotes(tmp_path: Path) -> None:
    result = _review(_project(tmp_path, _WELCOME))

    assert result.exit_code == 1, result.output
    assert shows(result.output, "VERDICT: DENIED")
    assert shows(result.output, "an empty name returns an empty string")
    assert shows(result.output, "an empty name raises ValueError")


def test_an_agreeing_spec_is_accepted(tmp_path: Path) -> None:
    agreeing = _WELCOME.replace("returns an empty string", "raises ValueError")

    result = _review(_project(tmp_path, agreeing))

    assert result.exit_code == 0, result.output
    assert shows(result.output, "VERDICT: ACCEPTED")
