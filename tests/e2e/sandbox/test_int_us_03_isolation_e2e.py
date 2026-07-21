# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-03 SF-03 Verifiable Proof (FR-8): the autonomous implement loop runs QA on freshly
generated, untrusted code worktree-bounded — engaged by DAL-driven auto-escalation.

Drives a real multi-step pipeline through the real PipelineRunner, with the per-run session
isolation policy resolved exactly as `sw implement` does it: `apply_session_policy(...,
dal_auto_escalate=True)` over a project marked DAL_B. Step 1 (bash) freshly generates code
into the ONE session worktree; step 2 runs pytest bounded to that same worktree; the single
end-of-run reconcile lands ONLY `allowed_paths` back into the real repo.

- [Happy]        DAL_B project → escalation ON → generated code runs QA in `.worktrees`,
                 reconcile lands `src/foo.py` only.
- [Hostile/NFR-4] `secret.py` (not allow-listed) is stripped — absent from the real repo.
- [Control]      a DAL_E project → escalation OFF → loop on host, probe FAILS at the real root
                 (discriminator: proves the probe genuinely runs and DAL gates isolation).

Requires only git + bash; skips cleanly otherwise (NFR-6 / NFR-4).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.config.settings import SpecWeaverSettings
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.runner_utils import apply_session_policy
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
_BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(_GIT is None or _BASH is None, reason="git and bash required")

_LOG = logging.getLogger("test.int_us_03_isolation")
_GEN = "mkdir -p src\nprintf 'VALUE = 42\\n' > src/foo.py\nprintf 'LEAK = 1\\n' > secret.py\n"
_PROBE = (
    "import os\n\n\n"
    "def test_generated_code_runs_in_worktree() -> None:\n"
    '    assert ".worktrees" in os.getcwd()\n'
    '    assert os.path.exists(os.path.join("src", "foo.py"))\n'
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True)


def _commit_project(tmp_path: Path, dal: str) -> None:
    """Real git repo marked at a given DAL, carrying the generator script + the probe."""
    (tmp_path / ".specweaver" / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".specweaver" / "scripts" / "gen.sh").write_text(_GEN, encoding="utf-8", newline="\n")
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_persist_probe.py").write_text(_PROBE, encoding="utf-8", newline="\n")
    (tmp_path / "context.yaml").write_text(
        f"operational:\n  dal_level: {dal}\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    _git(
        tmp_path,
        "add",
        "README.md",
        "context.yaml",
        ".specweaver/scripts/gen.sh",
        "tests/test_persist_probe.py",
    )
    _git(tmp_path, "commit", "-m", "init")


def _pipeline() -> PipelineDefinition:
    return PipelineDefinition(
        name="implement_like",
        steps=[
            PipelineStep(
                name="generate",
                action=StepAction.BASH,
                target=StepTarget.SCRIPT,
                params={"script": "gen.sh"},
                use_worktree=None,
            ),
            PipelineStep(
                name="qa",
                action=StepAction.VALIDATE,
                target=StepTarget.TESTS,
                params={"target": "tests", "kind": ""},
                use_worktree=None,
            ),
        ],
    )


def _context(tmp_path: Path) -> RunContext:
    """A RunContext wired exactly like `sw implement` — the per-run policy is resolved via
    apply_session_policy with DAL escalation opted in."""
    context = RunContext(
        project_path=tmp_path, spec_path=tmp_path / "foo_spec.md", config=MagicMock()
    )
    settings = SpecWeaverSettings(llm={"model": "test-model"})  # sandbox: default DAL_B threshold
    apply_session_policy(context, settings, _LOG, dal_auto_escalate=True)
    return context


def _run(context: RunContext):
    return asyncio.run(PipelineRunner(_pipeline(), context, registry=StepHandlerRegistry()).run())


def test_dal_b_escalation_runs_generated_qa_bounded_and_reconciles(tmp_path: Path) -> None:
    """[Happy/FR-8] a DAL_B project auto-escalates: generated code runs QA worktree-bounded,
    and the single authorized reconcile lands ONLY the allow-listed file."""
    _commit_project(tmp_path, "DAL_B")

    context = _context(tmp_path)
    assert context.session_isolation is True  # DAL_B escalated
    assert context.allowed_paths == ["src/foo.py", "tests/test_foo.py"]

    run_state = _run(context)
    assert run_state.status == RunStatus.COMPLETED, run_state

    # [persistence + bounded] the probe ran inside the worktree and saw step-1's file.
    probe = run_state.step_records[1]
    assert probe.status == StepStatus.PASSED, (run_state.status, probe.result)
    assert probe.result.output.get("passed") == 1, probe.result.output

    # [reconcile] the allow-listed generated file landed; the disallowed one was stripped.
    assert (tmp_path / "src" / "foo.py").exists()
    assert not (tmp_path / "secret.py").exists()  # [Hostile/NFR-4]


def test_low_dal_project_runs_on_host_and_probe_fails(tmp_path: Path) -> None:
    """[Control] a DAL_E project does NOT escalate → the loop runs at the real root, where the
    worktree probe FAILS. Discriminator: proves the probe genuinely runs and that DAL is what
    gated isolation in the paired test above."""
    _commit_project(tmp_path, "DAL_E")

    context = _context(tmp_path)
    assert context.session_isolation is False  # DAL_E is below the DAL_B threshold

    run_state = _run(context)
    probe = run_state.step_records[1]
    assert probe.status == StepStatus.FAILED, (run_state.status, probe.result)
    assert probe.result.output.get("failed") == 1, probe.result.output
    # Un-isolated: the generated files were written directly at the real root.
    assert (tmp_path / "src" / "foo.py").exists()
    assert (tmp_path / "secret.py").exists()
