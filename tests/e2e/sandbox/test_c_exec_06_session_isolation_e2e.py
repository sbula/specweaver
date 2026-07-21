# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-03 Verifiable Proof (FR-8): real-worktree, multi-step, unmocked e2e.

Drives a real MULTI-step pipeline through the real PipelineRunner under per-run (session)
isolation (`context.session_isolation = True`). Step 1 (bash) freshly generates files into
the ONE session worktree; step 2 (pytest) runs bounded to that SAME worktree and sees the
step-1 output — proving in-session persistence across steps. After the run completes, the
single authorized reconcile lands ONLY `allowed_paths` back into the real repo:

- [Happy/persistence]  step-2 pytest passes iff it ran in `.worktrees` AND step-1's
  `src/foo.py` is present in-tree (one shared worktree across steps).
- [Happy/reconcile]    the real repo gains `src/foo.py` (in allowed_paths).
- [Hostile/NFR-4]      `secret.py` (NOT in allowed_paths) is stripped — absent from real repo.
- [Control]            the same pipeline un-isolated runs at the real root; the probe FAILS
                       (discriminator: proves it actually runs and that isolation is what
                       moved cwd + gated the write-back).
- [Degradation/FR-6]   a non-git project + session on fails loud (isolation never silently
                       skipped).

Requires only git + bash; skips cleanly otherwise (NFR-7).
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

# Generator: writes an ALLOWED source file + a DISALLOWED file, relative to cwd (worktree).
_GEN_SCRIPT = "mkdir -p src\nprintf 'VALUE = 42\\n' > src/foo.py\nprintf 'LEAK = 1\\n' > secret.py\n"

# Generator variant that ALSO writes a docs/ file (hard-blocked even if allow-listed).
_GEN_WITH_DOCS = (
    "mkdir -p src docs\nprintf 'VALUE = 42\\n' > src/foo.py\nprintf 'evil\\n' > docs/evil.md\n"
)

# Probe: passes iff it runs inside the worktree AND step-1's src/foo.py persisted there.
_PERSIST_PROBE = (
    "import os\n\n\n"
    "def test_generated_file_persists_in_worktree() -> None:\n"
    '    assert ".worktrees" in os.getcwd()\n'
    '    assert os.path.exists(os.path.join("src", "foo.py"))\n'
)

_ALLOWED = ["src/foo.py", "tests/test_foo.py"]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True)


def _write_sources(tmp_path: Path, gen_script: str = _GEN_SCRIPT) -> None:
    scripts = tmp_path / ".specweaver" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "gen.sh").write_text(gen_script, encoding="utf-8", newline="\n")
    tests = tmp_path / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_persist_probe.py").write_text(_PERSIST_PROBE, encoding="utf-8", newline="\n")


def _commit_session_project(tmp_path: Path, gen_script: str = _GEN_SCRIPT) -> None:
    """Real git repo whose committed tree carries the generator script + the probe, so the
    ephemeral session worktree checkout carries them."""
    _write_sources(tmp_path, gen_script)
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md", ".specweaver/scripts/gen.sh", "tests/test_persist_probe.py")
    _git(tmp_path, "commit", "-m", "init")


def _gen_step() -> PipelineStep:
    return PipelineStep(
        name="generate",
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": "gen.sh"},
        use_worktree=None,  # defer to the run-level (session) policy
    )


def _probe_step() -> PipelineStep:
    return PipelineStep(
        name="qa",
        action=StepAction.VALIDATE,
        target=StepTarget.TESTS,
        params={"target": "tests", "kind": ""},
        use_worktree=None,
    )


def _run(context: RunContext):
    pipeline = PipelineDefinition(name="p", steps=[_gen_step(), _probe_step()])
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def test_session_isolation_multistep_generates_runs_and_reconciles(tmp_path: Path) -> None:
    """[Happy Path] the full FR-8 proof: multi-step generate -> bounded pytest -> single
    authorized reconcile lands ONLY allowed_paths back in the real repo."""
    _commit_session_project(tmp_path)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    context.session_isolation = True
    context.allowed_paths = _ALLOWED
    run_state = _run(context)

    assert run_state.status == RunStatus.COMPLETED, run_state

    # [persistence] step 2 (pytest) PASSED -> it ran inside the worktree and saw step 1's
    # freshly-generated src/foo.py (guard passed==1 against a 0-collected vacuous pass).
    probe = run_state.step_records[1]
    assert probe.status == StepStatus.PASSED, (run_state.status, probe.result)
    assert probe.result.output.get("passed") == 1, probe.result.output

    # [reconcile] the ALLOWED generated file landed back in the real repo.
    assert (tmp_path / "src" / "foo.py").exists()
    # [Hostile/NFR-4] the DISALLOWED file was stripped — never written back.
    assert not (tmp_path / "secret.py").exists()


def test_session_reconcile_hardblocks_docs_even_when_allowlisted(tmp_path: Path) -> None:
    """[Hostile/NFR-4] the README.md/docs/ hard-block wins over the allow-list: a generated
    `docs/evil.md` is stripped by the session reconcile EVEN when it is explicitly listed in
    allowed_paths. Proves the hard-block is active through the per-run session path, not just
    at the strip_merge unit level."""
    _commit_session_project(tmp_path, gen_script=_GEN_WITH_DOCS)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    context.session_isolation = True
    # Deliberately allow-list the docs file — the hard-block must STILL strip it.
    context.allowed_paths = ["src/foo.py", "tests/test_foo.py", "docs/evil.md"]
    run_state = _run(context)

    assert run_state.status == RunStatus.COMPLETED, run_state
    # The allowed source file landed...
    assert (tmp_path / "src" / "foo.py").exists()
    # ...but the docs file was hard-blocked despite being in allowed_paths.
    assert not (tmp_path / "docs" / "evil.md").exists()


def test_control_not_isolated_runs_at_real_root_and_probe_fails(tmp_path: Path) -> None:
    """[Control] session OFF -> the pipeline runs at the real root, where the worktree
    probe FAILS. The discriminator: proves the probe genuinely executes (not a 0-collected
    false pass) and that isolation is what moved cwd + gated the write-back. No git needed."""
    _write_sources(tmp_path)

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    # session_isolation defaults False — no worktree, no reconcile.
    run_state = _run(context)

    probe = run_state.step_records[1]
    assert probe.status == StepStatus.FAILED, (run_state.status, probe.result)
    # The probe actually ran (and FAILED, cwd is the real root) — discriminator.
    assert probe.result.output.get("failed") == 1, probe.result.output
    # Un-isolated: BOTH files were written directly at the real root (no strip-merge gate).
    assert (tmp_path / "src" / "foo.py").exists()
    assert (tmp_path / "secret.py").exists()


def test_session_isolation_on_non_git_project_fails_loud(tmp_path: Path) -> None:
    """[Graceful Degradation/FR-6] session isolation requested on a NON-git project fails
    loud — isolation is never silently skipped, and no span step touches the real root."""
    _write_sources(tmp_path)  # sources present, but NO `git init`

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    context.session_isolation = True
    context.allowed_paths = _ALLOWED

    with pytest.raises(RuntimeError, match="session isolation could not start"):
        _run(context)

    # Fail-closed: the untrusted generator never ran against the real project root.
    assert not (tmp_path / "secret.py").exists()
