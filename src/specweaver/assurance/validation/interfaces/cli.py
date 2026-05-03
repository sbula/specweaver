# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for validation and AST drift detection."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.table import Table

from specweaver.interfaces.cli import _core
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.project.discovery import resolve_project_path
from specweaver.workspace.project.interfaces.cli import _run_workspace_op

if TYPE_CHECKING:
    from specweaver.assurance.validation.models import RuleResult
    from specweaver.core.flow.engine.state import StepResult

logger = logging.getLogger(__name__)

# Status display mapping (shared across check command)
_STATUS_STYLE = {
    "pass": "[green]PASS[/green]",
    "fail": "[red]FAIL[/red]",
    "warn": "[yellow]WARN[/yellow]",
    "skip": "[dim]SKIP[/dim]",
}


def _display_results(
    results: list[RuleResult],
    title: str,
) -> None:
    """Display validation results as a Rich table with findings."""
    from specweaver.assurance.validation.models import Status

    table = Table(title=title)
    table.add_column("Rule", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    for r in results:
        table.add_row(
            r.rule_id,
            r.rule_name,
            _STATUS_STYLE.get(r.status.value, str(r.status)),
            r.message[:80] if r.message else "",
        )
    _core.console.print(table)

    # Show detailed findings for failed/warned rules
    for r in results:
        if r.findings and r.status in (Status.FAIL, Status.WARN):
            _core.console.print(
                f"\n[bold]{r.rule_id} {r.rule_name}[/bold] findings:",
            )
            for f in r.findings:
                line_info = f" (line {f.line})" if f.line else ""
                _core.console.print(
                    f"  [{f.severity.value}] {f.message}{line_info}",
                )
                if f.suggestion:
                    _core.console.print(f"    [dim]-> {f.suggestion}[/dim]")


def _print_summary(results: list[RuleResult], *, strict: bool = False) -> None:
    """Print pass/fail summary and raise Exit(1) on failures.

    Args:
        results: Validation results to summarize.
        strict: If True, WARNs also cause exit code 1.
    """
    from specweaver.assurance.validation.models import Status

    fail_count = sum(1 for r in results if r.status == Status.FAIL)
    warn_count = sum(1 for r in results if r.status == Status.WARN)

    if fail_count > 0:
        _core.console.print(
            f"\n[red]FAILED[/red]: {fail_count} rule(s) failed, {warn_count} warning(s)",
        )
        raise typer.Exit(code=1)
    if warn_count > 0:
        _core.console.print(
            f"\n[yellow]PASSED with warnings[/yellow]: {warn_count} warning(s)",
        )
        if strict:
            raise typer.Exit(code=1)
    else:
        _core.console.print("\n[green]ALL PASSED[/green]")



def _resolve_pipeline_name(
    level: str,
    pipeline: str | None,
    active_project: str | None = None,
) -> str:
    """Resolve the YAML pipeline name from --pipeline, --level, or active profile.

    Thin CLI wrapper around
    :func:`specweaver.assurance.validation.pipeline_loader.resolve_pipeline_name`.
    Translates :class:`ValueError` into ``typer.Exit(1)``.
    """
    import contextlib

    from specweaver.assurance.validation.pipeline_loader import resolve_pipeline_name

    active_profile = None
    if active_project:
        with contextlib.suppress(ValueError, Exception):
            active_profile = _run_workspace_op("get_domain_profile", active_project)

    try:
        return resolve_pipeline_name(
            level,
            pipeline,
            active_profile=active_profile,
        )
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _build_result_label(level: str, pipeline: str | None, pipeline_name: str) -> str:
    """Return a human-readable label for the validation result output."""
    if pipeline:
        return pipeline_name
    if level == "feature":
        return "Feature"
    if level == "code":
        return "Code"
    return "Spec"


validation_cli = typer.Typer(no_args_is_help=True)

@validation_cli.command(name="check")
def check(
    target: str = typer.Argument(
        "",
        help="Path to the spec or code file to check. Optional if using --lineage.",
    ),
    level: str = typer.Option(
        "component",
        "--level",
        "-l",
        help=(
            "Validation level: feature (spec, feature thresholds), "
            "component (spec, default thresholds), or code."
        ),
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warnings as failures (exit code 1).",
    ),
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        help="Name of the validation pipeline to use (e.g. validation_spec_library).",
    ),
    lineage: bool = typer.Option(
        False,
        "--lineage",
        help="Run a scan over the project's source tree to detect files missing lineage tags (orphans).",
    ),
) -> None:
    """Run validation rules against a spec or code file.

    Uses --level to determine which rule set to apply:
    - feature: Spec validation rules S01-S11 with feature-level thresholds
    - component: Spec validation rules S01-S11 with component-level thresholds (default)
    - code: Code validation rules C01-C08

    Use --pipeline to choose a specific validation pipeline by name.

    Override cascade is strictly pipeline YAML defaults -> applied pipeline configurations.
    """
    # Trigger auto-registration of built-in rules
    import specweaver.assurance.validation.rules.code
    import specweaver.assurance.validation.rules.spec  # noqa: F401
    from specweaver.assurance.validation.executor import execute_validation_pipeline
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

    if lineage:
        from specweaver.graph.interfaces.cli import check_lineage

        _core.get_db()
        active = _run_workspace_op("get_active_project")

        if project:
            proj_path = Path(project)
        elif active:
            proj_data = _run_workspace_op("get_project", active)
            proj_path = Path(str(proj_data["root_path"])) if proj_data else Path.cwd()
        else:
            proj_path = Path.cwd()

        src_dir = proj_path / "src"

        orphans = check_lineage(src_dir)
        if orphans:
            _core.console.print("[red]Lineage Tracking Error:[/red] Missing '# sw-artifact:' tags.")
            for orphan in orphans:
                _core.console.print(f"  - {orphan}")
            raise typer.Exit(code=1)

        _core.console.print("[green]Lineage scan passed.[/green] All files correctly tagged.")
        return

    target_path = Path(target)
    if not target or not target_path.exists():
        _core.console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    try:
        content = target_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _core.console.print(
            f"[red]Error:[/red] Cannot read '{target}': file is not valid UTF-8 text.",
        )
        raise typer.Exit(code=1) from None

    from specweaver.workspace.project.discovery import resolve_project_path

    _core.get_db()
    # Ensure project resolution handles implicit CWD and active project logic
    try:
        project_dir: Path | None = resolve_project_path(project)
    except Exception:
        # Fallback to None if not inside a valid project
        project_dir = Path(project) if project else None

    # Determine active project for profile-aware pipeline selection
    active = _run_workspace_op("get_active_project")
    pipeline_name = _resolve_pipeline_name(level, pipeline, active_project=active)

    try:
        resolved = load_pipeline_yaml(pipeline_name, project_dir=project_dir)
    except FileNotFoundError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.core.config.dal_resolver import DALResolver

    project_root = project_dir or Path.cwd()
    dal_resolver = DALResolver(project_root)
    dal_level = dal_resolver.resolve(target_path)
    effective_strict = strict or (dal_level.is_strict if dal_level else False)

    results = execute_validation_pipeline(resolved, content, target_path)

    label = _build_result_label(level, pipeline, pipeline_name)
    dal_str = dal_level.value if dal_level else "Unbound"
    _display_results(results, f"{label} Validation: {target_path.name} (DAL: {dal_str})")
    _print_summary(results, strict=effective_strict)


@validation_cli.command("list-rules")
def list_rules(
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        help="Show rules for a specific pipeline only.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory (for project pipelines).",
    ),
) -> None:
    """List all validation rules, grouped by pipeline in execution order."""
    # Trigger auto-registration
    import specweaver.assurance.validation.rules.code
    import specweaver.assurance.validation.rules.spec  # noqa: F401
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

    project_dir = Path(project) if project else None

    # Determine which pipelines to show
    if pipeline:
        pipeline_names = [pipeline]
    else:
        pipeline_names = ["validation_spec_default", "validation_code_default"]

    for pname in pipeline_names:
        try:
            resolved = load_pipeline_yaml(pname, project_dir=project_dir)
        except FileNotFoundError:
            _core.console.print(f"[yellow]Pipeline '{pname}' not found, skipping.[/yellow]")
            continue

        _core.console.print(f"\n[bold cyan]{resolved.name}[/bold cyan]", highlight=False)
        if resolved.description:
            _core.console.print(f"  [dim]{resolved.description.strip()}[/dim]")
        _core.console.print()

        for i, step in enumerate(resolved.steps, 1):
            params_str = ""
            if step.params:
                params_str = "  " + " ".join(f"[dim]{k}={v}[/dim]" for k, v in step.params.items())
            _core.console.print(f"  {i:>2}. [green]{step.rule}[/green]  {step.name}{params_str}")

        _core.console.print(f"\n  [dim]{len(resolved.steps)} rules total[/dim]")


drift_app = typer.Typer(
    name="drift",
    help="AST Drift detection engine operations.",
    no_args_is_help=True,
)
validation_cli.add_typer(drift_app, name="drift")


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

    context = RunContext(
        analyzer_factory=AnalyzerFactory,
        project_path=project_path,
        spec_path=plan_path,
        db=_core.get_db(),
    )

    if analyze:
        from specweaver.infrastructure.llm.interfaces.cli import _require_llm_adapter
        _, adapter, _ = _require_llm_adapter(project_path)
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

        context = RunContext(
            analyzer_factory=AnalyzerFactory,
            project_path=project_path,
            spec_path=matched_plan,
            db=_core.get_db(),
        )
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
