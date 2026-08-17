# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.tree import Tree

from specweaver.commons.lineage import extract_artifact_uuid
from specweaver.graph.lineage.engine import LineageEngine
from specweaver.graph.lineage.store.lineage_repository import LineageRepository
from specweaver.interfaces.cli import _core
from specweaver.interfaces.cli._core import console, get_db

logger = logging.getLogger(__name__)


# -- Graph App --------------------------------------------------------------

graph_app = typer.Typer(
    name="graph",
    help="Manage the Knowledge Graph.",
    no_args_is_help=True,
)


@graph_app.command()
def build(
    target: Annotated[
        str,
        typer.Argument(
            help="Path to a file or directory to ingest into the Knowledge Graph.",
        ),
    ],
    project_path: Annotated[
        Path,
        typer.Option(
            "--project-path",
            "-p",
            help="Path to the root of the project.",
        ),
    ] = Path("."),
) -> None:
    """
    Builds the semantic Knowledge Graph for the specified target.
    Extracts the AST, hashes it, and persists it to the local SQLite database.
    """
    try:
        from specweaver.graph.core.builder.orchestrator import GraphOrchestrator

        count = GraphOrchestrator.build_target(Path(target), project_path)
        console.print(f"[green]Successfully built graph for {target} ({count} files)[/green]")
    except Exception as e:
        console.print(f"[red]Failed to build graph: {e}[/red]")
        sys.exit(1)


# -- Lineage App ------------------------------------------------------------

lineage_app = typer.Typer(
    name="lineage",
    help="Manage and verify artifact lineage metadata.",
    no_args_is_help=True,
)


def _resolve_target_uuid(target: str) -> str:
    """The lineage UUID `target` names — read from the file when it is one, else `target` itself.

    Resolution is language-aware, matching whatever `wrap_artifact_tag` emits rather than only
    `"# sw-artifact: "` at line start — every spec `draft.py` writes carries
    `<!-- sw-artifact: … -->`, so a hash-comment-only match resolves nothing and passes the path
    string on as a UUID.
    """
    path = Path(target)
    try:
        if not path.is_file():
            return target
        return extract_artifact_uuid(path.read_text(encoding="utf-8")) or target
    except OSError:
        return target


def _require_active_project() -> None:
    """Exit 1 unless an active project is set and still resolvable. Written out twice."""
    active = _core.run_repo_op(lambda r: r.get_active_project())
    if not active:
        typer.secho("No active project. Run 'sw project set <name>' first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not _core.run_repo_op(lambda r: r.get_project(active)):
        typer.secho("Active project not found in global database.", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _add_lineage_nodes(node_data: dict[str, Any], parent_tree: Tree, target_uuid: str) -> None:
    """Render one lineage node and its children onto `parent_tree`."""
    if node_data["circular"]:
        parent_tree.add(f"[red]Circular reference: {node_data['id']}[/red]")
        return

    node_uid = node_data["id"]
    events = ", ".join(f"{h['event_type']}:{h['model_id']}" for h in node_data["history"])
    name = f"[bold green]{node_uid}[/bold green]" if node_uid == target_uuid else node_uid

    node = parent_tree.add(f"📄 {name} [dim]({events})[/dim]")
    for child in node_data["children"]:
        _add_lineage_nodes(child, node, target_uuid)


@lineage_app.command("tag")
def tag(
    target: Annotated[Path, typer.Argument(help="Python file to tag")],
    author: Annotated[
        str, typer.Option("--author", help="Author of the artifact or manual edit")
    ] = "human",
) -> None:
    """Add a missing lineage tag to a file, or log a manual edit if tagged."""
    if not target.exists() or not target.is_file():
        typer.secho(f"File {target} does not exist.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    content_lines = target.read_text(encoding="utf-8").splitlines()
    existing_uuid = extract_artifact_uuid("\n".join(content_lines))

    if existing_uuid:
        target_uuid = existing_uuid
        rprint(
            f"[yellow]File already tagged with {target_uuid}. Logging manual edit event.[/yellow]"
        )
    else:
        target_uuid = str(uuid.uuid4())
        if content_lines and content_lines[0].startswith("#!"):
            content_lines.insert(1, f"# sw-artifact: {target_uuid}")
        else:
            content_lines.insert(0, f"# sw-artifact: {target_uuid}")
        target.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
        rprint(f"[green]Added tag {target_uuid} to {target}[/green]")

    get_db()
    _require_active_project()

    from specweaver.core.config.paths import config_db_path

    db_path = config_db_path()
    repo = LineageRepository(str(db_path))

    repo.log_artifact_event(
        artifact_id=target_uuid,
        parent_id=None,
        run_id="manual",
        event_type="manual_tag",
        model_id=author,
    )


@lineage_app.command("tree")
def tree_command(
    target: Annotated[str, typer.Argument(help="UUID or file path to trace")],
) -> None:
    """Recursively traces up and down the artifact lineage DB to display a rich tree."""
    target_uuid = _resolve_target_uuid(target)

    get_db()
    _require_active_project()

    from specweaver.core.config.paths import config_db_path

    engine = LineageEngine(LineageRepository(str(config_db_path())))
    root_uuid = engine.find_root(target_uuid)

    tree = Tree(f"[bold blue]Lineage Graph (Root: {root_uuid})[/bold blue]")
    _add_lineage_nodes(engine.build_tree(root_uuid), tree, target_uuid)
    console.print(tree)
