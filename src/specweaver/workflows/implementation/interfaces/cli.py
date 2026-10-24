# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command for code generation: implement."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from collections.abc import Callable


logger = logging.getLogger(__name__)


implement_cli = typer.Typer(no_args_is_help=True)


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
    if out.get("note"):
        _core.console.print(f"  - code validation: {out['note']}", markup=False)
        return
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


def _report_acceptance(_mark: str, _name: str, out: dict[str, Any]) -> None:
    from specweaver.core.flow.handlers.acceptance import acceptance_lines

    for line in acceptance_lines(out.get("acceptance") or {}):
        _core.console.print(line)


#: Which step names get a bespoke line. Anything absent falls back to "report it only if it
#: failed" — a table rather than an `elif` chain, so adding a step is one entry rather than a
#: branch in what would otherwise be the longest function in this package.
_STEP_REPORTERS: dict[str, Callable[[str, str, dict[str, Any]], None]] = {
    "generate_code": _report_generated,
    "generate_tests": _report_generated,
    "run_tests": _report_tests,
    "lint_fix": _report_lint,
    "validate_code": _report_code_validation,
    "acceptance": _report_acceptance,
}


def _print_framework(project_path: Path, code_path: Path, language: str) -> None:
    """The framework the prompts follow, and where it was found; nothing when there is none."""
    from specweaver.core.flow.engine.frameworks import project_framework

    try:
        framework = project_framework(project_path, code_path, language)
    except ValueError as exc:
        _core.print_error(exc)
        raise typer.Exit(code=1) from exc
    if framework is not None:
        _core.console.print(f"  Framework: {framework.key} ({framework.source})", markup=False)
    _core.console.print()


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
    model: str | None = typer.Option(
        None,
        "--model",
        help=(
            "model@server for every step of this run only, but not the scenario agent's; "
            "the settings files stay unchanged."
        ),
    ),
) -> None:
    """Generate code + tests from a validated, reviewed spec.

    Reads a validated spec and uses the LLM to generate:
    - Implementation source file in src/
    - Test file in tests/
    """
    logger.debug("Executing implement command")
    from specweaver.infrastructure.llm.interfaces.command import run_model_option

    run_model = run_model_option(model)
    spec_path = Path(spec)
    if not spec_path.exists():
        _core.console.print(f"[red]Error:[/red] Spec not found: {spec}")
        raise typer.Exit(code=1)

    project_path = _core.project_path_or_exit(project)

    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.session import SessionWorktreeError
    from specweaver.interfaces.cli.run_doors import build_run_or_exit, refuse_unstarted_worktree

    _doc_policy, _autonomy, language = _core.project_sections_at(project_path)

    # Derive output paths from spec name
    # e.g., "greet_service_spec.md" -> "greet_service.py"
    from specweaver.core.flow.engine.task_files import task_files_for

    try:
        task = task_files_for(project_path, spec_path, language)
    except ValueError as exc:
        _core.print_error(exc)
        raise typer.Exit(code=1) from exc
    code_path = project_path / task.code
    test_path = project_path / task.tests

    from specweaver.core.flow.engine.parser import load_bundled_pipeline

    pipeline = load_bundled_pipeline("implement_spec")
    context = build_run_or_exit(
        project_path, spec_path, pipeline, selector=selector, run_model=run_model
    )

    _core.console.print(
        f"\n[bold]Implementing:[/bold] {spec_path.name}",
    )
    _core.console.print(f"  [dim]Code:[/dim]  {code_path}\n  [dim]Tests:[/dim] {test_path}")
    _print_framework(project_path, code_path, task.language)

    _core.console.print("[dim]Executing implementation pipeline...[/dim]")
    runner = PipelineRunner(pipeline, context, memory_task=True)
    try:
        run_state = asyncio.run(runner.run())
    except SessionWorktreeError as err:
        refuse_unstarted_worktree(err)

    _report_implementation(run_state)

    # Exit reflects QA outcome. A failed run_tests exhausts its
    # loop-back and leaves the run non-completed \u2192 exit 1. A failed validate_code
    # is report-only (CONTINUE gate) and does not, on its own, fail the command.
    if run_state.status == "parked":
        reason = run_state.step_records[run_state.current_step].result
        _core.console.print("\nStopped by the spend brake:", style="red")
        _core.console.print(reason.error_message if reason else "", markup=False)
        _core.console.print("Raise the limit in settings.toml and run sw implement again.")
        raise typer.Exit(code=1)
    if run_state.status != "completed":
        _core.console.print("\n[red]Implementation failed:[/red] tests did not pass.")
        raise typer.Exit(code=1)

    _core.console.print("\n[green]Implementation complete![/green]")
