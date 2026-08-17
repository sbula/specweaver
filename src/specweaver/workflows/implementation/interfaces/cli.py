# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command for code generation: implement."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from specweaver.assurance.graph.loader import load_topology, select_topology_contexts
from specweaver.assurance.standards.loader import load_standards_content
from specweaver.interfaces.cli import _core
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.project.constitution import find_constitution
from specweaver.workspace.project.discovery import resolve_project_path

if TYPE_CHECKING:
    from collections.abc import Callable

    from specweaver.core.flow.engine.models import PipelineDefinition

logger = logging.getLogger(__name__)


implement_cli = typer.Typer(no_args_is_help=True)


def _build_implement_pipeline(stem: str) -> PipelineDefinition:
    """Build the autonomous ``implement_spec`` pipeline.

    Generate code + tests, then run the tests and validate the code in one loop.
    The QA steps target this run's freshly generated files (``tests/test_<stem>.py``,
    ``src/<stem>.py``); ``run_tests`` loops back to regenerate on failure (bounded),
    and ``validate_code`` is report-only (a C01-C08 miss never aborts the run). QA
    steps leave ``use_worktree`` unset so SF-03 can thread the US-9 isolation policy
    without touching this builder.
    """
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
        name="implement_spec",
        description=f"Implement + QA for {stem}",
        steps=[
            PipelineStep(
                name="generate_code",
                action=StepAction.GENERATE,
                target=StepTarget.CODE,
            ),
            PipelineStep(
                name="generate_tests",
                action=StepAction.GENERATE,
                target=StepTarget.TESTS,
            ),
            # Auto-fix lint BEFORE running tests, so run_tests and
            # validate_code exercise the lint-fixed code. Report-only (CONTINUE):
            # remaining lint errors after reflections never abort the run.
            PipelineStep(
                name="lint_fix",
                action=StepAction.LINT_FIX,
                target=StepTarget.CODE,
                params={"target": f"src/{stem}.py", "max_reflections": 3},
                gate=GateDefinition(on_fail=OnFailAction.CONTINUE),
            ),
            PipelineStep(
                name="run_tests",
                action=StepAction.VALIDATE,
                target=StepTarget.TESTS,
                params={"target": f"tests/test_{stem}.py", "kind": "unit", "coverage": True},
                gate=GateDefinition(
                    type=GateType.AUTO,
                    condition=GateCondition.ALL_PASSED,
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="generate_code",
                    max_retries=2,
                ),
            ),
            PipelineStep(
                name="validate_code",
                action=StepAction.VALIDATE,
                target=StepTarget.CODE,
                params={"target": f"src/{stem}.py"},
                gate=GateDefinition(on_fail=OnFailAction.CONTINUE),
            ),
        ],
    )


def _report_implementation(run_state: object) -> None:
    """Print per-step results of the implement loop.

    Surfaces generated paths, test pass/fail + coverage, and code-validation
    rule outcomes inline so ``sw implement`` conveys the full autonomous result.
    """
    from specweaver.core.flow.engine.state import StepStatus

    for record in run_state.step_records:  # type: ignore[attr-defined]
        out = record.result.output if record.result else {}
        passed = record.status == StepStatus.PASSED
        mark = "[green]✓[/green]" if passed else "[red]✗[/red]"

        reporter = _STEP_REPORTERS.get(record.step_name)
        if reporter is not None:
            reporter(mark, record.step_name, out)
        elif not passed:
            _core.console.print(f"  {mark} {record.step_name}: {record.error_message or 'failed'}")


def _report_generated(mark: str, name: str, out: dict[str, Any]) -> None:
    generated_path = out.get("generated_path")
    if generated_path:
        _core.console.print(f"  {mark} {name}: {generated_path}")


def _report_tests(mark: str, _name: str, out: dict[str, Any]) -> None:
    line = f"  {mark} tests: {out.get('passed', 0)} passed, {out.get('failed', 0)} failed"
    coverage = out.get("coverage_pct")
    if coverage is not None:
        line += f", coverage {coverage}%"
    _core.console.print(line)


def _report_lint(mark: str, _name: str, out: dict[str, Any]) -> None:
    detail = (
        "auto-fixed" if out.get("auto_fixed") else f"{out.get('reflections_used', 0)} reflection(s)"
    )
    remaining = out.get("lint_errors_remaining", 0)
    _core.console.print(f"  {mark} lint: {detail}, {remaining} errors remaining")


def _report_code_validation(mark: str, _name: str, out: dict[str, Any]) -> None:
    _core.console.print(
        f"  {mark} code validation: {out.get('passed', 0)}/{out.get('total', 0)} rules passed"
    )
    failed_rules = [
        r.get("rule_id")
        for r in out.get("results", [])
        if str(r.get("status", "")).lower().startswith("fail")
    ]
    if failed_rules:
        _core.console.print(f"      [yellow]failed rules:[/yellow] {', '.join(failed_rules)}")


#: Which step names get a bespoke line. Anything absent falls back to "report it only if it
#: failed" — a table rather than an `elif` chain, so adding a step is one entry rather than a
#: branch in what would otherwise be the longest function in this package.
_STEP_REPORTERS: dict[str, Callable[[str, str, dict[str, Any]], None]] = {
    "generate_code": _report_generated,
    "generate_tests": _report_generated,
    "run_tests": _report_tests,
    "lint_fix": _report_lint,
    "validate_code": _report_code_validation,
}


@implement_cli.command(name="implement")
def implement(
    spec: str = typer.Argument(
        help="Path to the spec file to implement.",
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
    """Generate code + tests from a validated, reviewed spec.

    Reads a validated spec and uses the LLM to generate:
    - Implementation source file in src/
    - Test file in tests/
    """
    logger.debug("Executing implement command")
    spec_path = Path(spec)
    if not spec_path.exists():
        _core.console.print(f"[red]Error:[/red] Spec not found: {spec}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.core.config.bootstrap.settings_loader import load_settings
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.handlers.run_context import (
        AnalysisContext,
        GraphContext,
        GuidanceContent,
        ModelAccess,
        RunContext,
    )
    from specweaver.infrastructure.llm.factory import (
        LLMAdapterError,
        build_adapter_for_project,
    )

    db = _core.get_db()
    # Telemetry is attributed per active project, so a run that cannot be attributed cannot run —
    # and the refusal must name the missing project rather than surface a `load_settings` lookup
    # failure. The adapter is built through `build_adapter_for_project`, which is where
    # `cost_overrides` reaches a run.
    project = _core._require_active_project()
    try:
        settings = load_settings(db, project)
        settings, adapter = build_adapter_for_project(db, settings, project)
    except LLMAdapterError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] LLM configuration failed: {exc}")
        raise typer.Exit(code=1) from exc

    if settings and getattr(settings, "llm", None):
        settings.llm.temperature = 0.2  # Low temperature for code

    # Load topology context for the implementation target
    topo_graph = load_topology(project_path)
    module_name = spec_path.stem.removesuffix("_spec")
    topo_contexts = select_topology_contexts(
        topo_graph,
        module_name,
        selector_name=selector,
    )

    # Derive output paths from spec name
    # e.g., "greet_service_spec.md" -> "greet_service.py"
    stem = spec_path.stem.removesuffix("_spec")
    src_dir = project_path / "src"
    tests_dir = project_path / "tests"

    code_path = src_dir / f"{stem}.py"
    test_path = tests_dir / f"test_{stem}.py"

    _core.console.print(
        f"\n[bold]Implementing:[/bold] {spec_path.name}",
    )
    _core.console.print(
        f"  [dim]Code:[/dim]  {code_path}\n  [dim]Tests:[/dim] {test_path}\n",
    )

    constitution_info = find_constitution(project_path, spec_path=spec_path)
    constitution_content = constitution_info.content if constitution_info else None
    active = _core.run_repo_op(lambda r: r.get_active_project())
    standards_content = (
        load_standards_content(db, active, project_path, target_path=spec_path) if active else None
    )

    pipeline = _build_implement_pipeline(stem)

    context = RunContext(
        analysis=AnalysisContext(analyzer_factory=AnalyzerFactory),
        project_path=project_path,
        spec_path=spec_path,
        model=ModelAccess(llm=adapter, config=settings),
        graph=GraphContext(topology=topo_contexts),
        db=_core.get_db(),
        guidance=GuidanceContent(constitution=constitution_content, standards=standards_content),
    )

    # Run the autonomous (untrusted) implement loop
    # worktree-bounded when the risk warrants it. Opt into DAL-driven auto-escalation —
    # session isolation auto-enables for high-assurance (DAL_B+) code, while small/low-DAL
    # projects keep today's friction-free host behavior. Best-effort: never crashes the run.
    from specweaver.core.flow.engine.isolation import apply_session_policy

    apply_session_policy(context, settings, logger, dal_auto_escalate=True)

    _core.console.print("[dim]Executing implementation pipeline...[/dim]")
    runner = PipelineRunner(pipeline, context)
    run_state = asyncio.run(runner.run())

    _report_implementation(run_state)

    # Exit reflects QA outcome. A failed run_tests exhausts its
    # loop-back and leaves the run non-completed \u2192 exit 1. A failed validate_code
    # is report-only (CONTINUE gate) and does not, on its own, fail the command.
    if run_state.status != "completed":
        _core.console.print("\n[red]Implementation failed:[/red] tests did not pass.")
        raise typer.Exit(code=1)

    _core.console.print("\n[green]Implementation complete![/green]")
