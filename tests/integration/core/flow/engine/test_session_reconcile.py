# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-02 (T2): the authorized reconcile — real git, unmocked.

At span end (COMPLETED runs only), the session worktree's changes are committed and
strip-merged back to the real repo — writing back ONLY paths in ``allowed_paths``. This
is the DAL-C authorization gate: a file outside the allow-list must never reach the real repo.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
_BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(_GIT is None or _BASH is None, reason="git and bash required")

# Generates one allowed file (src/foo.py) and one disallowed file (secret.py).
_GEN = 'mkdir -p src\necho "def foo(): pass" > src/foo.py\necho "SECRET" > secret.py\n'
_FAIL = "exit 1\n"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True, text=True)


def _commit_project(tmp_path: Path, *scripts: tuple[str, str]) -> None:
    sd = tmp_path / ".specweaver" / "scripts"
    sd.mkdir(parents=True, exist_ok=True)
    rel = []
    for name, body in scripts:
        (sd / name).write_text(body, encoding="utf-8", newline="\n")
        rel.append(f".specweaver/scripts/{name}")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md", *rel)
    _git(tmp_path, "commit", "-m", "init")


def _bash(name: str, script: str) -> PipelineStep:
    return PipelineStep(name=name, action=StepAction.BASH, target=StepTarget.SCRIPT, params={"script": script})


def _ctx(tmp_path: Path, *, allowed: list[str]) -> RunContext:
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    ctx.session_isolation = True
    ctx.allowed_paths = allowed
    return ctx


def _run(pipe: PipelineDefinition, ctx: RunContext):
    return asyncio.run(PipelineRunner(pipe, ctx, registry=StepHandlerRegistry()).run())


# --- Happy + Hostile: only the allowed file lands in the real repo --------


def test_reconcile_lands_allowed_strips_disallowed(tmp_path: Path) -> None:
    _commit_project(tmp_path, ("gen.sh", _GEN))
    run_state = _run(
        PipelineDefinition(name="p", steps=[_bash("g", "gen.sh")]),
        _ctx(tmp_path, allowed=["src/foo.py"]),
    )
    assert run_state.status == RunStatus.COMPLETED, run_state
    # Allowed file was reconciled into the REAL repo (committed → present in the working tree).
    assert (tmp_path / "src" / "foo.py").exists()
    # Disallowed file was STRIPPED — never reached the real repo.
    assert not (tmp_path / "secret.py").exists()
    # It landed as a commit (authorized write-back).
    log = _git(tmp_path, "log", "--oneline").stdout
    assert "strip merge" in log or "session" in log.lower()


# --- Degradation: a failed run does NOT reconcile -------------------------


def test_failed_run_skips_reconcile(tmp_path: Path) -> None:
    _commit_project(tmp_path, ("gen.sh", _GEN), ("fail.sh", _FAIL))
    run_state = _run(
        PipelineDefinition(name="p", steps=[_bash("g", "gen.sh"), _bash("f", "fail.sh")]),
        _ctx(tmp_path, allowed=["src/foo.py"]),
    )
    assert run_state.status != RunStatus.COMPLETED
    # No reconcile → the real repo is untouched.
    assert not (tmp_path / "src" / "foo.py").exists()


# --- Degradation: a strip_merge failure is surfaced (not swallowed) -------


def test_strip_merge_failure_is_surfaced(tmp_path: Path) -> None:
    from specweaver.sandbox.base import AtomResult, AtomStatus

    _commit_project(tmp_path, ("gen.sh", _GEN))

    real_run = __import__(
        "specweaver.sandbox.git.core.atom", fromlist=["GitAtom"]
    ).GitAtom.run

    def _fail_strip(self, context):
        if context.get("intent") == "strip_merge":
            return AtomResult(status=AtomStatus.FAILED, message="strip merge boom")
        return real_run(self, context)

    with (
        patch("specweaver.sandbox.git.core.atom.GitAtom.run", _fail_strip),
        pytest.raises(RuntimeError, match="strip"),
    ):
        _run(
            PipelineDefinition(name="p", steps=[_bash("g", "gen.sh")]),
            _ctx(tmp_path, allowed=["src/foo.py"]),
        )


# --- Degradation: dirty real working tree that the merge would clobber -----


def test_dirty_real_tree_fails_loud_and_leaves_repo_clean(tmp_path: Path) -> None:
    # Commit src/foo.py so it is tracked, plus gen.sh which rewrites it in the worktree.
    sd = tmp_path / ".specweaver" / "scripts"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "gen.sh").write_text('echo "def foo(): pass" > src/foo.py\n', encoding="utf-8", newline="\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "foo.py").write_text("original\n", encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md", "src/foo.py", ".specweaver/scripts/gen.sh")
    _git(tmp_path, "commit", "-m", "init")

    # The user has an UNCOMMITTED change to src/foo.py — the reconcile merge would clobber it.
    (src / "foo.py").write_text("DIRTY LOCAL EDIT\n", encoding="utf-8")

    with pytest.raises(RuntimeError):
        _run(
            PipelineDefinition(name="p", steps=[_bash("g", "gen.sh")]),
            _ctx(tmp_path, allowed=["src/foo.py"]),
        )

    # The user's uncommitted work is intact and the real repo is left clean (merge aborted).
    assert (src / "foo.py").read_text(encoding="utf-8") == "DIRTY LOCAL EDIT\n"
    status = _git(tmp_path, "status", "--porcelain").stdout
    assert "UU" not in status and "<<<<" not in (src / "foo.py").read_text(encoding="utf-8")


def _log(tmp_path: Path) -> str:
    return _git(tmp_path, "log", "--oneline").stdout


def _no_worktrees_or_branch(tmp_path: Path) -> None:
    wt = tmp_path / ".worktrees"
    assert not wt.exists() or not any(wt.iterdir())
    assert "sf-session-" not in _git(tmp_path, "branch").stdout


def _patch_intent_fail(intent: str):
    """Patch GitAtom.run so a given intent returns FAILED, passing others through."""
    from specweaver.sandbox.base import AtomResult, AtomStatus

    real = __import__("specweaver.sandbox.git.core.atom", fromlist=["GitAtom"]).GitAtom.run

    def _run(self, context):
        if context.get("intent") == intent:
            return AtomResult(status=AtomStatus.FAILED, message=f"{intent} boom")
        return real(self, context)

    return patch("specweaver.sandbox.git.core.atom.GitAtom.run", _run)


# --- G1 [Hostile]: empty allowed_paths → nothing lands --------------------


def test_empty_allowed_paths_lands_nothing(tmp_path: Path) -> None:
    _commit_project(tmp_path, ("gen.sh", _GEN))
    run_state = _run(PipelineDefinition(name="p", steps=[_bash("g", "gen.sh")]), _ctx(tmp_path, allowed=[]))
    assert run_state.status == RunStatus.COMPLETED
    assert not (tmp_path / "src" / "foo.py").exists()
    assert not (tmp_path / "secret.py").exists()
    assert "strip merge" not in _log(tmp_path)  # nothing committed back


# --- G2 [Hostile]: README/docs hard-block wins over the allow-list ---------


def test_docs_hardblocked_even_if_allowed(tmp_path: Path) -> None:
    gen = 'mkdir -p docs\necho "evil" > docs/evil.md\n'
    _commit_project(tmp_path, ("gd.sh", gen))
    # docs/evil.md is EXPLICITLY allowed — the hard-block must still strip it.
    run_state = _run(PipelineDefinition(name="p", steps=[_bash("g", "gd.sh")]), _ctx(tmp_path, allowed=["docs/evil.md"]))
    assert run_state.status == RunStatus.COMPLETED
    assert not (tmp_path / "docs" / "evil.md").exists()


# --- G3 [Degradation]: reconcile raises on worktree_commit failure ---------


def test_reconcile_raises_on_commit_failure(tmp_path: Path) -> None:
    _commit_project(tmp_path, ("gen.sh", _GEN))
    with _patch_intent_fail("worktree_commit"), pytest.raises(RuntimeError, match="commit"):
        _run(PipelineDefinition(name="p", steps=[_bash("g", "gen.sh")]), _ctx(tmp_path, allowed=["src/foo.py"]))


# --- G4 [Graceful teardown]: worktree + branch cleaned up on reconcile fail -


def test_worktree_torn_down_on_reconcile_failure(tmp_path: Path) -> None:
    _commit_project(tmp_path, ("gen.sh", _GEN))
    with _patch_intent_fail("strip_merge"), pytest.raises(RuntimeError):
        _run(PipelineDefinition(name="p", steps=[_bash("g", "gen.sh")]), _ctx(tmp_path, allowed=["src/foo.py"]))
    # The finally teardown ran despite the reconcile failure — no orphaned worktree/branch.
    _no_worktrees_or_branch(tmp_path)


# --- G5 [Boundary]: all files stripped → no commit, repo clean ------------


def test_all_stripped_leaves_repo_clean(tmp_path: Path) -> None:
    gen = 'echo "secret" > secret.py\n'  # only a disallowed file
    _commit_project(tmp_path, ("gs.sh", gen))
    run_state = _run(PipelineDefinition(name="p", steps=[_bash("g", "gs.sh")]), _ctx(tmp_path, allowed=["src/foo.py"]))
    assert run_state.status == RunStatus.COMPLETED
    assert not (tmp_path / "secret.py").exists()
    assert "strip merge" not in _log(tmp_path)  # nothing merged
    _no_worktrees_or_branch(tmp_path)


# --- G6 [Boundary]: session generates nothing → clean no-op reconcile ------


def test_empty_session_noop_reconcile(tmp_path: Path) -> None:
    _commit_project(tmp_path, ("noop.sh", "echo hi\n"))
    run_state = _run(PipelineDefinition(name="p", steps=[_bash("g", "noop.sh")]), _ctx(tmp_path, allowed=["src/foo.py"]))
    assert run_state.status == RunStatus.COMPLETED
    assert "strip merge" not in _log(tmp_path)  # nothing to reconcile


# --- G7 [Boundary]: doc_updates.md always survives the strip (FR-8) --------


def test_doc_updates_md_survives(tmp_path: Path) -> None:
    _commit_project(tmp_path, ("du.sh", 'echo "claim" > doc_updates.md\n'))
    # Even with an empty allow-list, doc_updates.md survives by explicit rule.
    run_state = _run(PipelineDefinition(name="p", steps=[_bash("g", "du.sh")]), _ctx(tmp_path, allowed=[]))
    assert run_state.status == RunStatus.COMPLETED
    assert (tmp_path / "doc_updates.md").exists()
