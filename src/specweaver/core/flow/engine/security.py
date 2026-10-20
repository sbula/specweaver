# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pre-run safety checks that must fail the run rather than warn.

The vault-binding audit: a tracked `vault.env` aborts execution rather than leaking credentials
into a commit. The generated-block audit: a `[[docs.block]]` is filled by a `bash` step only, and
never in a protected file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.handlers.run_context import RunContext


def verify_vault_security(context: RunContext) -> None:
    """Feature 3.32c SF-1: Safe Vault Binding Audit (Option D)."""
    vault_path = context.project_path / ".specweaver" / "vault.env"
    if vault_path.exists():
        from specweaver.sandbox.git.core.atom import GitAtom

        git_atom = GitAtom(cwd=context.project_path)
        # Check if tracked
        result = git_atom.run({"intent": "is_tracked", "path": ".specweaver/vault.env"})
        if getattr(result, "exports", {}).get("is_tracked", False):
            raise RuntimeError(
                "FATAL: vault.env is currently tracked by Git! Aborting execution to prevent credential leakage."
            )


def verify_doc_blocks(pipeline: PipelineDefinition, context: RunContext) -> None:
    """Refuse the run when a block would be filled by a step that is not `bash`, or in a protected
    file: no model writes a block, and no block opens a file the walls keep closed."""
    from specweaver.core.flow.engine.models import StepAction
    from specweaver.sandbox.security import PROTECTED_NAMES

    actions = {step.name: step.action for step in pipeline.steps}
    for block in context.isolation.doc_policy.block:
        where = f"block {block.name!r} in {block.file}"
        parts = block.file.replace("\\", "/").lower().split("/")
        if PROTECTED_NAMES.intersection(parts):
            msg = f"{where}: {block.file} is protected; no step may write it"
            raise ValueError(msg)
        action = actions.get(block.step)
        if action is not None and action != StepAction.BASH:
            msg = f"{where}: step {block.step!r} is a {action.value} step; only a bash step fills a block"
            raise ValueError(msg)


def verify_agentic_ceiling(pipeline: PipelineDefinition, context: RunContext) -> None:
    """Refuse a run that would go agentic in a project that named no ceiling."""
    from specweaver.core.flow.engine.autonomy import NO_CEILING, ExecutionMode, requested_mode

    policy = context.isolation.autonomy
    if policy.agentic_max_dal is not None:
        return
    for step in pipeline.steps:
        if requested_mode(step, policy) is ExecutionMode.AGENTIC:
            msg = f"step {step.name!r} asks for agentic, and the project names no ceiling: {NO_CEILING}"
            raise ValueError(msg)
