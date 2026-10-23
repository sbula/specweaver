# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command for drafting a spec: draft, validate and review in one run."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import typer
from rich.markup import escape

from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineDefinition

logger = logging.getLogger(__name__)

drafting_cli = typer.Typer(no_args_is_help=True)


def _build_draft_pipeline(name: str) -> PipelineDefinition:
    """Draft -> validate -> review in ONE pipeline, with no manual handoff.

    Review rejection loops back into a REAL re-draft through the feedback-aware handler, bounded at
    max_retries=2."""
    from specweaver.core.flow.engine.models import (
        GateCondition,
        GateDefinition,
        GateType,
        OnFailAction,
        PipelineDefinition,
        PipelineStep,
        StepAction,
        StepTarget,
    )

    return PipelineDefinition(
        name="draft_spec",
        description=f"Draft, validate and review spec for {name}",
        steps=[
            PipelineStep(
                name="draft_spec",
                action=StepAction.DRAFT,
                target=StepTarget.SPEC,
                description=f"Draft spec for {name}",
            ),
            PipelineStep(
                name="validate_spec",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                description="Run spec validation rules",
                gate=GateDefinition(
                    type=GateType.AUTO,
                    condition=GateCondition.ALL_PASSED,
                    on_fail=OnFailAction.ABORT,
                ),
            ),
            PipelineStep(
                name="review_spec",
                action=StepAction.REVIEW,
                target=StepTarget.SPEC,
                description="LLM semantic review of the spec",
                gate=GateDefinition(
                    type=GateType.AUTO,
                    condition=GateCondition.ACCEPTED,
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="draft_spec",
                    max_retries=2,
                ),
            ),
        ],
    )


def _report_draft_chain(run_state: Any, spec_path: Path) -> None:
    """Inline outcome report — the whole chain's result from one command, with no follow-up
    `sw check` handoff."""
    from specweaver.core.flow.engine.state import StepStatus

    records = {r.step_name: r for r in (run_state.step_records or [])}

    draft_rec = records.get("draft_spec")
    if draft_rec is not None and draft_rec.status == StepStatus.PASSED:
        path = _step_output(records, "draft_spec").get("path", spec_path)
        _core.console.print(f"\n[green]Spec drafted:[/green] {path}")

    _report_validation(_step_output(records, "validate_spec"))
    _report_review(_step_output(records, "review_spec"))


def _step_output(records: dict[str, Any], step_name: str) -> dict[str, Any]:
    """One step's `output` dict, or `{}` when the step is missing, unfinished or non-dict."""
    result = getattr(records.get(step_name), "result", None)
    output = getattr(result, "output", None) if result else None
    return output if isinstance(output, dict) else {}


def _report_validation(validate_out: dict[str, Any]) -> None:
    """Rule tally, then each failure."""
    if not validate_out:
        return

    _core.console.print(
        f"Validation: {validate_out.get('passed', '?')}/{validate_out.get('total', '?')} "
        "rules passed"
    )
    for rule in validate_out.get("results", []) or []:
        # RuleStatus.value is lowercase ("fail") — compare case-insensitively.
        if isinstance(rule, dict) and str(rule.get("status", "")).upper() == "FAIL":
            # escape(): rule messages can embed spec content — stray [/tags] would
            # raise rich.errors.MarkupError and crash the report.
            _core.console.print(
                f"  [red]{escape(str(rule.get('rule_id', '?')))}[/red]: "
                f"{escape(str(rule.get('message', '')))}"
            )


def _report_review(review_out: dict[str, Any]) -> None:
    """Verdict, then the findings behind a rejection."""
    if not review_out:
        return

    verdict = str(review_out.get("verdict", "unknown"))
    _core.console.print(f"Review: {verdict}")
    if verdict == "accepted":
        return

    _core.console.print("[red]Review rejected (re-draft retries exhausted).[/red]")
    for finding in review_out.get("findings") or []:
        text = finding.get("message", finding) if isinstance(finding, dict) else finding
        _core.console.print(f"  [red]-[/red] {escape(str(text))}")


@drafting_cli.command(name="draft")
def draft(
    name: str = typer.Argument(
        help="Name of the component to draft a spec for.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    selector: str = typer.Option(
        "direct",
        "--selector",
        help="Topology selector: direct, nhop, constraint, impact.",
    ),
) -> None:
    """Interactively draft a new component spec with LLM assistance."""
    logger.debug("Executing draft command")
    project_path = _core.project_path_or_exit(project)

    specs_dir = project_path / "specs"
    spec_path = specs_dir / f"{name}_spec.md"
    if spec_path.exists():
        _core.console.print(
            f"[yellow]Warning:[/yellow] {spec_path} already exists. It will NOT be overwritten.",
        )
        raise typer.Exit(code=1)

    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.session import SessionWorktreeError
    from specweaver.core.flow.engine.state import RunStatus
    from specweaver.interfaces.cli.hitl_provider import HITLProvider
    from specweaver.interfaces.cli.run_doors import build_run_or_exit, refuse_unstarted_worktree

    pipeline = _build_draft_pipeline(name)
    context = build_run_or_exit(project_path, spec_path, pipeline, selector=selector)
    context.context_provider = HITLProvider(console=_core.console)

    _core.console.print(
        f"\n[bold]Drafting spec for[/bold] [cyan]{name}[/cyan]\n"
        "[dim]Answer questions below. Press Enter to skip.[/dim]\n",
    )

    runner = PipelineRunner(pipeline, context)
    try:
        run_state = asyncio.run(runner.run())
    except SessionWorktreeError as err:
        refuse_unstarted_worktree(err)

    _report_draft_chain(run_state, spec_path)

    if run_state.status != RunStatus.COMPLETED:
        raise typer.Exit(code=1)
