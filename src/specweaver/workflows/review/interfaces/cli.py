# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command for LLM review: review."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.markup import escape

from specweaver.interfaces.cli import _core

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from specweaver.workflows.review.reviewer import ReviewResult


review_cli = typer.Typer(no_args_is_help=True)


@review_cli.command(name="review")
def review(
    target: str = typer.Argument(
        help="Path to the spec or code file to review.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    spec: str | None = typer.Option(
        None,
        "--spec",
        "-s",
        help="Path to the source spec (required for code review).",
    ),
    selector: str = typer.Option(
        "nhop",
        "--selector",
        help="Topology selector: direct, nhop, constraint, impact.",
    ),
) -> None:
    """Submit a spec or code file for LLM-based review.

    Returns ACCEPTED or DENIED with structured findings.
    For code review, also provide --spec to compare against.
    """
    logger.debug("Executing review command")
    target_path = _core.file_or_exit(target)

    project_path = _core.project_path_or_exit(project)

    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.interfaces.cli.run_doors import build_run_or_exit

    if spec:
        spec_path = Path(spec)
        if not spec_path.exists():
            _core.console.print(f"[red]Error:[/red] Spec not found: {spec}")
            raise typer.Exit(code=1)

        action = StepAction.REVIEW
        target_kind = StepTarget.CODE
        actual_spec_path = spec_path
        params = {"target": str(target_path)}
    else:
        action = StepAction.REVIEW
        target_kind = StepTarget.SPEC
        actual_spec_path = target_path
        params = {}

    pipeline = PipelineDefinition.create_single_step(
        name="review_target",
        action=action,
        target=target_kind,
        description=f"Review {target_path.name}",
        params=params,
    )
    context = build_run_or_exit(
        project_path, actual_spec_path, pipeline, selector=selector, read_only=True
    )
    _core.console.print(f"\n[bold]Reviewing:[/bold] {target_path.name}")
    _core.console.print("[dim]Sending to LLM for semantic review...[/dim]\n")

    runner = PipelineRunner(pipeline, context)

    from specweaver.workflows.review.reviewer import result_from_run

    _display_review_result(result_from_run(asyncio.run(runner.run())))


def _display_review_result(result: ReviewResult) -> None:
    """Display review verdict and findings."""
    from specweaver.workflows.review.reviewer import ReviewVerdict

    verdict_style = {
        ReviewVerdict.ACCEPTED: "[green bold]VERDICT: ACCEPTED[/green bold]",
        ReviewVerdict.DENIED: "[red bold]VERDICT: DENIED[/red bold]",
        ReviewVerdict.ERROR: "[yellow bold]VERDICT: ERROR[/yellow bold]",
    }
    _core.console.print(verdict_style.get(result.verdict, str(result.verdict)))

    if result.summary:
        # escape(): LLM-authored text — stray [/tags] would raise MarkupError.
        _core.console.print(f"\n{escape(result.summary)}")

    if result.findings:
        _core.console.print(f"\n[bold]Findings ({len(result.findings)}):[/bold]")
        for f in result.findings:
            _core.console.print(f"  - {escape(f.message)}")

    if result.verdict in (ReviewVerdict.DENIED, ReviewVerdict.ERROR):
        raise typer.Exit(code=1)
