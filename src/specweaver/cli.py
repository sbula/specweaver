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

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from specweaver import __version__
from specweaver.project.discovery import resolve_project_path
from specweaver.project.scaffold import scaffold_project

if TYPE_CHECKING:
    from specweaver.validation.models import RuleResult

app = typer.Typer(
    name="sw",
    help="SpecWeaver — Specification-driven development lifecycle tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

# Status display mapping (shared across check command)
_STATUS_STYLE = {
    "pass": "[green]PASS[/green]",
    "fail": "[red]FAIL[/red]",
    "warn": "[yellow]WARN[/yellow]",
    "skip": "[dim]SKIP[/dim]",
}


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"SpecWeaver v{__version__}")
        raise typer.Exit()


def _display_results(
    results: list[RuleResult],
    title: str,
) -> None:
    """Display validation results as a Rich table with findings."""
    from specweaver.validation.models import Status

    table = Table(title=title)
    table.add_column("Rule", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    for r in results:
        table.add_row(
            r.rule_id,
            r.rule_name,
            _STATUS_STYLE.get(r.status.value, str(r.status)),
            r.message[:80] if r.message else "",
        )
    console.print(table)

    # Show detailed findings for failed/warned rules
    for r in results:
        if r.findings and r.status in (Status.FAIL, Status.WARN):
            console.print(
                f"\n[bold]{r.rule_id} {r.rule_name}[/bold] findings:",
            )
            for f in r.findings:
                line_info = f" (line {f.line})" if f.line else ""
                console.print(
                    f"  [{f.severity.value}] {f.message}{line_info}",
                )
                if f.suggestion:
                    console.print(f"    [dim]-> {f.suggestion}[/dim]")


def _print_summary(results: list[RuleResult]) -> None:
    """Print pass/fail summary and raise Exit(1) on failures."""
    from specweaver.validation.models import Status

    fail_count = sum(1 for r in results if r.status == Status.FAIL)
    warn_count = sum(1 for r in results if r.status == Status.WARN)

    if fail_count > 0:
        console.print(
            f"\n[red]FAILED[/red]: {fail_count} rule(s) failed, {warn_count} warning(s)",
        )
        raise typer.Exit(code=1)
    if warn_count > 0:
        console.print(
            f"\n[yellow]PASSED with warnings[/yellow]: {warn_count} warning(s)",
        )
    else:
        console.print("\n[green]ALL PASSED[/green]")


def _require_llm_adapter(project_path: Path) -> tuple:
    """Create and validate an LLM adapter from project settings.

    Returns (settings, adapter, gen_config) or raises typer.Exit.
    """
    from specweaver.config.settings import load_settings
    from specweaver.llm.gemini_adapter import GeminiAdapter
    from specweaver.llm.models import GenerationConfig

    settings = load_settings(project_path)
    adapter = GeminiAdapter(api_key=settings.llm.api_key or None)

    if not adapter.available():
        console.print(
            "[red]Error:[/red] No API key configured. Set GEMINI_API_KEY environment variable.",
        )
        raise typer.Exit(code=1)

    gen_config = GenerationConfig(
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_output_tokens=settings.llm.max_output_tokens,
    )

    return settings, adapter, gen_config


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
        help="Path to the target project directory. Defaults to cwd.",
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
            f"[green]Project initialized[/green] at [bold]{result.project_path}[/bold]",
        )
        for item in result.created:
            console.print(f"  [dim]Created:[/dim] {item}")
    else:
        console.print(
            f"[yellow]Already initialized[/yellow] at "
            f"[bold]{result.project_path}[/bold] (no changes needed)",
        )


# ---------------------------------------------------------------------------
# sw check
# ---------------------------------------------------------------------------


@app.command()
def check(
    target: str = typer.Argument(
        help="Path to the spec or code file to check.",
    ),
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
    from specweaver.validation.runner import (
        get_code_rules,
        get_spec_rules,
        run_rules,
    )

    target_path = Path(target)
    if not target_path.exists():
        console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    content = target_path.read_text(encoding="utf-8")

    if level == "component":
        rules = get_spec_rules(include_llm=False)
        results = run_rules(rules, content, target_path)
        _display_results(results, f"Spec Validation: {target_path.name}")
        _print_summary(results)
    elif level == "code":
        rules = get_code_rules(include_subprocess=False)
        results = run_rules(rules, content, target_path)
        _display_results(results, f"Code Validation: {target_path.name}")
        _print_summary(results)
    else:
        console.print(
            f"[red]Error:[/red] Unknown level '{level}'. Use 'component' or 'code'.",
        )
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# sw draft
# ---------------------------------------------------------------------------


@app.command()
def draft(
    name: str = typer.Argument(
        help="Name of the component to draft a spec for.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Interactively draft a new component spec with LLM assistance."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    specs_dir = project_path / "specs"
    spec_path = specs_dir / f"{name}_spec.md"
    if spec_path.exists():
        console.print(
            f"[yellow]Warning:[/yellow] {spec_path} already exists. It will NOT be overwritten.",
        )
        raise typer.Exit(code=1)

    from specweaver.context.hitl_provider import HITLProvider
    from specweaver.drafting.drafter import Drafter

    _, adapter, gen_config = _require_llm_adapter(project_path)

    drafter = Drafter(
        llm=adapter,
        context_provider=HITLProvider(console=console),
        config=gen_config,
    )

    console.print(
        f"\n[bold]Drafting spec for[/bold] [cyan]{name}[/cyan]\n"
        "[dim]Answer questions below. Press Enter to skip.[/dim]\n",
    )

    result_path = asyncio.run(drafter.draft(name, specs_dir))

    console.print(f"\n[green]Spec drafted:[/green] {result_path}")
    console.print("[dim]Run 'sw check' to validate the drafted spec.[/dim]")


# ---------------------------------------------------------------------------
# sw review
# ---------------------------------------------------------------------------


@app.command()
def review(
    target: str = typer.Argument(
        help="Path to the spec or code file to review.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    spec: str | None = typer.Option(
        None,
        "--spec",
        "-s",
        help="Path to the source spec (required for code review).",
    ),
) -> None:
    """Submit a spec or code file for LLM-based review.

    Returns ACCEPTED or DENIED with structured findings.
    For code review, also provide --spec to compare against.
    """
    target_path = Path(target)
    if not target_path.exists():
        console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.review.reviewer import Reviewer

    _, adapter, gen_config = _require_llm_adapter(project_path)
    gen_config.temperature = 0.3  # Lower for reviews

    reviewer = Reviewer(llm=adapter, config=gen_config)

    console.print(f"\n[bold]Reviewing:[/bold] {target_path.name}")
    console.print("[dim]Sending to LLM for semantic review...[/dim]\n")

    result = _execute_review(reviewer, target_path, spec)
    _display_review_result(result)


def _execute_review(
    reviewer: object,
    target_path: Path,
    spec: str | None,
) -> object:
    """Run the appropriate review (spec or code)."""
    if spec:
        spec_path = Path(spec)
        if not spec_path.exists():
            console.print(f"[red]Error:[/red] Spec not found: {spec}")
            raise typer.Exit(code=1)
        return asyncio.run(reviewer.review_code(target_path, spec_path))
    return asyncio.run(reviewer.review_spec(target_path))


def _display_review_result(result: object) -> None:
    """Display review verdict and findings."""
    from specweaver.review.reviewer import ReviewVerdict

    verdict_style = {
        ReviewVerdict.ACCEPTED: "[green bold]VERDICT: ACCEPTED[/green bold]",
        ReviewVerdict.DENIED: "[red bold]VERDICT: DENIED[/red bold]",
        ReviewVerdict.ERROR: "[yellow bold]VERDICT: ERROR[/yellow bold]",
    }
    console.print(verdict_style.get(result.verdict, str(result.verdict)))

    if result.summary:
        console.print(f"\n{result.summary}")

    if result.findings:
        console.print(f"\n[bold]Findings ({len(result.findings)}):[/bold]")
        for f in result.findings:
            console.print(f"  - {f.message}")

    if result.verdict == ReviewVerdict.DENIED:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# sw implement (stub)
# ---------------------------------------------------------------------------


@app.command()
def implement(
    spec: str = typer.Argument(
        help="Path to the spec file to implement.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Generate code + tests from a validated, reviewed spec."""
    console.print(
        f"[yellow]Implement[/yellow] is not yet implemented. (spec={spec})",
    )
