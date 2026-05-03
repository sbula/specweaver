# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Shared helper functions used across CLI submodules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer

from specweaver.interfaces.cli import _core


def _run_workspace_op(method_name: str, *args: Any, **kwargs: Any) -> Any:
    import anyio

    from specweaver.workspace.store import WorkspaceRepository

    db = _core.get_db()

    async def _action() -> Any:
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args, **kwargs)

    return anyio.run(_action)


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.graph.topology import TopologyContext, TopologyGraph
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
    from specweaver.infrastructure.llm.models import GenerationConfig

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
    from specweaver.interfaces.cli.settings_loader import load_settings

    db = _core.get_db()
    project = _run_workspace_op("get_active_project")

    try:
        settings = load_settings(db, project, llm_role=llm_role)
        return create_llm_adapter(
            settings,
            telemetry_project=project,
        )
    except LLMAdapterError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        logger.warning("DB profile failed, using hardcoded fallback: %s", exc)
        from specweaver.core.config.settings import SpecWeaverSettings

        settings = SpecWeaverSettings(
            llm={"provider": "gemini", "model": "gemini-3-flash-preview", "api_key": "test-key"}
        )
        try:
            return create_llm_adapter(
                settings,
                telemetry_project=project,
            )
        except LLMAdapterError as inner_exc:
            _core.console.print(f"[red]Error:[/red] {inner_exc}")
            raise typer.Exit(code=1) from inner_exc


def _load_topology(project_path: Path) -> TopologyGraph | None:
    from specweaver.graph.interfaces.cli import _load_topology as _actual
    return _actual(project_path)


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
    active = _run_workspace_op("get_active_project")
    if not active:
        return None

    return load_standards_content(
        db,
        active,
        project_path,
        target_path=target_path,
        max_chars=max_chars,
    )
