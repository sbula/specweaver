# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI command for code generation: implement."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from specweaver.cli import _core, _helpers
from specweaver.cli._helpers import (
    _load_constitution_content,
    _load_standards_content,
    _load_topology,
    _select_topology_contexts,
)
from specweaver.project.discovery import resolve_project_path


@_core.app.command()
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

    from specweaver.implementation.generator import Generator

    _, adapter, gen_config = _helpers._require_llm_adapter(project_path)
    gen_config.temperature = 0.2  # Low temperature for code

    generator = Generator(llm=adapter, config=gen_config)

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

    try:
        # Generate code
        _core.console.print("[dim]Generating implementation code...[/dim]")
        asyncio.run(
            generator.generate_code(
                spec_path,
                code_path,
                topology_contexts=topo_contexts,
                constitution=constitution_content,
                standards=standards_content,
            ),
        )
        _core.console.print(f"  [green]\u2713[/green] {code_path}")

        # Generate tests
        _core.console.print("[dim]Generating test file...[/dim]")
        asyncio.run(
            generator.generate_tests(
                spec_path,
                test_path,
                topology_contexts=topo_contexts,
                constitution=constitution_content,
                standards=standards_content,
            ),
        )
        _core.console.print(f"  [green]\u2713[/green] {test_path}")
    finally:
        from specweaver.llm.collector import TelemetryCollector

        if isinstance(adapter, TelemetryCollector):
            adapter.flush(_core.get_db())

    _core.console.print(
        "\n[green]Implementation complete![/green]\n"
        "[dim]Next steps:\n"
        "  sw check --level=code <generated_file>\n"
        "  sw review <generated_file> --spec <spec_file>[/dim]",
    )
