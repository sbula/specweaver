# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for lineage tracking and orphan detection."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.tree import Tree

from specweaver.cli._core import app as core_app
from specweaver.cli._core import console, get_db

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="lineage",
    help="Manage and verify artifact lineage metadata.",
    no_args_is_help=True,
)

core_app.add_typer(app, name="lineage")


@app.command("tag")
def tag(
    target: Annotated[Path, typer.Argument(help="Python file to tag")],
    author: Annotated[str, typer.Option("--author", help="Author of the artifact or manual edit")] = "human",
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
        rprint(f"[yellow]File already tagged with {target_uuid}. Logging manual edit event.[/yellow]")
    else:
        target_uuid = str(uuid.uuid4())
        if content_lines and content_lines[0].startswith("#!"):
            content_lines.insert(1, f"# sw-artifact: {target_uuid}")
        else:
            content_lines.insert(0, f"# sw-artifact: {target_uuid}")
        target.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
        rprint(f"[green]Added tag {target_uuid} to {target}[/green]")

    db = get_db()
    db.log_artifact_event(
        artifact_id=target_uuid,
        parent_id=None,
        run_id="manual",
        event_type="manual_tag",
        model_id=author,
    )


@app.command("tree")
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
    current = target_uuid
    root_uuid = current

    # Safe walk up to root
    visited_ancestors = set()
    while True:
        if current in visited_ancestors:
            break
        visited_ancestors.add(current)
        history = db.get_artifact_history(current)
        if not history:
            break
        parent_id = history[0].get("parent_id")
        if not parent_id:
            break
        current = parent_id
        root_uuid = current

    tree = Tree(f"[bold blue]Lineage Graph (Root: {root_uuid})[/bold blue]")

    def build_node(node_uid: str, parent_tree: Tree, visited: set[str]) -> None:
        if node_uid in visited:
            parent_tree.add(f"[red]Circular reference: {node_uid}[/red]")
            return
        visited.add(node_uid)

        hist = db.get_artifact_history(node_uid)
        events = [f"{h['event_type']}:{h['model_id']}" for h in hist]

        highlight = "[bold green]" if node_uid == target_uuid else ""
        close = "[/bold green]" if highlight else ""
        label = f"📄 {highlight}{node_uid}{close} [dim]({', '.join(events)})[/dim]"

        node = parent_tree.add(label)

        children = db.get_children(node_uid)
        child_uids = list(dict.fromkeys(c["artifact_id"] for c in children if c["artifact_id"] != node_uid))
        for c_uid in child_uids:
            build_node(c_uid, node, visited.copy())

    build_node(root_uuid, tree, set())
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
