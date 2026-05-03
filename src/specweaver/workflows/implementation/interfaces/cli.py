# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command for code generation: implement."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from specweaver.assurance.standards.interfaces.cli import _load_standards_content
from specweaver.graph.interfaces.cli import (
    _load_topology,
    _select_topology_contexts,
)
from specweaver.infrastructure.llm.interfaces.cli import _require_llm_adapter
from specweaver.interfaces.cli import _core
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.project.discovery import resolve_project_path
from specweaver.workspace.project.interfaces.cli import _load_constitution_content

logger = logging.getLogger(__name__)


implement_cli = typer.Typer(no_args_is_help=True)


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
    spec_path = Path(spec)
    if not spec_path.exists():
        _core.console.print(f"[red]Error:[/red] Spec not found: {spec}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.core.flow.engine.models import (
        PipelineDefinition,
        PipelineStep,
        StepAction,
        StepTarget,
    )
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.state import StepStatus
    from specweaver.core.flow.handlers.base import RunContext

    settings, adapter, _ = _require_llm_adapter(project_path)
    if settings and getattr(settings, "llm", None):
        settings.llm.temperature = 0.2  # Low temperature for code

    # Load topology context for the implementation target
    topo_graph = _load_topology(project_path)
    module_name = spec_path.stem.removesuffix("_spec")
    topo_contexts = _select_topology_contexts(
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

    # Load constitution for this project
    constitution_content = _load_constitution_content(
        project_path,
        spec_path=spec_path,
    )
    standards_content = _load_standards_content(project_path, target_path=spec_path)

    pipeline = PipelineDefinition(
        name="implement_spec",
        description=f"Implement spec {spec_path.name}",
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
        ],
    )

    context = RunContext(
        analyzer_factory=AnalyzerFactory,
        project_path=project_path,
        spec_path=spec_path,
        llm=adapter,
        config=settings,
        topology=topo_contexts,
        constitution=constitution_content,
        standards=standards_content,
        db=_core.get_db(),
    )

    _core.console.print("[dim]Executing implementation pipeline...[/dim]")
    runner = PipelineRunner(pipeline, context)
    run_state = asyncio.run(runner.run())

    if run_state.status != "completed":
        _core.console.print("[red]Pipeline failed or parked.[/red]")
        raise typer.Exit(code=1)

    for record in run_state.step_records:
        if record.status == StepStatus.PASSED and record.result:
            generated_path = record.result.output.get("generated_path")
            if generated_path:
                _core.console.print(f"  [green]\u2713[/green] {generated_path}")
        else:
            _core.console.print(f"  [red]\u2717[/red] Failed step: {record.step_name}")

    _core.console.print(
        "\n[green]Implementation complete![/green]\n"
        "[dim]Next steps:\n"
        "  sw check --level=code <generated_file>\n"
        "  sw review <generated_file> --spec <spec_file>[/dim]",
    )
