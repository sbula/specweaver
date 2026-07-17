# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-09 Verifiable Proof (FR-6): real-worktree, unmocked end-to-end.

Drives a real `action: bash` step through the real PipelineRunner + GitAtom into a
real ephemeral git worktree, and proves the untrusted process executes bounded to the
worktree source tree (its `pwd` is inside `.worktrees/...`) — not the real project root.

The marker script is committed to the repo, so the worktree checkout carries it; the
worktree-cache `.specweaver` symlink is best-effort (a warning if unsupported), so this
runs cross-platform. Requires only git + bash; skips cleanly otherwise (NFR-7).
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
_BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(_GIT is None or _BASH is None, reason="git and bash required")

_MARKER_SCRIPT = 'echo "PWD=$(pwd)"\necho sentinel > marker.txt\n'


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True)


def _write_marker_script(tmp_path: Path) -> None:
    scripts = tmp_path / ".specweaver" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "mark.sh").write_text(_MARKER_SCRIPT, encoding="utf-8", newline="\n")


def _commit_project_with_script(tmp_path: Path) -> None:
    """Real git repo whose committed tree includes the marker script, so the ephemeral
    worktree checkout carries it (no reliance on the best-effort `.specweaver` symlink)."""
    _write_marker_script(tmp_path)
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md", ".specweaver/scripts/mark.sh")
    _git(tmp_path, "commit", "-m", "init")


def _bash_step(*, use_worktree: bool | None) -> PipelineStep:
    return PipelineStep(
        name="mark",
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": "mark.sh"},
        use_worktree=use_worktree,
    )


def _run(pipeline: PipelineDefinition, context: RunContext):
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def _stdout(run_state) -> str:
    record = run_state.step_records[0]
    assert record.result is not None, run_state
    return record.result.output["stdout"]


def test_explicit_use_worktree_runs_bash_bounded_to_worktree(tmp_path: Path) -> None:
    """[Happy Path] use_worktree=True → the real bash process runs inside the worktree."""
    _commit_project_with_script(tmp_path)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    run_state = _run(PipelineDefinition(name="p", steps=[_bash_step(use_worktree=True)]), context)

    assert run_state.status == RunStatus.COMPLETED, run_state
    # The untrusted process's own pwd is inside the ephemeral worktree — proof that
    # execution was bounded there, not against the real project root.
    assert ".worktrees" in _stdout(run_state)
    # FR-6 (blast radius): the untrusted write did NOT reach the real source root.
    assert not (tmp_path / "marker.txt").exists()


def test_policy_enforced_runs_bash_bounded_to_worktree(tmp_path: Path) -> None:
    """[Happy Path — the real US-9 path] use_worktree=None + enforce_isolation=True
    (the isolation policy) → the bash process still runs inside the worktree."""
    _commit_project_with_script(tmp_path)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    context.enforce_isolation = True  # the policy resolved at the composition root
    run_state = _run(PipelineDefinition(name="p", steps=[_bash_step(use_worktree=None)]), context)

    assert run_state.status == RunStatus.COMPLETED, run_state
    assert ".worktrees" in _stdout(run_state)
    # FR-6 (blast radius): the untrusted write did NOT reach the real source root.
    assert not (tmp_path / "marker.txt").exists()


_CWD_PROBE_TEST = (
    "import os\n\n\ndef test_runs_inside_worktree() -> None:\n"
    '    assert ".worktrees" in os.getcwd()\n'
)


def _commit_pytest_project(tmp_path: Path) -> None:
    """Real git repo whose committed tree carries a pytest test that asserts its own
    cwd is inside `.worktrees` — it PASSES iff pytest ran worktree-bounded."""
    tests = tmp_path / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_cwd_probe.py").write_text(_CWD_PROBE_TEST, encoding="utf-8", newline="\n")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md", "tests/test_cwd_probe.py")
    _git(tmp_path, "commit", "-m", "init")


def test_run_tests_pytest_executes_bounded_to_worktree(tmp_path: Path) -> None:
    """[Happy Path — the other untrusted surface] ValidateTests -> QARunnerAtom -> pytest
    runs bounded to the worktree under the isolation policy. The committed probe test
    asserts its own cwd is inside `.worktrees`, so a PASSED step proves it ran there."""
    _commit_pytest_project(tmp_path)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    context.enforce_isolation = True  # the US-9 policy
    step = PipelineStep(
        name="qa",
        action=StepAction.VALIDATE,
        target=StepTarget.TESTS,
        params={"target": "tests", "kind": ""},
        use_worktree=None,  # defer to the policy
    )
    run_state = _run(PipelineDefinition(name="p", steps=[step]), context)

    record = run_state.step_records[0]
    assert record.status == StepStatus.PASSED, (run_state.status, record.result)
    # Guard against a 0-collected vacuous pass: the probe MUST have actually run.
    assert record.result.output.get("passed") == 1, record.result.output


def test_run_tests_not_isolated_runs_at_project_root(tmp_path: Path) -> None:
    """[Control] NO isolation → pytest runs at the real project root, where the same
    worktree-cwd probe FAILS. This is the discriminator: it proves the probe actually
    executes (not a 0-tests false pass) AND that isolation is what moved cwd into the
    worktree in the paired test above. No git/worktree needed."""
    tests = tmp_path / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_cwd_probe.py").write_text(_CWD_PROBE_TEST, encoding="utf-8", newline="\n")

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    step = PipelineStep(
        name="qa",
        action=StepAction.VALIDATE,
        target=StepTarget.TESTS,
        params={"target": "tests", "kind": ""},
        use_worktree=False,  # force NO isolation
    )
    run_state = _run(PipelineDefinition(name="p", steps=[step]), context)

    record = run_state.step_records[0]
    assert record.status == StepStatus.FAILED, (run_state.status, record.result)
    # The probe actually ran here too (and FAILED, since cwd is the real root) — this is
    # the discriminator proving the paired isolated test isn't a 0-collected false pass.
    assert record.result.output.get("failed") == 1, record.result.output


def test_not_isolated_runs_bash_at_project_root(tmp_path: Path) -> None:
    """[Control/Boundary] use_worktree=False → NO isolation; bash runs at the real
    project root (proves the rebind only happens under isolation). No git needed."""
    _write_marker_script(tmp_path)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    run_state = _run(PipelineDefinition(name="p", steps=[_bash_step(use_worktree=False)]), context)

    assert run_state.status == RunStatus.COMPLETED, run_state
    stdout = _stdout(run_state)
    assert ".worktrees" not in stdout
    # The marker was written directly at the real project root (not isolated).
    assert (tmp_path / "marker.txt").exists()
