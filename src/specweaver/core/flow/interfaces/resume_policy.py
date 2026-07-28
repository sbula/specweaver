# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the CLI permits and says when a user asks to resume a run.

Two rules, both learned from defects in INT-US-21 SF-03:

* **Refuse to reopen a finished journey.** `PipelineRunner.resume()` sets `RunStatus.RUNNING`
  unconditionally, so resuming a COMPLETED run left it stuck in RUNNING forever — a finished
  journey reporting as in-flight, and every status query downstream believing it. The `sw resume`
  command's auto-discovery already knew this (it only offers PARKED and FAILED candidates), but
  `sw run --resume <id>` bypassed that filter entirely.
* **Never print an instruction the user cannot follow.** The Ctrl-C hint said
  `Resume with: sw run --resume` with no id, because the handler sat outside the frame that owned
  it.

Split out of `cli.py` on 2026-07-28, which the resume guard took to 606 lines against a 600-line
RED threshold. Named for the contract — the rules governing a resume request — rather than for the
code, so it cannot accrete unrelated CLI helpers. The engine-side predicate lives in
`engine/resumability.py`; this module is only the delivery-layer half.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from specweaver.core.flow.engine.resumability import resumability_error
from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from specweaver.core.flow.engine.store import StateStore


def guard_resumable(store: StateStore, run_id: str) -> None:
    """Stop the command when `run_id` names a run that must not be resumed.

    Raises ``typer.Exit(1)`` after printing the reason, so the caller needs no error handling.
    """
    problem = resumability_error(store.load_run(run_id), run_id)
    if problem:
        _core.console.print(f"[red]Error:[/red] {problem}")
        raise typer.Exit(code=1)


def print_resume_hint(run_id: str | None) -> None:
    """Tell the user how to resume, naming the run when it is known.

    ``sw resume <id>`` and ``sw run --resume <id>`` both exist and both stay: they are real
    commands, and telling someone interrupted during ``sw resume`` to type ``sw run --resume``
    would be the worse instruction. What is enforced is the narrower contract the defect named —
    every resume instruction must carry a run id, or say how to find one.
    """
    if run_id:
        _core.console.print(
            "\n[yellow]Interrupted.[/yellow] [dim]Run state saved. "
            f"Resume with:[/dim] sw run --resume {run_id}",
        )
        return
    _core.console.print(
        "\n[yellow]Interrupted.[/yellow] [dim]Run state saved. "
        "Find the run with `sw runs` and resume with: sw run --resume <run_id>[/dim]",
    )
