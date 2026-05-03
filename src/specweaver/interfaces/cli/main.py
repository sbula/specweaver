# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SpecWeaver CLI — Typer application.

Entry point registered as ``sw`` in pyproject.toml.

Commands are spread across submodules; this ``__init__`` creates the
shared ``app`` / ``console`` instances and imports every submodule so
that commands self-register.
"""

from __future__ import annotations

# App callback (uses shared objects)
import typer

from specweaver.interfaces.cli._core import (  # noqa: F401
    _require_active_project,
    _version_callback,
    app,
    console,
    logger,
)
from specweaver.workspace.project.interfaces.cli import _run_workspace_op


@app.callback()
def _app_callback(
    *,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """SpecWeaver \u2014 Specification-driven development lifecycle tool."""
    from specweaver.interfaces.cli import _core
    from specweaver.logging import setup_logging
    db = _core.get_db()
    active = _run_workspace_op("get_active_project")
    if active:
        try:
            import anyio

            from specweaver.workspace.store import WorkspaceRepository

            async def _get_level() -> str:
                async with db.async_session_scope() as session:
                    return await WorkspaceRepository(session).get_log_level(active)

            level = anyio.run(_get_level)
        except (ValueError, Exception):
            level = "DEBUG"
    else:
        level = "DEBUG"

    setup_logging(project_name=active, level=level)
    logger.debug("CLI invoked \u2014 active project: %s", active or "(none)")


# ---------------------------------------------------------------------------
# Import submodules so their commands auto-register on ``app``
# ---------------------------------------------------------------------------


try:
    from specweaver.core.config.interfaces.cli import config_app
    app.add_typer(config_app, name="config")
except ImportError as e:
    console.print(f"[bold red]Failed to load config plugin:[/bold red] {e}")

try:
    from specweaver.graph.interfaces.cli import graph_app, lineage_app
    app.add_typer(graph_app, name="graph")
    app.add_typer(lineage_app, name="lineage")
except ImportError as e:
    console.print(f"[bold red]Failed to load graph plugin:[/bold red] {e}")

try:
    from specweaver.assurance.validation.interfaces.cli import validation_cli
    app.add_typer(validation_cli)
except ImportError as e:
    console.print(f"[bold red]Failed to load validation plugin:[/bold red] {e}")

try:
    from specweaver.assurance.standards.interfaces.cli import standards_app
    app.add_typer(standards_app, name="standards")
except ImportError as e:
    console.print(f"[bold red]Failed to load standards plugin:[/bold red] {e}")

try:
    from specweaver.infrastructure.llm.interfaces.cli import costs_app, usage_app
    app.add_typer(costs_app, name="costs")
    app.add_typer(usage_app, name="usage")
except ImportError as e:
    console.print(f"[bold red]Failed to load llm plugin:[/bold red] {e}")

try:
    from specweaver.workflows.implementation.interfaces.cli import implement_cli
    app.add_typer(implement_cli)
except ImportError as e:
    console.print(f"[bold red]Failed to load implementation workflow plugin:[/bold red] {e}")

try:
    from specweaver.workflows.review.interfaces.cli import review_cli
    app.add_typer(review_cli)
except ImportError as e:
    console.print(f"[bold red]Failed to load review workflow plugin:[/bold red] {e}")

try:
    from specweaver.workspace.project.interfaces.cli import workspace_cli
    app.add_typer(workspace_cli)
except ImportError as e:
    console.print(f"[bold red]Failed to load workspace project plugin:[/bold red] {e}")

try:
    from specweaver.core.flow.interfaces.cli import flow_cli
    app.add_typer(flow_cli)
except ImportError as e:
    console.print(f"[bold red]Failed to load flow pipelines plugin:[/bold red] {e}")

try:
    from specweaver.interfaces.cli.routers.serve_router import serve_cli
    app.add_typer(serve_cli)
except ImportError as e:
    console.print(f"[bold red]Failed to load serve router:[/bold red] {e}")

if __name__ == "__main__":
    app()
