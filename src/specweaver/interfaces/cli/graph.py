import sys
from pathlib import Path
from typing import Annotated

import typer

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.store.repository import SqliteGraphRepository
from specweaver.interfaces.cli._core import app as core_app
from specweaver.interfaces.cli._core import console
from specweaver.interfaces.cli._helpers import _load_topology
from specweaver.workspace.adapters.graph_adapter import extract_ast_dict


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

app = typer.Typer(
    name="graph",
    help="Manage the Knowledge Graph.",
    no_args_is_help=True,
)

core_app.add_typer(app, name="graph")

@app.command()
def build(
    target: Annotated[str, typer.Argument(
        help="Path to a file or directory to ingest into the Knowledge Graph.",
    )],
    project_path: Annotated[Path, typer.Option(
        "--project-path",
        "-p",
        help="Path to the root of the project.",
    )] = Path("."),
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
