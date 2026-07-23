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
    from specweaver.telemetry_logger import setup_logging

    # db = _core.get_db()
    active = _core.run_repo_op(lambda r: r.get_active_project())
    if active:
        try:
            level = _core.run_repo_op(lambda r: r.get_log_level(active))
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

def _stdin_isatty() -> bool:
    """Patchable indirection for the interactivity check (the TTY knowledge lives here,
    in the delivery layer — core's channel seam is terminal-agnostic)."""
    import sys

    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _interactive_context_provider() -> object | None:
    """INT-US-02 SF-02 (FR-4/FR-5): the delivery-layer interaction-channel factory.

    Returns an HITLProvider only on an interactive stdin; None otherwise, so headless
    runs keep the draft-parking contract byte-identical.
    """
    if not _stdin_isatty():
        return None
    from specweaver.interfaces.cli.hitl_provider import HITLProvider

    return HITLProvider(console=console)


try:
    from specweaver.core.flow.interfaces.cli import flow_cli, set_context_provider_factory

    set_context_provider_factory(_interactive_context_provider)
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
