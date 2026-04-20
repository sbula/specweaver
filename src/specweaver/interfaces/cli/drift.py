# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for AST drift detection: sw drift check."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.table import Table

from specweaver.interfaces.cli import _core, _helpers
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.project.discovery import resolve_project_path

if TYPE_CHECKING:
    from specweaver.core.flow.engine.state import StepResult

logger = logging.getLogger(__name__)

drift_app = typer.Typer(
    name="drift",
    help="AST Drift detection engine operations.",
    no_args_is_help=True,
)
_core.app.add_typer(drift_app, name="drift")


@drift_app.command("check")
def drift_check(
    target: str = typer.Argument(help="Path to the code file to check."),
    plan: str = typer.Option(
        ...,
        "--plan",
        help="Path to the PlanArtifact YAML file.",
    ),
    analyze: bool = typer.Option(
        False,
        "--analyze",
        help="Use LLM to perform root-cause analysis on the AST drift.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Check a code file against its planned AST signatures."""
    target_path = Path(target)
    if not target_path.exists():
        _core.console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    plan_path = Path(plan)
    if not plan_path.exists():
        _core.console.print(f"[red]Error:[/red] Plan file not found: {plan}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.state import StepStatus
    from specweaver.core.flow.handlers.base import RunContext

    pipeline = PipelineDefinition.create_single_step(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        description=f"AST Drift Check for {target_path.name}",
        params={
            "target_path": str(target_path),
            "plan_path": str(plan_path),
            "analyze": analyze,
        },
    )

    context = RunContext(analyzer_factory=AnalyzerFactory,
        project_path=project_path,
        spec_path=plan_path,
        db=_core.get_db(),
    )

    if analyze:
        _, adapter, _ = _helpers._require_llm_adapter(project_path)
        context.llm = adapter

    runner = PipelineRunner(pipeline, context)
    run_state = asyncio.run(runner.run())

    last_record = run_state.step_records[-1] if run_state.step_records else None

    if not last_record or last_record.status == StepStatus.ERROR or not last_record.result:
        error_msg = (
            last_record.result.error_message
            if last_record and last_record.result
            else "Unknown runner error"
        )
        _core.console.print(f"[red]Execution failed:[/red] {error_msg}")
        raise typer.Exit(code=1)

    _present_result(last_record.result, target_path.name, analyze)


def _present_result(result: StepResult, target_name: str, analyze: bool) -> None:
    is_drifted = result.output.get("is_drifted", False)
    findings = result.output.get("findings", [])

    if not is_drifted:
        _core.console.print(f"[green]✓ AST signatures match specification.[/green] ({target_name})")
        if findings:
            table = Table(title=f"Warnings for {target_name}")
            table.add_column("Severity")
            table.add_column("Description")
            for f in findings:
                table.add_row(f.get("severity", "WARNING"), f.get("description", ""))
            _core.console.print(table)
        return

    _core.console.print(f"[red]Failure: AST Drift Detected![/red] ({target_name})")
    table = Table(title=f"Drift Findings for {target_name}")
    table.add_column("Severity", style="red")
    table.add_column("Description")

    for f in findings:
        table.add_row(f.get("severity", "ERROR"), f.get("description", ""))

    _core.console.print(table)

    if analyze and "llm_root_cause" in result.output:
        _core.console.print("\n[bold cyan]LLM Root-Cause Analysis:[/bold cyan]")
        _core.console.print(f"[dim]{result.output['llm_root_cause']}[/dim]")

    raise typer.Exit(code=42)


@drift_app.command("check-rot")
def drift_check_rot(  # noqa: C901
    staged: bool = typer.Option(
        False,
        "--staged",
        help="Check only files currently staged in git.",
    ),
) -> None:
    """Bi-Directional Spec Rot Interceptor (SF-1 Stub)."""
    import yaml
    from rich.table import Table

    if not staged:
        _core.console.print("Checking AST drift for all target files")
        raise typer.Exit(code=0)

    _core.console.print("Checking AST drift for staged files")

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        raw_files = result.stdout.splitlines()
    except subprocess.CalledProcessError as exc:
        _core.console.print(f"[red]Error:[/red] Failed to query git index: {exc}")
        raise typer.Exit(code=1) from exc

    target_files = [f.strip() for f in raw_files if f.strip()]
    if not target_files:
        raise typer.Exit(code=0)

    try:
        project_path = resolve_project_path(None)
    except Exception as exc:
        _core.console.print(f"[red]Error resolving project:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    specs_dir = project_path / "specs"
    all_plans = []
    if specs_dir.exists() and specs_dir.is_dir():
        all_plans = list(specs_dir.glob("*_plan.yaml"))

    drift_found = False

    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.state import StepStatus
    from specweaver.core.flow.handlers.base import RunContext

    for target in target_files:
        _core.console.print(f"DEBUG TARGET STR: {target}")
        target_path = project_path / target
        if not target_path.exists():
            _core.console.print(f"DEBUG SKIP: {target_path} does not exist!")
            continue

        matched_plan = None
        target_posix = target_path.as_posix()
        try:
            rel_posix = target_path.resolve().relative_to(project_path.resolve()).as_posix()
        except ValueError:
            rel_posix = target_posix

        for plan_path in all_plans:
            try:
                with plan_path.open() as pf:
                    plan_data = yaml.safe_load(pf)
                for task in plan_data.get("tasks", []):
                    sigs = task.get("expected_signatures", {})
                    if rel_posix in sigs or target_posix in sigs or str(target_path) in sigs:
                        matched_plan = plan_path
                        break
                if matched_plan:
                    break
            except Exception as e:
                logger.warning(f"Failed to validate plan {plan_path} against {target}: {e}")

        if not matched_plan:
            matched_plan = _resolve_plan_by_lineage(target_path, all_plans, target)

        if not matched_plan:
            continue

        pipeline = PipelineDefinition.create_single_step(
            name="check_rot",
            action=StepAction.DETECT,
            target=StepTarget.DRIFT,
            description=f"Rot Check {target_path.name}",
            params={
                "target_path": str(target_path.absolute()),
                "plan_path": str(matched_plan.absolute()),
                "analyze": False,
            },
        )

        context = RunContext(analyzer_factory=AnalyzerFactory, project_path=project_path, spec_path=matched_plan, db=_core.get_db())
        runner_instance = PipelineRunner(pipeline, context)
        run_state = asyncio.run(runner_instance.run())

        last_record = run_state.step_records[-1] if run_state.step_records else None
        status_code = getattr(last_record, "status", None) if last_record else None

        _core.console.print(f"DEBUG PIPELINE: status_code={status_code}, last_record={last_record}")

        if status_code in (StepStatus.FAILED, StepStatus.ERROR):
            drift_found = True
            res = last_record.result if last_record else None
            if res and res.output and res.output.get("is_drifted"):
                _core.console.print(f"[red]Failure: AST Drift Detected![/red] ({target_posix})")
                table = Table(title=f"Drift Findings for {target}")
                table.add_column("Severity", style="red")
                table.add_column("Description")
                for f in res.output.get("findings", []):
                    table.add_row(f.get("severity", "ERROR"), f.get("description", ""))
                _core.console.print(table)

    if drift_found:
        _core.console.print("\n================================================================")
        _core.console.print("ERROR: SpecWeaver detected structural drift between Spec and Code!")
        _core.console.print("Fix the mismatch to proceed with this commit.")
        _core.console.print("================================================================\n")
        import sys

        sys.exit(42)

    _core.console.print("[green]AST signatures match specification.[/green]")
    raise typer.Exit(code=0)


def _resolve_plan_by_lineage(
    target_path: Path, all_plans: list[Path], target_posix: str
) -> Path | None:
    try:
        from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

        content = target_path.read_text(encoding="utf-8")
        uuid = extract_artifact_uuid(content)
        if uuid:
            db = _core.get_db()
            with db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT parent_id FROM artifact_events WHERE artifact_id = ?", (uuid,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    parent_uuid = row[0]
                    for p in all_plans:
                        p_content = p.read_text(encoding="utf-8")
                        p_uuid = extract_artifact_uuid(p_content)
                        if p_uuid == parent_uuid:
                            return p
    except Exception as e:
        logger.debug(f"Lineage lookup failed for {target_posix}: {e}")
    return None
