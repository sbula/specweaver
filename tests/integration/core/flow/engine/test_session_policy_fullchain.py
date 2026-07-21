# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-03 G2: full-chain composition-root proof (real git + bash).

Unifies the two independently-proven halves — (a) a real `specweaver.toml` resolved through
the real `apply_session_policy` composition helper, and (b) a real multi-step pipeline run
under per-run isolation with the end-of-run authorized reconcile — into ONE test. Proves the
whole chain: `[sandbox] enforce_session_isolation = true` -> derived `allowed_paths` ->
session run -> only `allowed_paths` land back in the real repo.

Distinct from the e2e (which sets `session_isolation` directly): here the flag AND the
allow-list are produced by `apply_session_policy` from real TOML-loaded settings, exercising
the composition-root seam that feeds `execute_run`.
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
from specweaver.core.config.settings_loader import _load_toml_sandbox
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
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(_GIT is None or _BASH is None, reason="git and bash required"),
]

_LOG = logging.getLogger("test.session_fullchain")
_GEN = "mkdir -p src\nprintf 'V = 1\\n' > src/foo.py\nprintf 'LEAK = 1\\n' > secret.py\n"
_PROBE = (
    "import os\n\n\n"
    "def test_generated_file_persists_in_worktree() -> None:\n"
    '    assert ".worktrees" in os.getcwd()\n'
    '    assert os.path.exists(os.path.join("src", "foo.py"))\n'
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True)


def _commit_project(tmp_path: Path, toml_body: str) -> None:
    (tmp_path / ".specweaver" / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".specweaver" / "scripts" / "gen.sh").write_text(_GEN, encoding="utf-8", newline="\n")
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_persist_probe.py").write_text(_PROBE, encoding="utf-8", newline="\n")
    (tmp_path / "specweaver.toml").write_text(toml_body, encoding="utf-8")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", "README.md", ".specweaver/scripts/gen.sh", "tests/test_persist_probe.py")
    _git(tmp_path, "commit", "-m", "init")


def _pipeline() -> PipelineDefinition:
    return PipelineDefinition(
        name="p",
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


def test_toml_session_policy_drives_isolated_run_and_authorized_reconcile(tmp_path: Path) -> None:
    """[Happy Path] real specweaver.toml -> apply_session_policy -> derived allow-list ->
    real multi-step session run -> reconcile lands ONLY the allowed generated file."""
    _commit_project(tmp_path, "[sandbox]\nenforce_session_isolation = true\n")

    # Real settings, real TOML-loaded [sandbox] section (no db needed for the policy).
    settings = SpecWeaverSettings(
        llm={"model": "gemini-2.0-flash"},
        sandbox=_load_toml_sandbox(str(tmp_path)),
    )
    # spec stem "foo_spec" -> derived allow-list src/foo.py + tests/test_foo.py.
    context = RunContext(
        project_path=tmp_path, spec_path=tmp_path / "foo_spec.md", config=MagicMock()
    )

    # THE composition-root seam under test: policy + allow-list are produced here.
    apply_session_policy(context, settings, _LOG)
    assert context.session_isolation is True
    assert context.allowed_paths == ["src/foo.py", "tests/test_foo.py"]

    run_state = asyncio.run(
        PipelineRunner(_pipeline(), context, registry=StepHandlerRegistry()).run()
    )

    assert run_state.status == RunStatus.COMPLETED, run_state
    # The probe ran bounded to the worktree and saw the freshly-generated file.
    probe = run_state.step_records[1]
    assert probe.status == StepStatus.PASSED, (run_state.status, probe.result)
    assert probe.result.output.get("passed") == 1, probe.result.output
    # Reconcile landed ONLY the allow-listed file; the disallowed one was stripped.
    assert (tmp_path / "src" / "foo.py").exists()
    assert not (tmp_path / "secret.py").exists()


def test_toml_session_policy_off_runs_without_isolation(tmp_path: Path) -> None:
    """[Boundary/NFR-2] with the knob absent, apply_session_policy leaves the run
    un-isolated (session off, empty allow-list) — the composition chain is a true no-op."""
    _commit_project(tmp_path, "[sandbox]\nexecution_mode = \"host\"\n")

    settings = SpecWeaverSettings(
        llm={"model": "gemini-2.0-flash"},
        sandbox=_load_toml_sandbox(str(tmp_path)),
    )
    context = RunContext(
        project_path=tmp_path, spec_path=tmp_path / "foo_spec.md", config=MagicMock()
    )
    apply_session_policy(context, settings, _LOG)

    assert context.session_isolation is False
    assert context.allowed_paths == []
