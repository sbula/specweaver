# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Shared helper functions used across CLI submodules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer
from rich.table import Table

from specweaver.interfaces.cli import _core

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.graph.topology import TopologyContext, TopologyGraph
    from specweaver.assurance.validation.models import RuleResult
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
    from specweaver.infrastructure.llm.models import GenerationConfig

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


def _require_llm_adapter(
    project_path: Path,
    *,
    llm_role: str = "draft",
) -> tuple[SpecWeaverSettings, GeminiAdapter, GenerationConfig]:
    """Create and validate an LLM adapter from project settings.

    Thin CLI wrapper around :func:`specweaver.infrastructure.llm.factory.create_llm_adapter`.
    Translates :class:`LLMAdapterError` into ``typer.Exit(1)``.
    """
    from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter

    db = _core.get_db()
    project = db.get_active_project()
    try:
        return create_llm_adapter(
            db,
            llm_role=llm_role,
            telemetry_project=project,
        )
    except LLMAdapterError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _load_topology(project_path: Path) -> TopologyGraph | None:
    """Try to load the project's topology graph from context.yaml files.

    Returns ``None`` (with a dim console note) if no context.yaml files
    are found -- this keeps all LLM commands usable without context.
    """
    from specweaver.assurance.graph.topology import TopologyGraph
    from specweaver.graph.topology.engine import TopologyEngine

    engine = TopologyEngine()
    graph = TopologyGraph.from_project(project_path, engine, auto_infer=False)
    if not graph.nodes:
        _core.console.print(
            "[dim]No context.yaml files found -- topology context disabled.[/dim]",
        )
        return None
    _core.console.print(
        f"[dim]Loaded topology: {len(graph.nodes)} modules.[/dim]",
    )
    return graph


# Selector name -> class mapping (configurable via --selector)
_SELECTOR_MAP: dict[str, type] = {}


def _get_selector_map() -> dict[str, type]:
    """Lazily populate and return the selector name->class mapping."""
    if not _SELECTOR_MAP:
        from specweaver.assurance.graph.selectors import (
            ConstraintOnlySelector,
            DirectNeighborSelector,
            ImpactWeightedSelector,
            NHopConstraintSelector,
        )

        _SELECTOR_MAP.update(
            {
                "direct": DirectNeighborSelector,
                "nhop": NHopConstraintSelector,
                "constraint": ConstraintOnlySelector,
                "impact": ImpactWeightedSelector,
            }
        )
    return _SELECTOR_MAP


def _select_topology_contexts(
    graph: TopologyGraph | None,
    module_name: str,
    *,
    selector_name: str = "direct",
) -> list[TopologyContext] | None:
    """Run a selector and return topology contexts, or None.

    Args:
        graph: The topology graph (None = no topology).
        module_name: Target module name (typically derived from spec/file stem).
        selector_name: One of 'direct', 'nhop', 'constraint', 'impact'.

    Returns:
        List of TopologyContext, or None if no graph or no related modules.
    """
    if graph is None:
        return None

    selector_map = _get_selector_map()
    selector_cls = selector_map.get(selector_name)
    if selector_cls is None:
        _core.console.print(
            f"[yellow]Warning:[/yellow] Unknown selector '{selector_name}', "
            "falling back to 'direct'.",
        )
        from specweaver.assurance.graph.selectors import DirectNeighborSelector

        selector_cls = DirectNeighborSelector

    selector = selector_cls()
    related = selector.select(graph, module_name)
    if not related:
        return None

    contexts = graph.format_context_summary(module_name, related)
    _core.console.print(
        f"[dim]Topology: {len(contexts)} related module(s) via {selector_name} selector.[/dim]",
    )
    return contexts


def _load_constitution_content(
    project_path: Path,
    spec_path: Path | None = None,
) -> str | None:
    """Load constitution content for the given project, or None."""
    from specweaver.workspace.project.constitution import find_constitution

    info = find_constitution(project_path, spec_path=spec_path)
    return info.content if info else None


def _load_standards_content(
    project_path: Path,
    target_path: Path | None = None,
    *,
    max_chars: int = 2000,
) -> str | None:
    """Load formatted standards from DB for prompt injection, or None.

    Thin CLI wrapper around :func:`specweaver.assurance.standards.loader.load_standards_content`.
    """
    from specweaver.assurance.standards.loader import load_standards_content

    db = _core.get_db()
    active = db.get_active_project()
    if not active:
        return None

    return load_standards_content(
        db,
        active,
        project_path,
        target_path=target_path,
        max_chars=max_chars,
    )
