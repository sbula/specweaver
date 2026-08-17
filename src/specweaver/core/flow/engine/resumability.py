# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which runs may be resumed, and why the others may not.

Without this, resuming an already-COMPLETED run leaves it stuck in ``RUNNING``:
``PipelineRunner.resume()`` sets ``RunStatus.RUNNING`` unconditionally, the loop finds nothing left
to execute, and the corrupted status is persisted by the ``finally:`` block — so
a finished journey reports as in-flight forever, and every status-based query downstream believes
it.

The knowledge already existed, in the wrong place. The ``sw resume`` command's auto-discovery
filters candidates to ``(PARKED, FAILED)`` — it knows COMPLETED is not resumable — but
``sw run --resume <id>`` and the API path bypass that filter entirely and reach the engine, which
has no such guard. One delivery mechanism enforced a rule that was never part of the contract.

FAILED and ABORTED stay resumable on purpose: retrying a failed run is a legitimate thing to want,
and it is what the loop-back and 3-strike machinery already assumes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.flow.engine.state import RunStatus

if TYPE_CHECKING:
    from specweaver.core.flow.engine.state import PipelineRun

#: Terminal states with nothing left to execute. Resuming one is a user mistake, not a workflow.
NOT_RESUMABLE = frozenset({RunStatus.COMPLETED})


def resumability_error(run: PipelineRun | None, run_id: str) -> str | None:
    """The reason ``run`` cannot be resumed, or ``None`` when it can.

    A pure predicate returning a message rather than raising, so callers choose their own failure
    mode — the CLI prints and exits, the engine raises.
    """
    if run is None:
        return f"Run '{run_id}' not found"
    if run.status in NOT_RESUMABLE:
        return (
            f"Run '{run_id}' already completed — nothing to resume. "
            "Start a new run instead; resuming would reopen a finished journey."
        )
    return None
