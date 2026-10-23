# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Core shared objects for the CLI package.

All submodules import this module (not individual names) so that
``monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", ...)`` works
in tests — the lookup goes through the module attribute, not a
local binding.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from specweaver.core.config.autonomy_policy import AutonomyPolicy
    from specweaver.core.config.database import Database
    from specweaver.core.config.doc_policy import DocPolicy
    from specweaver.core.config.llm_settings import LlmSettingsFiles
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.workspace.store import WorkspaceRepository

import anyio
import typer
from rich.console import Console

from specweaver._version import __version__
from specweaver.core.config.bootstrap.db_bootstrap import get_db
from specweaver.workspace.project.discovery import resolve_project_path

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="sw",
    help="SpecWeaver \u2014 Specification-driven development lifecycle tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

_T = TypeVar("_T")

__all__ = [
    "_require_active_project",
    "app",
    "console",
    "get_db",
    "logger",
    "run_repo_op",
]


def run_repo_op(fn: Callable[[WorkspaceRepository], Awaitable[_T]]) -> _T:
    """Run a typed WorkspaceRepository operation synchronously (CLI only).

    Replaces the string-dispatched ``_run_workspace_op`` anti-pattern.
    Each caller passes a typed coroutine function (lambda or async def),
    giving IDE autocomplete and grep-ability.

    Example::

        active = run_repo_op(lambda r: r.get_active_project())
        proj = run_repo_op(lambda r: r.get_project(name))

    Warning: This is CLI-only infrastructure. API handlers must use
    async sessions directly via FastAPI dependency injection.
    """
    from specweaver.workspace.store import WorkspaceRepository

    db = get_db()

    async def _action() -> _T:
        async with db.async_session_scope() as session:
            return await fn(WorkspaceRepository(session))

    return anyio.run(_action)


def _require_active_project() -> str:
    """Get the active project name or exit with error."""
    logger.debug("Executing _require_active_project")
    get_db()
    name_raw = run_repo_op(lambda r: r.get_active_project())
    if not name_raw:
        console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold].",
        )
        raise typer.Exit(code=1)
    return str(name_raw)


def project_root(name: str) -> Path | None:
    """The registered root directory of project `name`, or `None` if it has none."""

    project = run_repo_op(lambda repo: repo.get_project(name))
    root = project.get("root_path") if project else None
    return Path(str(root)) if root else None


def registered_project_at(path: Path) -> str | None:
    """The name of the project registered at `path`, if any."""
    target = path.resolve()
    for project in run_repo_op(lambda repo: repo.list_projects()):
        root = project.get("root_path")
        if root and Path(str(root)).resolve() == target:
            return str(project["name"])
    return None


def project_name_for(path: Path) -> str:
    """The project registered at `path`; the active project when none is registered there."""
    return registered_project_at(path) or _require_active_project()


def load_llm_settings_at(path: Path) -> LlmSettingsFiles:
    """The LLM settings files for the project at `path`, or exit naming the error."""
    from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
    from specweaver.core.config.settings_file import SettingsFileError

    try:
        return load_llm_settings(path)
    except SettingsFileError as err:
        refuse_settings(err)


def load_section_at(path: Path, parse: Callable[[str, str], _T]) -> _T:
    """A section of the project's settings at `path`, or exit naming the file, key and line."""
    from specweaver.core.config.bootstrap.project_settings import load_section
    from specweaver.core.config.settings_file import SettingsFileError

    try:
        return load_section(path, parse)
    except SettingsFileError as err:
        refuse_settings(err)


def project_sections_at(path: Path) -> tuple[DocPolicy, AutonomyPolicy, str | None]:
    """The `[docs]`, `[autonomy]` and `[implement]` language a run is built from, or exit."""
    from specweaver.core.config.autonomy_policy import parse_autonomy
    from specweaver.core.config.doc_policy import parse_doc_policy
    from specweaver.core.config.implement_policy import parse_implement

    return (
        load_section_at(path, parse_doc_policy),
        load_section_at(path, parse_autonomy),
        load_section_at(path, parse_implement).language,
    )


def file_or_exit(given: str) -> Path:
    """`given` as a path when the file exists, or exit naming it."""
    path = Path(given)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {given}")
        raise typer.Exit(code=1)
    return path


def project_path_or_exit(project: str | None) -> Path:
    """The project folder `project` names (the working folder when None), or exit naming why."""
    try:
        return resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def load_project_settings(db: Database, project: str) -> SpecWeaverSettings:
    """The project's settings, or exit naming the file, key and line of a broken one."""
    from specweaver.core.config.bootstrap.settings_loader import load_settings
    from specweaver.core.config.settings_file import SettingsFileError

    try:
        return load_settings(db, project)
    except SettingsFileError as err:
        refuse_settings(err)


def load_active_llm_settings(project_name: str | None = None) -> LlmSettingsFiles:
    """The LLM settings files for a project (the active one by default), or exit naming the error.

    A broken settings file stops every command that uses LLM settings, naming the file and line.
    """
    from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
    from specweaver.core.config.settings_file import SettingsFileError

    try:
        return load_llm_settings(project_root(project_name or _require_active_project()))
    except SettingsFileError as err:
        refuse_settings(err)


def print_error(err: Exception) -> None:
    """The error in full: a message naming `[autonomy]` is text, not markup, and is never cut."""
    console.print("Error:", str(err), style="red", markup=False, highlight=False, soft_wrap=True)


def refuse_settings(err: Exception) -> NoReturn:
    """Stop a command whose settings file cannot be used, naming the file, key and line."""
    print_error(err)
    raise typer.Exit(code=1) from err


def stdin_is_interactive() -> bool:
    import sys

    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):  # expected: stdin is not a terminal
        return False


def ask_to_spend(question: str) -> bool:
    """Ask at a spend limit; only "y" or "yes" goes on, and end of input is a "no".

    Asked on stderr, so a command's own output (`--json`) stays parseable.
    """
    from rich.console import Console
    from rich.prompt import Prompt

    try:
        answer = Prompt.ask(
            f"Spend brake: {question} [y/N]", default="", console=Console(stderr=True)
        )
    except EOFError:  # expected: no answer means no
        return False
    return answer.strip().lower() in ("y", "yes")


def spend_asker() -> Callable[[str], bool] | None:
    """The spend question for a command with a terminal; none without one."""
    return ask_to_spend if stdin_is_interactive() else None


def _version_callback(value: bool) -> None:
    logger.debug("Executing _version_callback (value=%s)", value)
    if value:
        console.print(f"SpecWeaver v{__version__}")
        raise typer.Exit()
