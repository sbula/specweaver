# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw draft` at a terminal: each written section is shown, and the person keeps, changes or skips it.

Proves: E-INTL-02 FR-1
Proves: E-INTL-02 FR-2

Only the model's text is scripted; the keystrokes go through the real terminal prompt.

| Bucket | Case |
|---|---|
| Happy | the first section is changed once and kept; the spec holds the rewrite |
| Boundary | `skip` leaves a TODO; Enter keeps a section as written |
| Degradation | not applicable: a terminal is the only provider here |
| Hostile | the rewrite prompt carries the change and the old text, the spec only the new text |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


class _Writer:
    """Writes `v<n>` for every section prompt, recording each prompt."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: list[Any], config: Any) -> LLMResponse:
        self.prompts.append(messages[0].content)
        return LLMResponse(text=f"section text v{len(self.prompts)}", model="m")


def test_a_section_is_shown_changed_and_kept(tmp_path: Path) -> None:
    # Proves: E-INTL-02 FR-2
    assert runner.invoke(app, ["init", "greet", "--path", str(tmp_path)]).exit_code == 0
    writer = _Writer()
    keys = "\n".join(
        [
            "It greets people.",  # Purpose question
            "mention German",  # change the written Purpose
            "",  # keep the rewrite
            "greet(name) -> str",  # Contract question
            "skip",  # skip the written Contract
            "",
            "",
            "",  # Protocol, Policy, Boundaries: no answer
        ]
    )

    with doubled_llm(writer):
        result = runner.invoke(
            app, ["draft", "greeter", "--project", str(tmp_path)], input=keys + "\n"
        )

    # The half-empty spec then fails validation (S06, S07), so `sw draft` exits 1; the draft is saved.
    assert "Spec drafted" in result.output, result.output
    spec = (tmp_path / "specs" / "greeter_spec.md").read_text(encoding="utf-8")
    purpose = spec.split("## 1. Purpose", 1)[1].split("## 2.", 1)[0]
    assert "section text v2" in purpose
    assert "section text v1" not in spec
    assert "TODO: Fill in Contract section." in spec
    assert "section text v1" in result.output  # the person saw the first version
    assert "mention German" in writer.prompts[1]
    assert "section text v1" in writer.prompts[1]
