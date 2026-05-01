import sys
from pathlib import Path
from typing import Annotated

import typer

from specweaver.graph.builder.orchestrator import GraphBuilder
from specweaver.graph.engine.core import InMemoryGraphEngine
from specweaver.graph.store.repository import SqliteGraphRepository
from specweaver.interfaces.cli._core import app as core_app
from specweaver.interfaces.cli._core import console
from specweaver.workspace.adapters.graph_adapter import extract_ast_dict

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
        # In a real context, we'd read service_name from context.yaml
        repo = SqliteGraphRepository(db_path, "default")

        # Load any existing state
        graph, _ = repo.load_from_db()
        engine._graph = graph

        # Inject the workspace parser adapter
        builder = GraphBuilder(engine=engine, parser=extract_ast_dict)

        # Ingest the target
        target_path = Path(target)
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
