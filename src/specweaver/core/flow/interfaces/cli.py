# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for pipeline execution: pipelines, run, resume."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from specweaver.assurance.graph.loader import load_topology, select_topology_contexts
from specweaver.assurance.standards.loader import load_standards_content
from specweaver.core.config.paths import state_db_path
from specweaver.core.flow.handlers.run_context import AnalysisContext, GuidanceContent, RunContext
from specweaver.core.flow.interfaces.resume_policy import guard_resumable, print_resume_hint
from specweaver.core.flow.interfaces.spec_path_resolution import resolve_spec_path
from specweaver.interfaces.cli import _core
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.project.constitution import find_constitution
from specweaver.workspace.project.discovery import resolve_project_path

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from specweaver.core.config.database import Database
    from specweaver.core.flow.engine.display import JsonPipelineDisplay, RichPipelineDisplay
    from specweaver.core.flow.engine.store import StateStore

    PipelineDisplay = JsonPipelineDisplay | RichPipelineDisplay


# ---------------------------------------------------------------------------
# The generic context-provider channel seam. The delivery layer registers a factory here; core
# stays terminal-agnostic — the factory owns the interactivity decision and may return None (e.g.
# no TTY). Future channels register through this same seam, and core adds NO delivery-layer imports
# for it.
# ---------------------------------------------------------------------------

_context_provider_factory: Callable[[], Any] | None = None


def set_context_provider_factory(factory: Callable[[], Any] | None) -> None:
    """Register (or clear, with None) the interaction-channel factory.

    Called by the delivery layer at composition time. The factory is invoked per run
    and may return None to signal "not interactive right now".
    """
    global _context_provider_factory
    _context_provider_factory = factory


def _maybe_attach_provider(context: RunContext) -> None:
    """Attach a context provider from the registered factory — best-effort, never breaks a run.

    A caller-supplied provider always wins (the factory is not consulted); a factory
    failure or a None return leaves the context untouched (headless park semantics, FR-5).
    """
    if _context_provider_factory is None or context.context_provider is not None:
        return
    try:
        provider = _context_provider_factory()
    except Exception:  # a channel failure must never break a run
        logger.debug("context-provider factory failed; continuing without one", exc_info=True)
        return
    if provider is not None:
        context.context_provider = provider


def _get_state_store() -> StateStore:
    """Get the pipeline state store (lazy import)."""
    from specweaver.core.flow.engine.store import StateStore

    return StateStore(state_db_path())


def _wire_llm(context: RunContext, pipeline_name: str, project_path: Path) -> None:
    """Wire context.model.llm for non-validate-only pipelines — shared by run AND
    resume. A resume that skips this silently degrades every resumed LLM step to
    "LLM not configured"."""
    if pipeline_name == "validate_only":
        return
    try:
        from specweaver.core.config.bootstrap.settings_loader import load_settings
        from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter

        settings = load_settings(_core.get_db(), project_path.name)
        _, adapter, _gen_config = create_llm_adapter(settings, telemetry_project=project_path.name)
        context.model = context.model.model_copy(update={"llm": adapter})
    except (LLMAdapterError, ValueError):
        _core.console.print(
            "[yellow]Warning:[/yellow] No LLM configured. LLM-dependent steps will fail.",
        )


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
        # Fallback only. `_execute_run` handles the interrupt where `runner.current_run_id` is
        # reachable and exits 130 itself, so this fires only for an interrupt BEFORE the run exists
        # (argument resolution, pipeline loading). There is no id to give then — and no run to
        # resume — so it points at how to find one instead of printing the unfollowable
        # "Resume with: sw run --resume" that used to be here.
        print_resume_hint(None)
        raise typer.Exit(code=130) from None
    except typer.Exit:
        # Intentional exits (e.g. PARKED -> Exit(code=0), "not an error, just parked") must pass
        # through untouched — click's Exit is a RuntimeError subclass, so the generic handler below
        # would otherwise swallow it and convert every parked run into a bogus "Error: Exit:" with
        # exit code 1.
        raise
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


def _build_run_context(project_path: Path, spec_path: Path, pipeline_name: str) -> RunContext:
    """The fully-wired `RunContext` a run or a resume starts from.

    Shared by `_execute_run` and `resume` — constitution, standards, interaction provider,
    isolation policy, model router, LLM wiring. As two copies it is forty lines where the entry
    points can drift into giving a run and its resume different execution postures.
    """
    from specweaver.core.config.bootstrap.settings_loader import load_settings
    from specweaver.infrastructure.llm.router import ModelRouter

    info = find_constitution(project_path, spec_path=spec_path)
    active = _core.run_repo_op(lambda r: r.get_active_project())
    db = _core.get_db()

    context = RunContext(
        analysis=AnalysisContext(analyzer_factory=AnalyzerFactory),
        project_path=project_path,
        spec_path=spec_path,
        output_dir=project_path / "src",
        db=db,
        guidance=GuidanceContent(
            constitution=info.content if info else None,
            standards=(
                load_standards_content(db, active, project_path, target_path=spec_path)
                if active
                else None
            ),
        ),
    )

    # Attach the registered interaction channel, if any —
    # the delivery-layer factory decides interactivity (returns None when headless, so
    # DraftSpecHandler's parking contract is untouched without a TTY).
    _maybe_attach_provider(context)
    _apply_isolation_policy(context, db, project_path)

    context.model = context.model.model_copy(
        update={
            "llm_router": ModelRouter(
                settings_provider=lambda role: load_settings(
                    _core.get_db(), project_path.name, llm_role=role
                ),
                telemetry_project=project_path.name,
            )
        }
    )
    _wire_llm(context, pipeline_name, project_path)
    return context


def _apply_isolation_policy(context: RunContext, db: Database, project_path: Path) -> None:
    """Resolve the worktree-isolation policies at the composition root (ADR-002).

    Both the per-step policy (``enforce_isolation``) and the per-run one (``session_isolation`` +
    ``allowed_paths``). Deliberately does NOT populate ``context.model.config``: that would also
    expose ``[sandbox] execution_mode`` and incidentally activate container QA on this path.

    **Best-effort by contract:** a settings-resolution failure must never crash a run, so the
    policies fall back to their defaults (off).
    """
    from specweaver.core.config.bootstrap.settings_loader import load_settings
    from specweaver.core.flow.engine.isolation import apply_isolation_policy

    try:
        settings = load_settings(db, project_path.name)
    except Exception:  # settings resolution is best-effort here — never crash a run
        logger.debug(
            "Could not resolve settings for project '%s'; worktree isolation "
            "policy will use its default (off).",
            project_path.name,
        )
        return
    apply_isolation_policy(context, settings, logger)


def _finish_run(final_run: Any, project_path: Path, *, warn_on_console: bool) -> None:
    """Save the staleness cache on success, then translate the run status into an exit code.

    Shared by `_execute_run` and `resume`, which differ in one respect that is preserved rather
    than smoothed over: `resume` logs a cache-save failure without printing it, so
    `warn_on_console` says which caller is which.

    `PARKED` exits 0 explicitly. Falling through would too, but a parked run is a routine outcome
    rather than an absence of one, and saying so keeps the three statuses side by side.
    """
    from specweaver.core.flow.engine.state import RunStatus

    if final_run.status == RunStatus.COMPLETED:
        from specweaver.assurance.graph.hasher import DependencyHasher

        try:
            DependencyHasher(project_path, AnalyzerFactory).save_cache()
            logger.info("Pipeline completed successfully, saved staleness topology cache.")
            _core.console.print("[dim]Topology staleness cache saved successfully.[/dim]")
        except Exception as e:
            logger.warning(f"Failed to save staleness cache: {e}")
            if warn_on_console:
                _core.console.print(f"[yellow]Failed to save staleness cache: {e}[/yellow]")

    if final_run.status == RunStatus.FAILED:
        raise typer.Exit(code=1)
    if final_run.status == RunStatus.PARKED:
        raise typer.Exit(code=0)  # Not an error, just parked


def _execute_run(
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
    spec_path = resolve_spec_path(pipeline_def.name, spec_or_module, project_path)

    # For pipelines that need an existing spec, check it exists
    spec_must_exist = pipeline_def.name not in ("new_feature",)
    if spec_must_exist and not spec_path.exists():
        _core.console.print(f"[red]Error:[/red] Spec file not found: {spec_path}")
        raise typer.Exit(code=1)

    # Build display backend
    display = _create_display(use_json=json_output, verbose=verbose)

    context = _build_run_context(project_path, spec_path, pipeline_def.name)

    # Load topology
    topo_graph = load_topology(project_path)
    if topo_graph:
        module_name = spec_path.stem.removesuffix("_spec")
        topo_contexts = select_topology_contexts(
            topo_graph,
            module_name,
            selector_name=selector,
        )
        context.graph = context.graph.model_copy(update={"topology": topo_contexts})

    # Set up state store
    store = _get_state_store()

    # Build runner with display as event callback
    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=display,
    )

    if resume_id is not None:
        guard_resumable(store, resume_id)

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
    except KeyboardInterrupt:
        # Handled HERE, not in the caller's `except KeyboardInterrupt`. By the time the caller sees
        # it, `_execute_run` has already raised and the run id is gone with the frame, so the
        # message would name `sw run --resume` with nothing to resume. The runner's own `finally:`
        # has already saved handover, so the id is real.
        display.stop()
        print_resume_hint(runner.current_run_id)
        raise typer.Exit(code=130) from None
    except Exception:
        display.stop()
        raise
    finally:
        display.stop()

    # Exit code based on final status

    _finish_run(final_run, project_path, warn_on_console=True)


def _resolve_resumable_run(store: StateStore, run_id: str | None) -> Any:
    """The run `sw resume` should continue: the one named, or the newest resumable one.

    Exits 1 when a named run or the active project is missing, and **0** when auto-detection
    simply finds nothing — having no parked run is not a failure.
    """
    if run_id is not None:
        run_state = store.load_run(run_id)
        if run_state is None:
            _core.console.print(f"[red]Error:[/red] Run '{run_id}' not found.")
            raise typer.Exit(code=1)
        return run_state

    name = _core._require_active_project()
    _core.get_db()
    if not _core.run_repo_op(lambda r: r.get_project(name)):
        _core.console.print(f"[red]Error:[/red] Project '{name}' not found.")
        raise typer.Exit(code=1)

    # Ask the store, do not reconstruct the answer from `list_bundled_pipelines()`. Such a loop
    # cannot see a run of a pipeline given to `sw run` as a YAML path, and returns the first bundled
    # name with a resumable run rather than the newest run.
    candidate = store.get_latest_resumable_run(name)
    if candidate is not None:
        return candidate

    _core.console.print("[dim]No resumable runs found for the active project.[/dim]")
    raise typer.Exit(code=0)


@flow_cli.command(name="resume")
def resume(
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

    store = _get_state_store()
    run_state = _resolve_resumable_run(store, run_id)

    _core.console.print(
        f"[bold]Resuming[/bold] run [cyan]{run_state.run_id[:8]}...[/cyan] "
        f"(pipeline: {run_state.pipeline_name}, "
        f"step {run_state.current_step + 1}/{len(run_state.step_records)})",
    )

    # Load the pipeline definition
    pipeline_def = load_pipeline(Path(run_state.pipeline_name))

    project_path = resolve_project_path(None)
    spec_path = Path(run_state.spec_path)
    context = _build_run_context(project_path, spec_path, pipeline_def.name)

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

    _finish_run(final_run, project_path, warn_on_console=False)
