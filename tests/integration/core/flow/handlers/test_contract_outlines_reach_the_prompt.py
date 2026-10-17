# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The API contracts a run wrote reach the code-writing and review prompts as outlines.

Proves: C-FLOW-06 FR-1

The seam: the contract paths a contract step records, the code-structure atom that outlines them,
and the prompt the next step sends.

| Bucket | Case |
|---|---|
| Happy | code generation and code review prompts hold the contract's signatures, not its bodies |
| Boundary | no contract paths: no contract block |
| Degradation | a contract file that is gone is left out; the prompt still builds |
| Hostile | the code under review is shown in full once, not again as an outline |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.flow.engine.models import PipelineStep
from specweaver.core.flow.handlers.generation import _generation_prompt
from specweaver.core.flow.handlers.review import _build_review_prompt
from specweaver.core.flow.handlers.run_context import GraphContext, RunContext

if TYPE_CHECKING:
    from pathlib import Path

_CONTRACT = """def fetch_user(user_id: int) -> dict:
    SECRET_BODY = "the body stays out of the prompt"
    return {"id": user_id}
"""


def _context(tmp_path: Path, *paths: str) -> RunContext:
    (tmp_path / "api").mkdir(exist_ok=True)
    (tmp_path / "api" / "users.py").write_text(_CONTRACT, encoding="utf-8")
    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "users_spec.md",
        graph=GraphContext(api_contract_paths=list(paths) or None),
    )


_STEP = PipelineStep(name="generate", action="generate", target="code")


async def test_code_generation_sees_the_contract_outline(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-1
    context = _context(tmp_path, "api/users.py")
    prompt = (await _generation_prompt(context, _STEP, instructions="write it")).build()

    assert "def fetch_user(user_id: int) -> dict" in prompt
    assert "SECRET_BODY" not in prompt


async def test_code_review_sees_the_contract_outline(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-1
    context = _context(tmp_path, "api/users.py")
    prompt = (await _build_review_prompt(context, _STEP, "code_review"))[0].build()

    assert "def fetch_user(user_id: int) -> dict" in prompt
    assert "SECRET_BODY" not in prompt


async def test_the_code_under_review_is_not_added_as_an_outline(tmp_path: Path) -> None:
    context = _context(tmp_path)
    (tmp_path / "users.py").write_text("def handler_under_review() -> None:\n    pass\n")
    base, _ = await _build_review_prompt(context, _STEP, "code_review", extra_targets=["users.py"])

    assert "users.py" in base._skeleton_files  # its outline exists, for the files it mentions
    assert "handler_under_review" not in base.build()


async def test_no_contract_paths_no_contract_block(tmp_path: Path) -> None:
    prompt = (await _generation_prompt(_context(tmp_path), _STEP, instructions="x")).build()
    assert "fetch_user" not in prompt


async def test_a_contract_that_is_gone_is_left_out(tmp_path: Path) -> None:
    context = _context(tmp_path, "api/users.py", "api/gone.py")
    prompt = (await _generation_prompt(context, _STEP, instructions="x")).build()

    assert "def fetch_user" in prompt
    assert "gone.py" not in prompt
