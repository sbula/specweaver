# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SpecWeaver CLI — Typer application.

Entry point registered as `sw` in pyproject.toml.
Commands:
- sw init       — Initialize project scaffold
- sw check      — Run validation rules (spec or code)
- sw draft      — Interactive spec drafting
- sw review     — LLM-based spec/code review
- sw implement  — Generate code from spec
"""

from __future__ import annotations

import typer
from rich.console import Console

from specweaver import __version__
from specweaver.project.discovery import resolve_project_path
from specweaver.project.scaffold import scaffold_project

app = typer.Typer(
    name="sw",
    help="SpecWeaver — Specification-driven development lifecycle tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"SpecWeaver v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """SpecWeaver — Specification-driven development lifecycle tool."""


# ---------------------------------------------------------------------------
# sw init
# ---------------------------------------------------------------------------

@app.command()
def init(
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory. Defaults to current directory.",
    ),
) -> None:
    """Initialize a project with SpecWeaver scaffolding.

    Creates .specweaver/, specs/, config.yaml, and spec templates.
    Safe to run multiple times — existing files are never overwritten.
    """
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    result = scaffold_project(project_path)

    if result.created:
        console.print(
            f"[green]Project initialized[/green] at [bold]{result.project_path}[/bold]"
        )
        for item in result.created:
            console.print(f"  [dim]Created:[/dim] {item}")
    else:
        console.print(
            f"[yellow]Already initialized[/yellow] at [bold]{result.project_path}[/bold] "
            "(no changes needed)"
        )


# ---------------------------------------------------------------------------
# sw check (stub)
# ---------------------------------------------------------------------------

@app.command()
def check(
    target: str = typer.Argument(help="Path to the spec or code file to check."),
    level: str = typer.Option(
        "component",
        "--level",
        "-l",
        help="Validation level: component (spec) or code.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Run validation rules against a spec or code file.

    Uses --level to determine which rule set to apply:
    - component: Spec validation rules S01-S10
    - code: Code validation rules C01-C08
    """
    console.print(
        f"[yellow]Check[/yellow] is not yet implemented. "
        f"(level={level}, target={target})"
    )


# ---------------------------------------------------------------------------
# sw draft (stub)
# ---------------------------------------------------------------------------

@app.command()
def draft(
    name: str = typer.Argument(help="Name of the component to draft a spec for."),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Interactively draft a new component spec with LLM assistance."""
    console.print(
        f"[yellow]Draft[/yellow] is not yet implemented. (name={name})"
    )


# ---------------------------------------------------------------------------
# sw review (stub)
# ---------------------------------------------------------------------------

@app.command()
def review(
    target: str = typer.Argument(help="Path to the spec or code file to review."),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Submit a spec or code file for LLM-based review.

    Returns ACCEPTED or DENIED with structured findings.
    """
    console.print(
        f"[yellow]Review[/yellow] is not yet implemented. (target={target})"
    )


# ---------------------------------------------------------------------------
# sw implement (stub)
# ---------------------------------------------------------------------------

@app.command()
def implement(
    spec: str = typer.Argument(help="Path to the spec file to implement."),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Generate code + tests from a validated, reviewed spec."""
    console.print(
        f"[yellow]Implement[/yellow] is not yet implemented. (spec={spec})"
    )
