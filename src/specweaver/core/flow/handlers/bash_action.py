# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""BashActionHandler — runs a bash script via BashActionAtom for an
`action: bash`, `target: script` pipeline step."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _now_iso
from specweaver.sandbox.base import AtomStatus

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.sandbox.execution.core.atom import BashActionAtom

logger = logging.getLogger(__name__)


class BashActionHandler:
    """Runs a `.specweaver/scripts/` script via BashActionAtom (SF-1).

    Step params (see BashActionAtom for full validation rules):
        script: str — bare filename, resolved inside .specweaver/scripts/.
        args: list[str] — optional, default [].
        working_dir: str — optional, relative to project_path.
        timeout_seconds: int — optional, overrides the SubprocessExecutor default.
        env: dict[str, str] — optional, explicit opt-in only.

    This handler is deliberately thin: it does not validate, default, or
    otherwise interpret `step.params` beyond passing it straight through to
    BashActionAtom.run(), which already owns all of that validation.
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()

        atom = self._get_atom(context)
        result = atom.run(step.params)

        if result.status == AtomStatus.SUCCESS:
            logger.info("BashActionHandler: script succeeded (%s)", result.message)
            refused = _fill_block(step.name, result.exports, context)
            if refused:
                return StepResult(
                    status=StepStatus.FAILED,
                    output=result.exports,
                    error_message=refused,
                    started_at=started,
                    completed_at=_now_iso(),
                )
            return StepResult(
                status=StepStatus.PASSED,
                output=result.exports,
                started_at=started,
                completed_at=_now_iso(),
            )

        logger.warning("BashActionHandler: script failed: %s", result.message)
        # A script that ran and exited non-zero failed; one that never ran is an error (FR-13).
        ran = "exit_code" in result.exports
        return StepResult(
            status=StepStatus.FAILED if ran else StepStatus.ERROR,
            output=result.exports,
            error_message=result.message,
            started_at=started,
            completed_at=_now_iso(),
        )

    def _get_atom(self, context: RunContext) -> BashActionAtom:
        """Lazily create a BashActionAtom for the project.

        Under worktree isolation the runner sets ``execution_root`` to the
        worktree source tree; bind the bash cwd there so an untrusted script's writes
        (and its ``.specweaver/scripts`` resolution) are worktree-bounded, not against
        the real project root. Falls back to ``project_path`` when not isolated.
        """
        from specweaver.sandbox.execution.core.atom import BashActionAtom

        return BashActionAtom(cwd=context.isolation.execution_root or context.project_path)


def _fill_block(step: str, exports: dict[str, Any], context: RunContext) -> str | None:
    """Write the script's output into the block this step fills, if any; why it could not, if not.

    SpecWeaver writes the block, not the script, so the script cannot reach past it.
    """
    from specweaver.commons.doc_blocks import fill_block

    block = next((b for b in context.isolation.doc_policy.block if b.step == step), None)
    if block is None:
        return None
    root = (context.isolation.execution_root or context.project_path).resolve()
    target = (root / block.file).resolve()
    if not target.is_relative_to(root):
        return f"{block.file} lies outside the project; block {block.name!r} was not written"
    if exports.get("stdout_truncated"):
        return f"the output was cut at 1 MiB; block {block.name!r} in {block.file} was not written"
    try:
        with target.open(encoding="utf-8", newline="") as source:
            text = source.read()
        filled = fill_block(text, block.name, str(exports.get("stdout", "")))
    except (OSError, ValueError) as exc:
        return f"block {block.name!r} in {block.file}: {exc}"
    with target.open("w", encoding="utf-8", newline="") as sink:
        sink.write(filled)
    return None
