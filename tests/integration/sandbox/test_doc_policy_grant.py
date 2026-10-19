# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The coder's write grant follows the project's doc policy, for the step it runs in.

Proves: C-EXEC-08 FR-8
Proves: C-EXEC-08 NFR-3

Driven through `ToolDispatcher`, the path a model's tool call takes; the code-structure tool, the
executor, the grant and the policy are real.

| Bucket | Case |
|---|---|
| Happy | an `open` rule lets the coder write a user guide; a `step` rule lets the named step write |
| Boundary | a `step` rule refuses every other step, and a dispatcher built with no step |
| Degradation | no policy given: `README.md` and `docs/` are refused, as before |
| Hostile | a rule opening `**` does not make `context.yaml` writable |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.config.doc_policy import DocPolicy, DocRule
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_POLICY = DocPolicy(
    rule=[
        DocRule(paths=["docs/user_guides/**"], access="open"),
        DocRule(paths=["docs/api/**"], access="step", steps=["update_api_docs"]),
    ]
)
_CODE = "def greet() -> str:\n    return 'hi'\n"


def _dispatcher(root: Path, **kwargs: Any) -> ToolDispatcher:
    return ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[root]),
        role="implementer",
        allowed_tools=["ast"],
        task_files=["src/greeter.py"],
        **kwargs,
    )


async def _create(dispatcher: ToolDispatcher, path: str) -> dict[str, Any]:
    return await dispatcher.execute("create_module", {"path": path, "code": _CODE})


async def test_an_open_rule_lets_the_coder_write_there(tmp_path: Path) -> None:
    result = await _create(
        _dispatcher(tmp_path, doc_policy=_POLICY, step="implement"), "docs/user_guides/greet.py"
    )

    assert "error" not in result, result
    assert (tmp_path / "docs" / "user_guides" / "greet.py").exists()


async def test_a_step_rule_lets_the_named_step_write(tmp_path: Path) -> None:
    result = await _create(
        _dispatcher(tmp_path, doc_policy=_POLICY, step="update_api_docs"), "docs/api/greet.py"
    )

    assert "error" not in result, result


@pytest.mark.parametrize("step", ["implement", None])
async def test_a_step_rule_refuses_any_other_step(tmp_path: Path, step: str | None) -> None:
    result = await _create(
        _dispatcher(tmp_path, doc_policy=_POLICY, step=step), "docs/api/greet.py"
    )

    assert "docs/api/greet.py" in result["error"]
    assert not (tmp_path / "docs" / "api" / "greet.py").exists()


@pytest.mark.parametrize("path", ["README.md", "docs/user_guides/greet.py"])
async def test_without_a_policy_the_docs_stay_closed(tmp_path: Path, path: str) -> None:
    result = await _create(_dispatcher(tmp_path), path)

    assert path in result["error"]


async def test_a_rule_opening_everything_leaves_a_protected_file_closed(tmp_path: Path) -> None:
    everything = DocPolicy(rule=[DocRule(paths=["**"], access="open")])

    result = await _create(_dispatcher(tmp_path, doc_policy=everything), "src/context.yaml")

    assert "error" in result
    assert not (tmp_path / "src" / "context.yaml").exists()
