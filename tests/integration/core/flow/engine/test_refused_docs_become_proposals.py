# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The worktree merge follows the project's doc policy, and a refused doc change is a proposal.

Proves: C-EXEC-08 FR-7
Proves: C-EXEC-08 FR-8
Proves: C-EXEC-08 NFR-2
Proves: C-FLOW-11 FR-9

Real git, real `bash` steps, the real runner: per-step worktrees (`use_worktree`) and one session
worktree for the whole run.

| Bucket | Case |
|---|---|
| Happy | the named step's doc lands; another step's `README.md` change is restored and its diff is in `doc_updates.md` |
| Boundary | `doc_updates.md` absent before → created; present → kept and appended; a merge whose only change is refused still commits the proposal |
| Degradation | a binary doc is named, not shown; a failed step's leftover is judged as that step's, not the next one's |
| Hostile | a `.env` change is stripped and never copied into `doc_updates.md`; in a session, a doc the named step wrote and another step then changed is proposed |
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.config.doc_policy import DocPolicy, DocRule
from specweaver.core.flow.engine.models import (
    GateDefinition,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(_GIT is None or shutil.which("bash") is None, reason="git and bash"),
]

_POLICY = DocPolicy(rule=[DocRule(paths=["docs/api/**"], access="step", steps=["update_api_docs"])])


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [_GIT or "git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _project(root: Path, scripts: dict[str, str], seed: dict[str, str] | None = None) -> Path:
    folder = root / ".specweaver" / "scripts"
    folder.mkdir(parents=True)
    for name, body in scripts.items():
        (folder / name).write_text(body, encoding="utf-8", newline="\n")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    for path, text in (seed or {}).items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return root


def _step(name: str, script: str, *, own_worktree: bool, gate: GateDefinition | None = None):
    return PipelineStep(
        name=name,
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": script},
        use_worktree=True if own_worktree else None,
        gate=gate,
    )


def _run(root: Path, steps: list[PipelineStep], *, session: bool = False):
    context = RunContext(
        project_path=root, spec_path=root / "spec.md", model=ModelAccess(config=MagicMock())
    )
    context.isolation = context.isolation.model_copy(
        update={"session_isolation": session, "allowed_paths": ["src/**"], "doc_policy": _POLICY}
    )
    pipeline = PipelineDefinition(name="p", steps=steps)
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def _proposals(root: Path) -> str:
    return (root / "doc_updates.md").read_text(encoding="utf-8")


def test_the_named_step_lands_its_doc(tmp_path: Path) -> None:
    root = _project(tmp_path, {"api.sh": "mkdir -p docs/api\necho api > docs/api/x.md\n"})

    run = _run(root, [_step("update_api_docs", "api.sh", own_worktree=True)])

    assert run.status == RunStatus.COMPLETED, run
    assert (root / "docs" / "api" / "x.md").read_text(encoding="utf-8") == "api\n"
    assert not (root / "doc_updates.md").exists()


def test_a_refused_readme_change_becomes_a_proposal(tmp_path: Path) -> None:
    root = _project(tmp_path, {"readme.sh": "echo changed > README.md\n"})

    run = _run(root, [_step("other", "readme.sh", own_worktree=True)])

    assert run.status == RunStatus.COMPLETED, run
    assert (root / "README.md").read_text(encoding="utf-8") == "seed\n"
    proposal = _proposals(root)
    assert "README.md" in proposal
    assert "other" in proposal
    assert "+changed" in proposal
    assert "-seed" in proposal
    assert "doc_updates.md" in _git(root, "show", "--name-only", "HEAD")


def test_a_refused_new_doc_is_deleted_and_proposed(tmp_path: Path) -> None:
    root = _project(tmp_path, {"api.sh": "mkdir -p docs/api\necho api > docs/api/x.md\n"})

    _run(root, [_step("other", "api.sh", own_worktree=True)])

    assert not (root / "docs" / "api").exists()
    assert "docs/api/x.md" in _proposals(root)
    assert "+api" in _proposals(root)


def test_an_existing_doc_updates_is_kept_and_appended(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        {"readme.sh": "echo changed > README.md\n"},
        seed={"doc_updates.md": "# Earlier proposals\n"},
    )

    _run(root, [_step("other", "readme.sh", own_worktree=True)])

    proposal = _proposals(root)
    assert proposal.startswith("# Earlier proposals\n")
    assert "+changed" in proposal


def test_a_protected_change_is_stripped_and_never_proposed(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        {"leak.sh": "echo TOKEN=s3cr3t > .env\necho changed > README.md\n"},
    )

    _run(root, [_step("other", "leak.sh", own_worktree=True)])

    assert not (root / ".env").exists()
    assert "s3cr3t" not in _proposals(root)
    assert ".env" not in _proposals(root)


def test_a_binary_doc_is_named_not_shown(tmp_path: Path) -> None:
    root = _project(tmp_path, {"img.sh": "mkdir -p docs\nprintf '\\x00\\x01\\x02' > docs/a.png\n"})

    _run(root, [_step("other", "img.sh", own_worktree=True)])

    assert "docs/a.png" in _proposals(root)
    assert "binary change, not shown" in _proposals(root)


def test_in_a_session_the_named_steps_doc_lands(tmp_path: Path) -> None:
    root = _project(tmp_path, {"api.sh": "mkdir -p docs/api\necho api > docs/api/x.md\n"})

    run = _run(root, [_step("update_api_docs", "api.sh", own_worktree=False)], session=True)

    assert run.status == RunStatus.COMPLETED, run
    assert (root / "docs" / "api" / "x.md").exists()


def test_in_a_session_a_doc_another_step_also_changed_is_proposed(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        {
            "api.sh": "mkdir -p docs/api\necho api > docs/api/x.md\n",
            "more.sh": "echo more >> docs/api/x.md\n",
        },
    )

    run = _run(
        root,
        [
            _step("update_api_docs", "api.sh", own_worktree=False),
            _step("other", "more.sh", own_worktree=False),
        ],
        session=True,
    )

    assert run.status == RunStatus.COMPLETED, run
    assert not (root / "docs" / "api" / "x.md").exists()
    assert "+more" in _proposals(root)


def test_a_failed_steps_leftover_stays_its_own(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        {
            "fail.sh": "mkdir -p docs/api\necho stray > docs/api/x.md\nexit 1\n",
            "noop.sh": "true\n",
        },
    )
    go_on = GateDefinition(on_fail=OnFailAction.CONTINUE)

    run = _run(
        root,
        [
            _step("other", "fail.sh", own_worktree=False, gate=go_on),
            _step("update_api_docs", "noop.sh", own_worktree=False),
        ],
        session=True,
    )

    assert run.status == RunStatus.COMPLETED, run
    assert not (root / "docs" / "api" / "x.md").exists()
    assert "+stray" in _proposals(root)


def test_a_manifest_change_outside_the_task_is_proposed(tmp_path: Path) -> None:
    """C-FLOW-11 FR-9: adding a dependency stays the user's decision, and is not lost."""
    root = _project(
        tmp_path,
        {
            "dep.sh": 'printf "[project]\\nname = \\"p\\"\\ndependencies = [\\"left-pad\\"]\\n" > pyproject.toml\n'
        },
        seed={"pyproject.toml": '[project]\nname = "p"\n'},
    )

    _run(root, [_step("implement", "dep.sh", own_worktree=True)])

    assert (root / "pyproject.toml").read_text(encoding="utf-8") == '[project]\nname = "p"\n'
    assert '+dependencies = ["left-pad"]' in _proposals(root)
