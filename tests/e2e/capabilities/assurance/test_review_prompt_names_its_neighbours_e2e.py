# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw review` tells the model which modules the spec's module works with.

Proves: TECH-088 FR-2

The run setup stores the related modules as a list; the review handler wrapped that list in a second
list, and the prompt builder raised `AttributeError` on it. `sw review` failed on every project whose
`context.yaml` gave the spec's module a neighbour. The test it replaces asserted
`exit_code in (0, 1)`, which accepted that failure.

Everything is real except the model: `sw init`, hand-written `context.yaml` files, the CLI, the run
setup, the handler and the prompt builder. The model double records what it was sent.

| Bucket | Case |
|---|---|
| Happy | `billing` consumes `payments`: the review exits 0 and the prompt names `payments` as a direct dependency |
| Boundary | the reverse: reviewing `payments` names `billing` as a direct consumer |
| Degradation | a project with no `context.yaml` still reviews, with no topology block |
| Hostile | — the neighbours come from files on disk; a broken `context.yaml` is the loader's own test |
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

_SPEC = (
    "# {name}\n\n## 1. Purpose\n\nMoves invoices.\n\n"
    "## 2. Contract\n\n```python\ndef run() -> None: ...\n```\n\n"
    "## 3. Protocol\n\n1. Run.\n\n## 4. Policy\n\n| Error | Behavior |\n|:---|:---|\n"
    "| Any | Raise |\n\n## 5. Boundaries\n\n| Concern | Owned By |\n|:---|:---|\n| I/O | Infra |\n"
)


class _RecordingLLM:
    """Records every prompt and accepts the spec."""

    provider_name = "mock"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, *_args: Any, **_kw: Any) -> LLMResponse:
        self.prompts.append("\n".join(str(getattr(m, "content", m)) for m in messages))
        return LLMResponse(text="VERDICT: ACCEPTED\nGood spec.", model="mock")

    generate_with_tools = generate


def _project(tmp_path: Path, *, manifests: bool = True) -> Path:
    root = tmp_path / "shop"
    (root / "specs").mkdir(parents=True)
    for name in ("billing", "payments"):
        (root / "specs" / f"{name}_spec.md").write_text(_SPEC.format(name=name), encoding="utf-8")
    if manifests:
        (root / "billing").mkdir()
        (root / "billing" / "context.yaml").write_text(
            "name: billing\npurpose: Bills customers.\narchetype: pure-logic\n"
            "consumes:\n  - payments\n",
            encoding="utf-8",
        )
        (root / "payments").mkdir()
        (root / "payments" / "context.yaml").write_text(
            "name: payments\npurpose: Moves money.\narchetype: adapter\n", encoding="utf-8"
        )
    result = runner.invoke(app, ["init", "shop", "--path", str(root)])
    assert result.exit_code == 0, result.output
    return root


def _review(root: Path, module: str) -> tuple[Any, list[str]]:
    llm = _RecordingLLM()
    with doubled_llm(llm, model="mock"):
        result = runner.invoke(
            app, ["review", str(root / "specs" / f"{module}_spec.md"), "--project", str(root)]
        )
    return result, llm.prompts


def test_the_prompt_names_the_module_it_consumes(tmp_path: Path) -> None:
    result, prompts = _review(_project(tmp_path), "billing")

    assert result.exit_code == 0, result.output
    assert any("payments (direct dependency): Moves money." in p for p in prompts), prompts


def test_the_prompt_names_the_module_that_consumes_it(tmp_path: Path) -> None:
    result, prompts = _review(_project(tmp_path), "payments")

    assert result.exit_code == 0, result.output
    assert any("billing (direct consumer): Bills customers." in p for p in prompts), prompts


def test_a_project_without_manifests_still_reviews(tmp_path: Path) -> None:
    result, prompts = _review(_project(tmp_path, manifests=False), "billing")

    assert result.exit_code == 0, result.output
    assert prompts, "the model was never asked"
    assert not any("(direct dependency)" in p for p in prompts)
