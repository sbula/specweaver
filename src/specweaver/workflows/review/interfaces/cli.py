# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for LLM review: draft, review."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.markup import escape

from specweaver.assurance.graph.loader import load_topology, select_topology_contexts
from specweaver.assurance.standards.loader import load_standards_content
from specweaver.interfaces.cli import _core
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.project.constitution import find_constitution
from specweaver.workspace.project.discovery import resolve_project_path

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.workflows.review.reviewer import ReviewResult


review_cli = typer.Typer(no_args_is_help=True)


def _build_draft_pipeline(name: str) -> PipelineDefinition:
    """INT-US-02 SF-01 (FR-1/FR-2/FR-3): draft -> validate -> review in ONE pipeline —
    no manual handoff. Review rejection loops back into a REAL re-draft (AD-6a
    feedback-aware handler), bounded at max_retries=2."""
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
    """INT-US-02 SF-01 (FR-6): inline outcome report — the whole chain's result from one
    command; the old "run 'sw check' manually" handoff is gone by design."""
    from specweaver.core.flow.engine.state import StepStatus

    records = {r.step_name: r for r in (run_state.step_records or [])}

    def _output(step_name: str) -> dict[str, Any]:
        rec = records.get(step_name)
        result = getattr(rec, "result", None) if rec else None
        output = getattr(result, "output", None) if result else None
        return output if isinstance(output, dict) else {}

    draft_out = _output("draft_spec")
    draft_rec = records.get("draft_spec")
    if draft_rec is not None and draft_rec.status == StepStatus.PASSED:
        _core.console.print(f"\n[green]Spec drafted:[/green] {draft_out.get('path', spec_path)}")

    validate_out = _output("validate_spec")
    if validate_out:
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

    review_out = _output("review_spec")
    if review_out:
        verdict = str(review_out.get("verdict", "unknown"))
        findings = review_out.get("findings") or []
        _core.console.print(f"Review: {verdict}")
        if verdict != "accepted":
            _core.console.print("[red]Review rejected (re-draft retries exhausted).[/red]")
            for finding in findings:
                text = finding.get("message", finding) if isinstance(finding, dict) else finding
                _core.console.print(f"  [red]-[/red] {escape(str(text))}")


@review_cli.command(name="draft")
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

    from specweaver.core.config.settings_loader import load_settings
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.state import RunStatus
    from specweaver.core.flow.handlers.base import RunContext
    from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter
    from specweaver.interfaces.cli.hitl_provider import HITLProvider

    db = _core.get_db()
    project = _core.run_repo_op(lambda r: r.get_active_project())
    try:
        settings = load_settings(db, project, llm_role="draft")  # type: ignore[arg-type]
        settings, adapter, _ = create_llm_adapter(settings, telemetry_project=project)
    except LLMAdapterError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] LLM configuration failed: {exc}")
        raise typer.Exit(code=1) from exc

    # Load topology context for the new component (best-effort)
    topo_graph = load_topology(project_path)
    topo_contexts = select_topology_contexts(
        topo_graph,
        name,
        selector_name=selector,
    )

    _core.console.print(
        f"\n[bold]Drafting spec for[/bold] [cyan]{name}[/cyan]\n"
        "[dim]Answer questions below. Press Enter to skip.[/dim]\n",
    )

    pipeline = _build_draft_pipeline(name)

    context = RunContext(
        analyzer_factory=AnalyzerFactory,
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

    _report_draft_chain(run_state, spec_path)

    if run_state.status != RunStatus.COMPLETED:
        raise typer.Exit(code=1)


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
    target_path = Path(target)
    if not target_path.exists():
        _core.console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.core.config.settings_loader import load_settings
    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.handlers.base import RunContext
    from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter

    db = _core.get_db()
    project = _core.run_repo_op(lambda r: r.get_active_project())
    try:
        settings = load_settings(db, project)  # type: ignore[arg-type]
        settings, adapter, _ = create_llm_adapter(settings, telemetry_project=project)
    except LLMAdapterError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] LLM configuration failed: {exc}")
        raise typer.Exit(code=1) from exc
    if settings and getattr(settings, "llm", None):
        settings.llm.temperature = 0.3  # Lower for reviews

    # Load topology context for the review target
    topo_graph = load_topology(project_path)
    module_name = target_path.stem.removesuffix("_spec")
    topo_contexts = select_topology_contexts(
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
        analyzer_factory=AnalyzerFactory,
        project_path=project_path,
        spec_path=actual_spec_path,
        llm=adapter,
        config=settings,
        topology=topo_contexts,
        constitution=(lambda info: info.content if info else None)(
            find_constitution(project_path, spec_path=actual_spec_path)
        ),
        standards=(
            load_standards_content(db, project, project_path, target_path=target_path)
            if project
            else None
        ),
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
        # escape(): LLM-authored text — stray [/tags] would raise MarkupError.
        _core.console.print(f"\n{escape(result.summary)}")

    if result.findings:
        _core.console.print(f"\n[bold]Findings ({len(result.findings)}):[/bold]")
        for f in result.findings:
            _core.console.print(f"  - {escape(f.message)}")

    if result.verdict in (ReviewVerdict.DENIED, ReviewVerdict.ERROR):
        raise typer.Exit(code=1)
