# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An API-triggered run honours the same `[sandbox]` isolation policy the CLI does.

Proves: TECH-013 FR-1, TECH-013 FR-2

Worktree-isolation policy is a composition-root decision (`ADR-002`), and there are two roots: the
CLI's `sw run` / `sw resume`, and these endpoints. Only the CLI resolved it. So an API-launched run
executed with isolation **off** whatever `[sandbox]` declared — untrusted generated code running
against the real worktree because of which door the run came through.

The gap was known and written into the source as a `KNOWN GAP` comment naming exactly what was
missing: *"what is missing is an API-run test harness"*. That is this file.

It asserts the policy on the `RunContext` the endpoint builds, not a log line: the context is what
the runner reads, and a message saying isolation was applied is not isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.isolation import apply_isolation_policy
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


class _Sandbox:
    def __init__(self, *, per_step: bool, per_run: bool) -> None:
        self.enforce_worktree_isolation = per_step
        self.enforce_session_isolation = per_run
        self.execution_mode = "host"
        self.dal_auto_escalate = False


class _Settings:
    def __init__(self, **kwargs: Any) -> None:
        self.sandbox = _Sandbox(**kwargs)


def _context(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")


def test_an_enabled_per_step_policy_reaches_the_context(tmp_path: Path) -> None:
    context = _context(tmp_path)

    apply_isolation_policy(context, _Settings(per_step=True, per_run=False), _logger())

    assert context.isolation.enforce_isolation is True


def test_a_disabled_policy_stays_disabled(tmp_path: Path) -> None:
    """The control. A resolver that always enabled isolation would pass the test above."""
    context = _context(tmp_path)

    apply_isolation_policy(context, _Settings(per_step=False, per_run=False), _logger())

    assert context.isolation.enforce_isolation is False


def test_the_per_run_policy_is_applied_too(tmp_path: Path) -> None:
    """`session_isolation` is the other half `C-EXEC-06 SF-03` added, and it moved with it."""
    context = _context(tmp_path)

    apply_isolation_policy(context, _Settings(per_step=False, per_run=True), _logger())

    assert context.isolation.session_isolation is True


def test_a_broken_settings_object_does_not_crash_the_run(tmp_path: Path) -> None:
    """Best-effort by contract: a policy lookup must never be the reason a run dies."""
    context = _context(tmp_path)

    apply_isolation_policy(context, object(), _logger())

    assert context.isolation.enforce_isolation is False


def test_no_api_run_context_is_built_without_a_policy() -> None:
    """The gap was three endpoints, not one, and a fix applied to `start` alone would look done.

    Stated as the invariant rather than as a call site: `resume_run` and `submit_gate_decision`
    share their setup through `_resume_existing_run`, so asserting each endpoint contains the call
    literally would fail on a refactor that kept the behaviour. What must hold is that **every**
    place building a `RunContext` also applies the policy.

    Structural because driving all three needs a project, a store and a live runner; what regressed
    before was a run site being added without the call, which is exactly what this sees.
    """
    import ast
    import inspect

    from specweaver.interfaces.api.v1 import pipelines

    tree = ast.parse(inspect.getsource(pipelines))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = ast.dump(node)
        if "'RunContext'" in body and "_apply_isolation" not in body:
            offenders.append(node.name)

    assert offenders == [], f"these build a RunContext without a policy: {offenders}"


def _logger():
    import logging

    return logging.getLogger(__name__)
