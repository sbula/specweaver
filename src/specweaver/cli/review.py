# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for LLM review: draft, review."""

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

    from specweaver.context.hitl_provider import HITLProvider
    from specweaver.drafting.drafter import Drafter

    _, adapter, gen_config = _helpers._require_llm_adapter(project_path)

    drafter = Drafter(
        llm=adapter,
        context_provider=HITLProvider(console=_core.console),
        config=gen_config,
    )

    # Load topology context for the new component (best-effort)
    topo_graph = _load_topology(project_path)
    topo_contexts = _select_topology_contexts(
        topo_graph, name, selector_name=selector,
    )

    _core.console.print(
        f"\n[bold]Drafting spec for[/bold] [cyan]{name}[/cyan]\n"
        "[dim]Answer questions below. Press Enter to skip.[/dim]\n",
    )

    result_path = asyncio.run(
        drafter.draft(name, specs_dir, topology_contexts=topo_contexts),
    )

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

    from specweaver.review.reviewer import Reviewer

    _, adapter, gen_config = _helpers._require_llm_adapter(project_path)
    gen_config.temperature = 0.3  # Lower for reviews

    reviewer = Reviewer(llm=adapter, config=gen_config)

    # Load topology context for the review target
    topo_graph = _load_topology(project_path)
    module_name = target_path.stem.removesuffix("_spec")
    topo_contexts = _select_topology_contexts(
        topo_graph, module_name, selector_name=selector,
    )

    _core.console.print(f"\n[bold]Reviewing:[/bold] {target_path.name}")
    _core.console.print("[dim]Sending to LLM for semantic review...[/dim]\n")

    result = _execute_review(
        reviewer, target_path, spec, topo_contexts,
        constitution=_load_constitution_content(
            project_path, spec_path=target_path,
        ),
        standards=_load_standards_content(project_path, target_path=target_path),
    )
    _display_review_result(result)


def _execute_review(
    reviewer: object,
    target_path: Path,
    spec: str | None,
    topology_contexts: list | None = None,
    *,
    constitution: str | None = None,
    standards: str | None = None,
) -> object:
    """Run the appropriate review (spec or code)."""
    from specweaver.review.reviewer import ReviewResult, ReviewVerdict

    if spec:
        spec_path = Path(spec)
        if not spec_path.exists():
            _core.console.print(f"[red]Error:[/red] Spec not found: {spec}")
            raise typer.Exit(code=1)
        try:
            return asyncio.run(
                reviewer.review_code(
                    target_path, spec_path,
                    topology_contexts=topology_contexts,
                    constitution=constitution,
                    standards=standards,
                ),
            )
        except Exception as exc:
            return ReviewResult(
                verdict=ReviewVerdict.ERROR,
                summary=f"Review failed: {exc}",
            )
    try:
        return asyncio.run(
            reviewer.review_spec(
                target_path,
                topology_contexts=topology_contexts,
                constitution=constitution,
                standards=standards,
            ),
        )
    except Exception as exc:
        return ReviewResult(
            verdict=ReviewVerdict.ERROR,
            summary=f"Review failed: {exc}",
        )


def _display_review_result(result: object) -> None:
    """Display review verdict and findings."""
    from specweaver.review.reviewer import ReviewVerdict

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
