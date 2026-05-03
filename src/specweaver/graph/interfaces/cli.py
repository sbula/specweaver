# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer
from rich import print as rprint
from rich.tree import Tree

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.store.repository import SqliteGraphRepository
from specweaver.graph.lineage.engine import LineageEngine
from specweaver.graph.lineage.store.lineage_repository import LineageRepository
from specweaver.interfaces.cli import _core
from specweaver.interfaces.cli._core import console, get_db
from specweaver.interfaces.cli._helpers import _run_workspace_op
from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from specweaver.assurance.graph.topology import TopologyGraph

logger = logging.getLogger(__name__)


def _load_topology(project_path: Path) -> "TopologyGraph | None":
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


# -- Graph App --------------------------------------------------------------

def _purge_stale_nodes(target_path: Path, repo: SqliteGraphRepository) -> None:
    """RT-11: Stale Graph Boot Trap - Cross-reference DB against disk and purge deleted files."""
    existing_files = repo.get_all_file_hashes()

    found_on_disk = set()
    if target_path.is_file():
        found_on_disk.add(str(target_path))
    elif target_path.is_dir():
        for filepath in target_path.rglob("*"):
            if filepath.is_file():
                found_on_disk.add(str(filepath))
    else:
        found_on_disk.add(str(target_path))

    for db_file in existing_files:
        if db_file not in found_on_disk and not Path(db_file).exists():
            console.print(f"[dim]Purging deleted file from Knowledge Graph: {db_file}[/dim]")
            repo.purge_file(db_file)


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
        # Dependency Injection (CB4 Wiring)
        engine = InMemoryGraphEngine()
        db_path = str(project_path / ".specweaver" / "graph.db")

        # RT-30: Validate local context.yaml against project
        service_name = "default"
        topology = _load_topology(project_path)
        if topology and topology.nodes:
            # Try to find a root node (level = system or similar)
            # Or just take the first one if it's a microservice
            for node in topology.nodes.values():
                if node.yaml_path and str(node.yaml_path.parent) == str(project_path.resolve()):
                    service_name = node.name
                    break

        repo = SqliteGraphRepository(db_path, service_name)

        # RT-11: Stale Graph Boot Trap
        target_path = Path(target)
        _purge_stale_nodes(target_path, repo)

        # Load any existing state AFTER purge
        graph, _ = repo.load_from_db()
        engine._graph = graph

        # Inject the workspace parser adapter with ID Prefixing
        builder = GraphBuilder(engine=engine, parser=extract_ast_dict, id_prefix=service_name)

        # Ingest the target
        if target_path.is_file():
            builder.ingest_file(str(target_path))
        elif target_path.is_dir():
            for filepath in target_path.rglob("*"):
                if filepath.is_file():
                    builder.ingest_file(str(filepath))
        else:
            builder.ingest_file(str(target_path))

        # Persist back
        repo.flush_to_db(engine)

        console.print(f"[green]Successfully built graph for {target}[/green]")

    except Exception as e:
        console.print(f"[red]Failed to build graph: {e}[/red]")
        sys.exit(1)


# -- Lineage App ------------------------------------------------------------

lineage_app = typer.Typer(
    name="lineage",
    help="Manage and verify artifact lineage metadata.",
    no_args_is_help=True,
)


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
    existing_uuid = None
    for line in content_lines:
        if line.startswith("# sw-artifact: "):
            existing_uuid = line.split(": ")[1].strip()
            break

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

    db = get_db()
    active = _run_workspace_op("get_active_project")
    if not active:
        typer.secho("No active project. Run 'sw project set <name>' first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    proj = _run_workspace_op("get_project", active)
    if not proj:
        typer.secho("Active project not found in global database.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

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
def tree_command(  # noqa: C901
    target: Annotated[str, typer.Argument(help="UUID or Python file path to trace")],
) -> None:
    """Recursively traces up and down the artifact lineage DB to display a rich tree."""
    target_uuid = target
    path_target = Path(target)
    if not path_target.is_absolute():
        try:
            # Check if it looks like a valid path relative to cwd
            if path_target.exists() and path_target.is_file():
                content_lines = path_target.read_text(encoding="utf-8").splitlines()
                for line in content_lines:
                    if line.startswith("# sw-artifact: "):
                        target_uuid = line.split(": ")[1].strip()
                        break
        except Exception:
            pass
    elif path_target.exists() and path_target.is_file():
        try:
            content_lines = path_target.read_text(encoding="utf-8").splitlines()
            for line in content_lines:
                if line.startswith("# sw-artifact: "):
                    target_uuid = line.split(": ")[1].strip()
                    break
        except Exception:
            pass

    db = get_db()
    active = _run_workspace_op("get_active_project")
    if not active:
        typer.secho("No active project. Run 'sw project set <name>' first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    proj = _run_workspace_op("get_project", active)
    if not proj:
        typer.secho("Active project not found in global database.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    from specweaver.core.config.paths import config_db_path

    db_path = config_db_path()
    repo = LineageRepository(str(db_path))
    engine = LineageEngine(repo)

    root_uuid = engine.find_root(target_uuid)
    tree_data = engine.build_tree(root_uuid)

    tree = Tree(f"[bold blue]Lineage Graph (Root: {root_uuid})[/bold blue]")

    def build_node(node_data: dict[str, Any], parent_tree: Tree) -> None:
        node_uid = node_data["id"]

        if node_data["circular"]:
            parent_tree.add(f"[red]Circular reference: {node_uid}[/red]")
            return

        hist = node_data["history"]
        events = [f"{h['event_type']}:{h['model_id']}" for h in hist]

        highlight = "[bold green]" if node_uid == target_uuid else ""
        close = "[/bold green]" if highlight else ""
        label = f"📄 {highlight}{node_uid}{close} [dim]({', '.join(events)})[/dim]"

        node = parent_tree.add(label)

        for child in node_data["children"]:
            build_node(child, node)

    build_node(tree_data, tree)
    console.print(tree)


def check_lineage(src_dir: Path) -> list[str]:
    """Scan the source directory for Python files missing artifact tags.

    Returns a list of absolute paths to files that are missing the '# sw-artifact:' tag.
    """
    orphans: list[str] = []

    if not src_dir.exists() or not src_dir.is_dir():
        return orphans

    # Directories to skip
    excluded_dirs = {".tmp", ".venv", "__pycache__", ".git", ".pytest_cache"}

    # Iterate through all .py files in src_dir
    for py_file in src_dir.rglob("*.py"):
        # Check if the file is inside any excluded directory
        is_excluded = False
        for part in py_file.parts:
            if part in excluded_dirs:
                is_excluded = True
                break

        if is_excluded:
            continue

        # Read the file and check for the tag
        try:
            content = py_file.read_text(encoding="utf-8")
            if "# sw-artifact:" not in content:
                orphans.append(str(py_file.resolve()))
        except Exception as e:
            logger.warning("Could not read file %s: %s", py_file, e)

    return sorted(orphans)
