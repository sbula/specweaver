# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for LLM review: draft, review."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from specweaver.interfaces.cli import _core, _helpers
from specweaver.interfaces.cli._helpers import (
    _load_constitution_content,
    _load_standards_content,
    _load_topology,
    _select_topology_contexts,
)
from specweaver.workspace.project.discovery import resolve_project_path

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from specweaver.workflows.review.reviewer import ReviewResult


@_core.app.command()
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
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    specs_dir = project_path / "specs"
    spec_path = specs_dir / f"{name}_spec.md"
    if spec_path.exists():
        _core.console.print(
            f"[yellow]Warning:[/yellow] {spec_path} already exists. It will NOT be overwritten.",
        )
        raise typer.Exit(code=1)

    from specweaver.core.flow._base import RunContext
    from specweaver.core.flow.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.runner import PipelineRunner
    from specweaver.core.flow.state import StepStatus
    from specweaver.workspace.context.hitl_provider import HITLProvider

    settings, adapter, _ = _helpers._require_llm_adapter(project_path)

    # Load topology context for the new component (best-effort)
    topo_graph = _load_topology(project_path)
    topo_contexts = _select_topology_contexts(
        topo_graph,
        name,
        selector_name=selector,
    )

    _core.console.print(
        f"\n[bold]Drafting spec for[/bold] [cyan]{name}[/cyan]\n"
        "[dim]Answer questions below. Press Enter to skip.[/dim]\n",
    )

    pipeline = PipelineDefinition.create_single_step(
        name="draft_spec",
        action=StepAction.DRAFT,
        target=StepTarget.SPEC,
        description=f"Draft spec for {name}",
    )

    context = RunContext(
        project_path=project_path,
        spec_path=spec_path,
        llm=adapter,
        config=settings,
        context_provider=HITLProvider(console=_core.console),
        topology=topo_contexts,
        db=_core.get_db(),
    )

    runner = PipelineRunner(pipeline, context)
    run_state = asyncio.run(runner.run())

    last_record = run_state.step_records[-1] if run_state.step_records else None

    if last_record and last_record.status == StepStatus.PASSED and last_record.result:
        result_path = last_record.result.output.get("path", spec_path)
    else:
        # If parked or failed, printing a simple message and exiting
        raise typer.Exit(code=1)

    _core.console.print(f"\n[green]Spec drafted:[/green] {result_path}")
    _core.console.print("[dim]Run 'sw check' to validate the drafted spec.[/dim]")


@_core.app.command()
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
    target_path = Path(target)
    if not target_path.exists():
        _core.console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.core.flow._base import RunContext
    from specweaver.core.flow.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.runner import PipelineRunner

    settings, adapter, _ = _helpers._require_llm_adapter(project_path)
    if settings and getattr(settings, "llm", None):
        settings.llm.temperature = 0.3  # Lower for reviews

    # Load topology context for the review target
    topo_graph = _load_topology(project_path)
    module_name = target_path.stem.removesuffix("_spec")
    topo_contexts = _select_topology_contexts(
        topo_graph,
        module_name,
        selector_name=selector,
    )

    _core.console.print(f"\n[bold]Reviewing:[/bold] {target_path.name}")
    _core.console.print("[dim]Sending to LLM for semantic review...[/dim]\n")

    if spec:
        spec_path = Path(spec)
        if not spec_path.exists():
            _core.console.print(f"[red]Error:[/red] Spec not found: {spec}")
            raise typer.Exit(code=1)

        action = StepAction.REVIEW
        target_kind = StepTarget.CODE
        actual_spec_path = spec_path
        params = {"target_path": str(target_path)}
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

    context = RunContext(
        project_path=project_path,
        spec_path=actual_spec_path,
        llm=adapter,
        config=settings,
        topology=topo_contexts,
        constitution=_load_constitution_content(project_path, spec_path=actual_spec_path),
        standards=_load_standards_content(project_path, target_path=target_path),
        db=_core.get_db(),
    )

    runner = PipelineRunner(pipeline, context)
    run_state = asyncio.run(runner.run())

    last_record = run_state.step_records[-1] if run_state.step_records else None

    from specweaver.workflows.review.reviewer import ReviewFinding, ReviewResult, ReviewVerdict

    if last_record and last_record.result:
        out = last_record.result.output
        verdict_str = out.get("verdict", "error")
        try:
            verdict = ReviewVerdict(verdict_str)
        except ValueError:
            verdict = ReviewVerdict.ERROR

        raw_findings = out.get("findings", [])
        findings = [ReviewFinding(**f) if isinstance(f, dict) else f for f in raw_findings]

        result = ReviewResult(
            verdict=verdict,
            summary=out.get("summary", last_record.result.error_message),
            findings=findings,
        )
    else:
        result = ReviewResult(
            verdict=ReviewVerdict.ERROR,
            summary="Review failed: pipeline did not produce a valid result.",
        )

    _display_review_result(result)


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
        _core.console.print(f"\n{result.summary}")

    if result.findings:
        _core.console.print(f"\n[bold]Findings ({len(result.findings)}):[/bold]")
        for f in result.findings:
            _core.console.print(f"  - {f.message}")

    if result.verdict in (ReviewVerdict.DENIED, ReviewVerdict.ERROR):
        raise typer.Exit(code=1)
