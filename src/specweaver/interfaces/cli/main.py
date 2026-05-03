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
from specweaver.interfaces.cli._helpers import _run_workspace_op


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


from specweaver.interfaces.cli import (  # noqa: E402, F401
    _helpers,
    constitution,
    hooks,
    implement,
    pipelines,
    projects,
    review,
)

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
    from specweaver.assurance.validation.interfaces import cli as validation_cli  # noqa: F401
except ImportError as e:
    console.print(f"[bold red]Failed to load validation plugin:[/bold red] {e}")

try:
    from specweaver.assurance.standards.interfaces import cli as standards_cli  # noqa: F401
except ImportError as e:
    console.print(f"[bold red]Failed to load standards plugin:[/bold red] {e}")

try:
    from specweaver.infrastructure.llm.interfaces import cli as llm_cli  # noqa: F401
except ImportError as e:
    console.print(f"[bold red]Failed to load llm plugin:[/bold red] {e}")

if __name__ == "__main__":
    app()
