# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""BashActionHandler — runs a bash script via BashActionAtom for an
`action: bash`, `target: script` pipeline step (C-EXEC-02 SF-2)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, _now_iso
from specweaver.sandbox.base import AtomStatus

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
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
    BashActionAtom.run(), which already owns all of that validation (SF-1's
    FR-2/FR-12/FR-13). See C-EXEC-02 SF-2's implementation plan, Q1.
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()

        atom = self._get_atom(context)
        result = atom.run(step.params)

        if result.status == AtomStatus.SUCCESS:
            logger.info("BashActionHandler: script succeeded (%s)", result.message)
            return StepResult(
                status=StepStatus.PASSED,
                output=result.exports,
                started_at=started,
                completed_at=_now_iso(),
            )

        logger.warning("BashActionHandler: script failed: %s", result.message)
        return StepResult(
            status=StepStatus.FAILED,
            output=result.exports,
            error_message=result.message,
            started_at=started,
            completed_at=_now_iso(),
        )

    def _get_atom(self, context: RunContext) -> BashActionAtom:
        """Lazily create a BashActionAtom for the project.

        INT-US-09: under worktree isolation the runner sets ``execution_root`` to the
        worktree source tree; bind the bash cwd there so an untrusted script's writes
        (and its ``.specweaver/scripts`` resolution) are worktree-bounded, not against
        the real project root. Falls back to ``project_path`` when not isolated.
        """
        from specweaver.sandbox.execution.core.atom import BashActionAtom

        return BashActionAtom(cwd=context.execution_root or context.project_path)
