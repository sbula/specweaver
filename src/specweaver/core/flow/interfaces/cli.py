# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for pipeline execution: pipelines, run, resume."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from specweaver.assurance.standards.interfaces.cli import _load_standards_content
from specweaver.core.config.paths import state_db_path
from specweaver.core.flow.handlers.base import RunContext
from specweaver.graph.interfaces.cli import (
    _load_topology,
    _select_topology_contexts,
)
from specweaver.infrastructure.llm.interfaces.cli import _require_llm_adapter
from specweaver.interfaces.cli import _core
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.project.discovery import resolve_project_path
from specweaver.workspace.project.interfaces.cli import (
    _load_constitution_content,
    _run_workspace_op,
)

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from specweaver.core.flow.engine.display import JsonPipelineDisplay, RichPipelineDisplay
    from specweaver.core.flow.engine.store import StateStore

    PipelineDisplay = JsonPipelineDisplay | RichPipelineDisplay


def _get_state_store() -> StateStore:
    """Get the pipeline state store (lazy import)."""
    from specweaver.core.flow.engine.store import StateStore

    return StateStore(state_db_path())


def _resolve_spec_path(
    pipeline_name: str,
    spec_or_module: str,
    project_path: Path,
) -> Path:
    """Resolve the spec argument based on pipeline type.

    For validate-style pipelines:  treat as direct file path.
    For new_feature-style:         treat as module name, derive spec path.
    """
    # If it looks like an existing file, use it directly
    spec_path = Path(spec_or_module)
    if spec_path.exists():
        return spec_path

    # For new_feature pipelines, derive from module name
    if pipeline_name == "new_feature":
        derived = project_path / "specs" / f"{spec_or_module}_spec.md"
        return derived

    # Try relative to project
    relative = project_path / spec_or_module
    if relative.exists():
        return relative

    # Fall back to the literal path (will fail later with clear message)
    return spec_path


def _create_display(
    *,
    use_json: bool = False,
    verbose: bool = False,
) -> PipelineDisplay:
    """Create the appropriate display backend."""
    if use_json:
        from specweaver.core.flow.engine.display import JsonPipelineDisplay

        return JsonPipelineDisplay()

    from specweaver.core.flow.engine.display import RichPipelineDisplay

    return RichPipelineDisplay(console=_core.console, verbose=verbose)


flow_cli = typer.Typer(no_args_is_help=True)

@flow_cli.command(name="pipelines")
def pipelines() -> None:
    """List available pipeline templates."""
    from specweaver.core.flow.engine.parser import list_bundled_pipelines

    bundled = list_bundled_pipelines()
    if not bundled:
        _core.console.print("[dim]No pipeline templates found.[/dim]")
        return

    from rich.table import Table

    table = Table(title="Available Pipelines")
    table.add_column("Name", style="cyan bold")
    table.add_column("Source", style="dim")

    for name in bundled:
        table.add_row(name, "bundled")

    _core.console.print(table)
    _core.console.print(
        "\n[dim]Usage: sw run <pipeline> <spec_or_module>[/dim]",
    )


@flow_cli.command(name="run")
def run_pipeline(
    pipeline: str = typer.Argument(
        help="Pipeline name or YAML path (e.g. 'new_feature', 'validate_only').",
    ),
    spec_or_module: str = typer.Argument(
        help="Spec file path or module name (depends on pipeline type).",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    resume: str | None = typer.Option(
        None,
        "--resume",
        help="Resume a run by ID (or omit value for latest).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed handler output.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output NDJSON event stream (machine-readable).",
    ),
    selector: str = typer.Option(
        "direct",
        "--selector",
        help="Topology selector: direct, nhop, constraint, impact.",
    ),
) -> None:
    """Run a pipeline against a spec file or module.

    Load a pipeline definition and execute it step-by-step.
    Shows live progress with checkmarks for each step.

    Examples:
        sw run validate_only specs/calculator.md
        sw run new_feature greet_service
        sw run validate_only specs/calculator.md --verbose
        sw run validate_only specs/calculator.md --json
    """
    try:
        _execute_run(
            pipeline=pipeline,
            spec_or_module=spec_or_module,
            project=project,
            resume_id=resume,
            verbose=verbose,
            json_output=json_output,
            selector=selector,
        )
    except KeyboardInterrupt:
        _core.console.print(
            "\n[yellow]Interrupted.[/yellow] "
            "[dim]Run state saved. Resume with: sw run --resume[/dim]",
        )
        raise typer.Exit(code=130) from None
    except FileNotFoundError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        if verbose:
            import traceback

            _core.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        if verbose:
            import traceback

            _core.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1) from None
    except Exception as exc:
        _core.console.print(
            f"[red]Error:[/red] {type(exc).__name__}: {exc}\n"
            "[dim]Run with --verbose for full traceback.[/dim]",
        )
        if verbose:
            import traceback

            _core.console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1) from None


def _execute_run(  # noqa: C901
    *,
    pipeline: str,
    spec_or_module: str,
    project: str | None,
    resume_id: str | None,
    verbose: bool,
    json_output: bool,
    selector: str,
) -> None:
    """Core run logic -- separated for testability."""
    from specweaver.core.flow.engine.parser import load_pipeline
    from specweaver.core.flow.engine.runner import PipelineRunner

    # Resolve project path
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Load pipeline definition
    pipeline_def = load_pipeline(Path(pipeline))

    # Resolve spec path based on pipeline type
    spec_path = _resolve_spec_path(pipeline_def.name, spec_or_module, project_path)

    # For pipelines that need an existing spec, check it exists
    spec_must_exist = pipeline_def.name not in ("new_feature",)
    if spec_must_exist and not spec_path.exists():
        _core.console.print(f"[red]Error:[/red] Spec file not found: {spec_path}")
        raise typer.Exit(code=1)

    # Build display backend
    display = _create_display(use_json=json_output, verbose=verbose)

    # Build run context
    from specweaver.infrastructure.llm.router import ModelRouter

    context = RunContext(
        analyzer_factory=AnalyzerFactory,
        project_path=project_path,
        spec_path=spec_path,
        output_dir=project_path / "src",
        constitution=_load_constitution_content(
            project_path,
            spec_path=spec_path,
        ),
        standards=_load_standards_content(project_path, target_path=spec_path),
        db=_core.get_db(),
    )

    from specweaver.core.config.settings_loader import load_settings

    context.llm_router = ModelRouter(
        settings_provider=lambda role: load_settings(
            _core.get_db(), project_path.name, llm_role=role
        ),
        telemetry_project=project_path.name,
    )

    # Wire up LLM if needed (non-validate-only pipelines)
    if pipeline_def.name != "validate_only":
        try:
            _, adapter, _gen_config = _require_llm_adapter(project_path)
            context.llm = adapter
        except (typer.Exit, SystemExit):
            if pipeline_def.name != "validate_only":
                _core.console.print(
                    "[yellow]Warning:[/yellow] No LLM configured. LLM-dependent steps will fail.",
                )

    # Load topology
    topo_graph = _load_topology(project_path)
    if topo_graph:
        module_name = spec_path.stem.removesuffix("_spec")
        topo_contexts = _select_topology_contexts(
            topo_graph,
            module_name,
            selector_name=selector,
        )
        context.topology = topo_contexts

    # Set up state store
    store = _get_state_store()

    # Build runner with display as event callback
    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=display,
    )

    # Initialize display
    step_info = [(step.name, step.description or "") for step in pipeline_def.steps]
    display.start(pipeline_def.name, step_info)

    try:
        if resume_id is not None:
            # Resume mode
            final_run = asyncio.run(runner.resume(resume_id))
        else:
            # Fresh run
            final_run = asyncio.run(runner.run())
    except Exception:
        display.stop()
        raise
    finally:
        display.stop()

    # Exit code based on final status
    from specweaver.core.flow.engine.state import RunStatus

    if final_run.status == RunStatus.COMPLETED:
        from specweaver.assurance.graph.hasher import DependencyHasher

        try:
            DependencyHasher(project_path, AnalyzerFactory).save_cache()
            logger.info("Pipeline completed successfully, saved staleness topology cache.")
            _core.console.print("[dim]Topology staleness cache saved successfully.[/dim]")
        except Exception as e:
            logger.warning(f"Failed to save staleness cache: {e}")
            _core.console.print(f"[yellow]Failed to save staleness cache: {e}[/yellow]")

    if final_run.status == RunStatus.FAILED:
        raise typer.Exit(code=1)
    if final_run.status == RunStatus.PARKED:
        raise typer.Exit(code=0)  # Not an error, just parked


@flow_cli.command(name="resume")
def resume(  # noqa: C901
    run_id: str | None = typer.Argument(
        None,
        help="Run ID to resume. If omitted, resumes the latest parked/failed run.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed handler output.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output NDJSON event stream (machine-readable).",
    ),
) -> None:
    """Resume a parked or failed pipeline run.

    If no run ID is given, finds the latest resumable run
    for the active project.

    Examples:
        sw resume
        sw resume abc12345-...
    """
    from specweaver.core.flow.engine.parser import load_pipeline
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.state import RunStatus

    store = _get_state_store()

    if run_id is not None:
        # Explicit run ID
        run_state = store.load_run(run_id)
        if run_state is None:
            _core.console.print(f"[red]Error:[/red] Run '{run_id}' not found.")
            raise typer.Exit(code=1)
    else:
        # Auto-detect: find latest resumable run for active project
        name = _core._require_active_project()
        db = _core.get_db()
        proj = _run_workspace_op("get_project", name)
        if not proj:
            _core.console.print(f"[red]Error:[/red] Project '{name}' not found.")
            raise typer.Exit(code=1)

        # Try common pipeline names
        from specweaver.core.flow.engine.parser import list_bundled_pipelines

        run_state = None
        for pipeline_name in list_bundled_pipelines():
            candidate = store.get_latest_run(name, pipeline_name)
            if candidate and candidate.status in (RunStatus.PARKED, RunStatus.FAILED):
                run_state = candidate
                break

        if run_state is None:
            _core.console.print(
                "[dim]No resumable runs found for the active project.[/dim]",
            )
            raise typer.Exit(code=0)

    _core.console.print(
        f"[bold]Resuming[/bold] run [cyan]{run_state.run_id[:8]}...[/cyan] "
        f"(pipeline: {run_state.pipeline_name}, "
        f"step {run_state.current_step + 1}/{len(run_state.step_records)})",
    )

    # Load the pipeline definition
    pipeline_def = load_pipeline(Path(run_state.pipeline_name))

    # Build context from stored state
    from specweaver.infrastructure.llm.router import ModelRouter

    project_path = resolve_project_path(None)
    spec_path = Path(run_state.spec_path)

    context = RunContext(
        analyzer_factory=AnalyzerFactory,
        project_path=project_path,
        spec_path=spec_path,
        output_dir=project_path / "src",
        constitution=_load_constitution_content(
            project_path,
            spec_path=spec_path,
        ),
        standards=_load_standards_content(project_path, target_path=spec_path),
        db=_core.get_db(),
    )

    from specweaver.core.config.settings_loader import load_settings

    context.llm_router = ModelRouter(
        settings_provider=lambda role: load_settings(
            _core.get_db(), project_path.name, llm_role=role
        ),
        telemetry_project=project_path.name,
    )

    display = _create_display(use_json=json_output, verbose=verbose)

    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=display,
    )

    step_info = [(step.name, step.description or "") for step in pipeline_def.steps]
    display.start(pipeline_def.name, step_info)

    try:
        final_run = asyncio.run(runner.resume(run_state.run_id))
    except KeyboardInterrupt:
        display.stop()
        _core.console.print(
            f"\n[yellow]Interrupted.[/yellow] [dim]Resume with: sw resume {run_state.run_id}[/dim]",
        )
        raise typer.Exit(code=130) from None
    except Exception:
        display.stop()
        raise
    finally:
        display.stop()

    if final_run.status == RunStatus.COMPLETED:
        from specweaver.assurance.graph.hasher import DependencyHasher

        try:
            DependencyHasher(project_path, AnalyzerFactory).save_cache()
            logger.info("Pipeline completed successfully, saved staleness topology cache.")
            _core.console.print("[dim]Topology staleness cache saved successfully.[/dim]")
        except Exception as e:
            logger.warning(f"Failed to save staleness cache: {e}")

    if final_run.status == RunStatus.FAILED:
        raise typer.Exit(code=1)
