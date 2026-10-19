# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""For one policy and one step, what the grant lets the agent write is what the merge keeps.

Proves: C-EXEC-08 FR-8

The seam between `E-SENS-03` (the task grant) and `D-EXEC-02` (the worktree merge). Each side is
real: the dispatcher's tool writes into one project, and `strip_merge` merges a real branch into
another.

| Bucket | Case |
|---|---|
| Happy | a task file and an `open` doc: written, and kept |
| Boundary | the root `doc_updates.md`; `docs/doc_updates.md` |
| Degradation | not applicable — both sides are pure decisions over real files |
| Hostile | `README.md`, a `step` doc for another step, a file outside the task: refused, and not kept |
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.doc_policy import DocPolicy, DocRule
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.git.core.atom import GitAtom
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("git") is None, reason="git required"),
]

_POLICY = DocPolicy(
    rule=[
        DocRule(paths=["docs/user_guides/**"], access="open"),
        DocRule(paths=["docs/api/**"], access="step", steps=["update_api_docs"]),
    ]
)
_TASK = ["src/greeter.py"]
_STEP = "implement"
_PATHS = [
    "src/greeter.py",
    "src/other.py",
    "README.md",
    "docs/user_guides/a.py",
    "docs/api/a.py",
    "doc_updates.md",
    "docs/doc_updates.md",
]
_CODE = "def greet() -> str:\n    return 'hi'\n"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


async def _granted(root: Path, path: str) -> bool:
    root.mkdir()
    dispatcher = ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[root]),
        role="implementer",
        allowed_tools=["ast"],
        task_files=_TASK,
        doc_policy=_POLICY,
        step=_STEP,
    )
    result = await dispatcher.execute("create_module", {"path": path, "code": _CODE})
    return "error" not in result


def _kept(root: Path, path: str) -> bool:
    root.mkdir()
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "switch", "-c", "task")
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(_CODE, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "task")
    _git(root, "switch", "main")
    GitAtom(cwd=root).run(
        {
            "intent": "strip_merge",
            "branch": "task",
            "allowed_paths": _TASK,
            "doc_policy": _POLICY,
            "step": _STEP,
        }
    )
    return (root / path).exists()


@pytest.mark.parametrize("path", _PATHS)
async def test_the_grant_and_the_merge_agree(tmp_path: Path, path: str) -> None:
    granted = await _granted(tmp_path / "agent", path)
    kept = _kept(tmp_path / "merge", path)

    assert granted == kept, f"{path}: grant {granted}, merge {kept}"


def test_the_matrix_holds_both_answers() -> None:
    """Agreement over paths that are all refused, or all kept, would prove nothing."""
    from specweaver.sandbox.security import write_verdict

    verdicts = {write_verdict(_POLICY, path, _STEP, _TASK) for path in _PATHS}

    assert {"keep", "propose", "strip"} <= verdicts
