# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SpecWeaver CLI — Typer application.

Entry point registered as ``sw`` in pyproject.toml.

Commands are spread across submodules; this ``__init__`` creates the
shared ``app`` / ``console`` instances and imports every submodule so
that commands self-register.
"""

from __future__ import annotations

# App callback (uses shared objects)
import typer

from specweaver.cli._core import (  # noqa: F401
    _require_active_project,
    _version_callback,
    app,
    console,
    get_db,
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
    from specweaver.logging import setup_logging

    db = get_db()
    active = db.get_active_project()
    if active:
        try:
            level = db.get_log_level(active)
        except (ValueError, Exception):
            level = "DEBUG"
    else:
        level = "DEBUG"

    setup_logging(project_name=active, level=level)
    logger.debug("CLI invoked \u2014 active project: %s", active or "(none)")


# ---------------------------------------------------------------------------
# Import submodules so their commands auto-register on ``app``
# ---------------------------------------------------------------------------
from specweaver.cli import (  # noqa: E402, F401
    _helpers,
    config,
    constitution,
    implement,
    pipelines,
    projects,
    review,
    standards,
    validation,
)

# ---------------------------------------------------------------------------
# Backward-compatible re-exports so ``from specweaver.cli import X`` works
# ---------------------------------------------------------------------------
from specweaver.cli._helpers import (  # noqa: E402, F401
    _display_results,
    _get_selector_map,
    _load_constitution_content,
    _load_standards_content,
    _load_topology,
    _print_summary,
    _require_llm_adapter,
    _select_topology_contexts,
)
from specweaver.cli.pipelines import (  # noqa: E402, F401
    _create_display,
    _resolve_spec_path,
)
