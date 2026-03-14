# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SpecWeaver CLI — Typer application.

Entry point registered as `sw` in pyproject.toml.
Commands:
- sw init       — Register project + scaffold
- sw use        — Switch active project
- sw projects   — List registered projects
- sw remove     — Unregister a project
- sw update     — Update project settings
- sw scan       — Auto-generate context.yaml files
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
from specweaver.config.database import Database
from specweaver.project.discovery import resolve_project_path
from specweaver.project.scaffold import scaffold_project

if TYPE_CHECKING:
    from specweaver.config.settings import ValidationSettings
    from specweaver.validation.models import RuleResult

app = typer.Typer(
    name="sw",
    help="SpecWeaver — Specification-driven development lifecycle tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

config_app = typer.Typer(
    name="config",
    help="Manage per-project validation rule overrides.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

console = Console()

# Status display mapping (shared across check command)
_STATUS_STYLE = {
    "pass": "[green]PASS[/green]",
    "fail": "[red]FAIL[/red]",
    "warn": "[yellow]WARN[/yellow]",
    "skip": "[dim]SKIP[/dim]",
}

_DEFAULT_DB_PATH = Path.home() / ".specweaver" / "specweaver.db"


def get_db() -> Database:
    """Get the global SpecWeaver database (creates if needed)."""
    return Database(_DEFAULT_DB_PATH)


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


def _print_summary(results: list[RuleResult], *, strict: bool = False) -> None:
    """Print pass/fail summary and raise Exit(1) on failures.

    Args:
        results: Validation results to summarize.
        strict: If True, WARNs also cause exit code 1.
    """
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
        if strict:
            raise typer.Exit(code=1)
    else:
        console.print("\n[green]ALL PASSED[/green]")


def _require_llm_adapter(project_path: Path, *, llm_role: str = "draft") -> tuple:
    """Create and validate an LLM adapter from project settings.

    Returns (settings, adapter, gen_config) or raises typer.Exit.
    """
    from specweaver.config.settings import load_settings_for_active
    from specweaver.llm.adapters.gemini import GeminiAdapter
    from specweaver.llm.models import GenerationConfig

    db = get_db()
    try:
        settings = load_settings_for_active(db, llm_role=llm_role)
    except ValueError:
        # Fallback: try loading from env with defaults
        import os

        from specweaver.config.settings import LLMSettings, SpecWeaverSettings

        settings = SpecWeaverSettings(
            llm=LLMSettings(api_key=os.environ.get("GEMINI_API_KEY", "")),
        )

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
# sw init <name> --path <path>
# ---------------------------------------------------------------------------


@app.command()
def init(
    name: str = typer.Argument(
        help="Project name (lowercase, hyphens, underscores only).",
    ),
    path: str | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to the project directory. Defaults to cwd.",
    ),
) -> None:
    """Register a project and create SpecWeaver scaffolding.

    Creates .specweaver/ marker, context.yaml, specs/, templates.
    Registers the project in the SpecWeaver database and sets it as active.
    """
    try:
        project_path = resolve_project_path(path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Register in DB
    db = get_db()
    try:
        db.register_project(name, str(project_path))
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    db.set_active_project(name)

    # Scaffold files
    result = scaffold_project(project_path)

    console.print(
        f"[green]Project initialized[/green] at [bold]{result.project_path}[/bold]",
    )
    for item in result.created:
        console.print(f"  [dim]Created:[/dim] {item}")
    console.print(f"  [dim]Registered:[/dim] project [bold]{name}[/bold]")
    console.print(f"  [dim]Active:[/dim] {name}")


# ---------------------------------------------------------------------------
# sw use <name>
# ---------------------------------------------------------------------------


@app.command()
def use(
    name: str = typer.Argument(
        help="Name of the project to switch to.",
    ),
) -> None:
    """Switch the active project."""
    db = get_db()
    proj = db.get_project(name)
    if not proj:
        console.print(
            f"[red]Error:[/red] Project '{name}' not found. "
            f"Run [bold]sw init {name} --path <path>[/bold] to register it.",
        )
        raise typer.Exit(code=1)

    # Check path still exists
    root = Path(proj["root_path"])
    if not root.exists():
        console.print(
            f"[red]Error:[/red] Project root no longer exists: {root}\n"
            f"  Run [bold]sw update {name} path <new-path>[/bold] if moved, or\n"
            f"  [bold]sw remove {name}[/bold] to unregister.",
        )
        raise typer.Exit(code=1)

    db.set_active_project(name)
    console.print(f"[green]Switched[/green] to project [bold]{name}[/bold] ({root})")


# ---------------------------------------------------------------------------
# sw projects
# ---------------------------------------------------------------------------


@app.command()
def projects() -> None:
    """List all registered projects."""
    db = get_db()
    all_projects = db.list_projects()
    active = db.get_active_project()

    if not all_projects:
        console.print(
            "[dim]No projects registered. Run [bold]sw init <name>[/bold] to add one.[/dim]",
        )
        return

    table = Table(title="SpecWeaver Projects")
    table.add_column("", width=2)
    table.add_column("Name", style="bold")
    table.add_column("Path")
    table.add_column("Last Used", style="dim")

    for proj in all_projects:
        marker = "*" if proj["name"] == active else ""
        table.add_row(
            marker,
            proj["name"],
            proj["root_path"],
            proj["last_used_at"][:10],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# sw remove <name>
# ---------------------------------------------------------------------------


@app.command()
def remove(
    name: str = typer.Argument(
        help="Name of the project to unregister.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Unregister a project from SpecWeaver."""
    db = get_db()
    proj = db.get_project(name)
    if not proj:
        console.print(f"[red]Error:[/red] Project '{name}' not found.")
        raise typer.Exit(code=1)

    if not force:
        confirm = typer.confirm(
            f"Unregister project '{name}' and delete its config?",
        )
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            return

    db.remove_project(name)
    console.print(f"[green]Removed[/green] project [bold]{name}[/bold]")


# ---------------------------------------------------------------------------
# sw update <name> path <new-path>
# ---------------------------------------------------------------------------


@app.command()
def update(
    name: str = typer.Argument(
        help="Name of the project to update.",
    ),
    field: str = typer.Argument(
        help="Field to update (currently: 'path').",
    ),
    value: str = typer.Argument(
        help="New value for the field.",
    ),
) -> None:
    """Update a project setting (e.g., root path)."""
    db = get_db()
    if field == "path":
        try:
            db.update_project_path(name, value)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(
            f"[green]Updated[/green] project [bold]{name}[/bold] path → {value}",
        )
    else:
        console.print(f"[red]Error:[/red] Unknown field '{field}'. Supported: path")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# sw scan
# ---------------------------------------------------------------------------


@app.command()
def scan() -> None:
    """Scan the active project and auto-generate missing context.yaml files."""
    db = get_db()
    active = db.get_active_project()
    if not active:
        console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold] first.",
        )
        raise typer.Exit(code=1)

    proj = db.get_project(active)
    project_path = Path(proj["root_path"])

    if not project_path.exists():
        console.print(f"[red]Error:[/red] Project root does not exist: {project_path}")
        raise typer.Exit(code=1)

    from specweaver.context.inferrer import ContextInferrer

    inferrer = ContextInferrer()
    console.print(f"[bold]Scanning[/bold] {project_path}...")

    generated = 0
    skipped = 0
    existing = 0

    for subdir in sorted(project_path.rglob("*")):
        if not subdir.is_dir():
            continue
        if any(p.startswith(".") or p == "__pycache__" for p in subdir.parts):
            continue

        context_file = subdir / "context.yaml"
        if context_file.exists():
            rel = subdir.relative_to(project_path)
            console.print(f"  [green]✓[/green] {rel}/ — context.yaml exists")
            existing += 1
            continue

        # Only infer for directories with Python files
        py_files = list(subdir.glob("*.py"))
        if not py_files:
            skipped += 1
            continue

        try:
            inferrer.infer_and_write(subdir)
            rel = subdir.relative_to(project_path)
            console.print(f"  [yellow]⚠[/yellow] {rel}/ — AUTO-GENERATED (review recommended)")
            generated += 1
        except Exception:  # noqa: BLE001
            rel = subdir.relative_to(project_path)
            console.print(f"  [red]✗[/red] {rel}/ — failed to infer")

    console.print(
        f"\n[bold]Scan complete[/bold]: "
        f"{existing} existing, {generated} generated, {skipped} skipped",
    )


# ---------------------------------------------------------------------------
# sw check
# ---------------------------------------------------------------------------


def _load_check_settings(
    set_overrides: list[str] | None,
) -> "ValidationSettings | None":
    """Load ValidationSettings from DB + CLI --set overrides.

    Cascade: code defaults → project DB overrides → --set CLI flags.
    Returns None if no active project and no --set flags.
    """
    from specweaver.config.settings import RuleOverride, ValidationSettings

    settings: ValidationSettings | None = None

    # 1. Try loading from DB for the active project
    db = get_db()
    active = db.get_active_project()
    if active:
        try:
            settings = db.load_validation_settings(active)
        except ValueError:
            pass  # project not found — proceed without DB overrides

    # 2. Apply --set CLI overrides on top
    if set_overrides:
        if settings is None:
            settings = ValidationSettings()

        for item in set_overrides:
            # Format: RULE.FIELD=VALUE  (e.g. S08.fail_threshold=5)
            if "=" not in item or "." not in item.split("=", 1)[0]:
                console.print(
                    f"[red]Error:[/red] Invalid --set format: '{item}'. "
                    "Expected RULE.FIELD=VALUE (e.g. S08.fail_threshold=5).",
                )
                raise typer.Exit(code=1)

            key, value = item.split("=", 1)
            rule_id, field = key.rsplit(".", 1)
            rule_id = rule_id.upper()

            # Get or create override for this rule
            existing = settings.overrides.get(rule_id)
            if existing is None:
                existing = RuleOverride(rule_id=rule_id)
                settings.overrides[rule_id] = existing

            if field == "enabled":
                settings.overrides[rule_id] = existing.model_copy(
                    update={"enabled": value.lower() in ("true", "1", "yes")},
                )
            elif field in ("warn_threshold", "fail_threshold"):
                try:
                    settings.overrides[rule_id] = existing.model_copy(
                        update={field: float(value)},
                    )
                except ValueError:
                    console.print(
                        f"[red]Error:[/red] Invalid threshold value: '{value}'. "
                        "Must be a number.",
                    )
                    raise typer.Exit(code=1)
            else:
                # Route to extra_params (e.g. S01.max_h2=5)
                try:
                    new_extra = {**existing.extra_params, field: float(value)}
                    settings.overrides[rule_id] = existing.model_copy(
                        update={"extra_params": new_extra},
                    )
                except ValueError:
                    console.print(
                        f"[red]Error:[/red] Invalid value for '{field}': '{value}'. "
                        "Must be a number.",
                    )
                    raise typer.Exit(code=1) from None

    return settings


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
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warnings as failures (exit code 1).",
    ),
    set_overrides: list[str] | None = typer.Option(
        None,
        "--set",
        help="One-off override: RULE.FIELD=VALUE (e.g. S08.fail_threshold=5).",
    ),
) -> None:
    """Run validation rules against a spec or code file.

    Uses --level to determine which rule set to apply:
    - component: Spec validation rules S01-S11
    - code: Code validation rules C01-C08

    Override cascade: code defaults → project DB overrides → --set flags.
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

    # Load settings: DB overrides for active project (if any)
    settings = _load_check_settings(set_overrides)

    content = target_path.read_text(encoding="utf-8")

    if level == "component":
        rules = get_spec_rules(include_llm=False, settings=settings)
        results = run_rules(rules, content, target_path)
        _display_results(results, f"Spec Validation: {target_path.name}")
        _print_summary(results, strict=strict)
    elif level == "code":
        rules = get_code_rules(include_subprocess=False, settings=settings)
        results = run_rules(rules, content, target_path)
        _display_results(results, f"Code Validation: {target_path.name}")
        _print_summary(results, strict=strict)
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
# sw implement
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
    """Generate code + tests from a validated, reviewed spec.

    Reads a validated spec and uses the LLM to generate:
    - Implementation source file in src/
    - Test file in tests/
    """
    spec_path = Path(spec)
    if not spec_path.exists():
        console.print(f"[red]Error:[/red] Spec not found: {spec}")
        raise typer.Exit(code=1)

    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.implementation.generator import Generator

    _, adapter, gen_config = _require_llm_adapter(project_path)
    gen_config.temperature = 0.2  # Low temperature for code

    generator = Generator(llm=adapter, config=gen_config)

    # Derive output paths from spec name
    # e.g., "greet_service_spec.md" -> "greet_service.py"
    stem = spec_path.stem.removesuffix("_spec")
    src_dir = project_path / "src"
    tests_dir = project_path / "tests"

    code_path = src_dir / f"{stem}.py"
    test_path = tests_dir / f"test_{stem}.py"

    console.print(
        f"\n[bold]Implementing:[/bold] {spec_path.name}",
    )
    console.print(
        f"  [dim]Code:[/dim]  {code_path}\n"
        f"  [dim]Tests:[/dim] {test_path}\n",
    )

    # Generate code
    console.print("[dim]Generating implementation code...[/dim]")
    asyncio.run(generator.generate_code(spec_path, code_path))
    console.print(f"  [green]✓[/green] {code_path}")

    # Generate tests
    console.print("[dim]Generating test file...[/dim]")
    asyncio.run(generator.generate_tests(spec_path, test_path))
    console.print(f"  [green]✓[/green] {test_path}")

    console.print(
        "\n[green]Implementation complete![/green]\n"
        "[dim]Next steps:\n"
        "  sw check --level=code <generated_file>\n"
        "  sw review <generated_file> --spec <spec_file>[/dim]",
    )


# ---------------------------------------------------------------------------
# sw config set/get/list/reset
# ---------------------------------------------------------------------------


def _require_active_project() -> str:
    """Get the active project name or exit with error."""
    db = get_db()
    name = db.get_active_project()
    if not name:
        console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold].",
        )
        raise typer.Exit(code=1)
    return name


@config_app.command("set")
def config_set(
    rule_id: str = typer.Argument(help="Rule ID (e.g. S08, C04)."),
    *,
    enabled: bool | None = typer.Option(None, help="Enable/disable the rule."),
    warn: float | None = typer.Option(None, "--warn", help="Warning threshold."),
    fail: float | None = typer.Option(None, "--fail", help="Failure threshold."),
) -> None:
    """Set a validation override for the active project."""
    name = _require_active_project()
    rule_upper = rule_id.upper()

    if enabled is None and warn is None and fail is None:
        console.print(
            "[red]Error:[/red] Provide at least one of "
            "--enabled/--no-enabled, --warn, --fail.",
        )
        raise typer.Exit(code=1)

    db = get_db()
    db.set_validation_override(
        name,
        rule_upper,
        enabled=enabled,
        warn_threshold=warn,
        fail_threshold=fail,
    )

    parts: list[str] = []
    if enabled is not None:
        parts.append(f"enabled={enabled}")
    if warn is not None:
        parts.append(f"warn={warn}")
    if fail is not None:
        parts.append(f"fail={fail}")

    console.print(
        f"[green]✓[/green] Override set for [bold]{rule_upper}[/bold] "
        f"({', '.join(parts)}) on project [bold]{name}[/bold].",
    )


@config_app.command("get")
def config_get(
    rule_id: str = typer.Argument(help="Rule ID to query."),
) -> None:
    """Show the current override for a rule in the active project."""
    name = _require_active_project()
    rule_upper = rule_id.upper()

    db = get_db()
    o = db.get_validation_override(name, rule_upper)

    if o is None:
        console.print(
            f"[dim]No override for [bold]{rule_upper}[/bold] "
            f"on project [bold]{name}[/bold] (using defaults).[/dim]",
        )
        return

    table = Table(title=f"Override: {rule_upper} ({name})")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("enabled", str(bool(o["enabled"])))
    table.add_row("warn_threshold", str(o["warn_threshold"]))
    table.add_row("fail_threshold", str(o["fail_threshold"]))
    console.print(table)


@config_app.command("list")
def config_list() -> None:
    """List all validation overrides for the active project."""
    name = _require_active_project()

    db = get_db()
    overrides = db.get_validation_overrides(name)

    if not overrides:
        console.print(
            f"[dim]No overrides configured for project [bold]{name}[/bold] "
            "(all rules use defaults).[/dim]",
        )
        return

    table = Table(title=f"Validation Overrides ({name})")
    table.add_column("Rule", style="cyan")
    table.add_column("Enabled")
    table.add_column("Warn Threshold")
    table.add_column("Fail Threshold")

    for o in overrides:
        table.add_row(
            o["rule_id"],
            "[green]Yes[/green]" if o["enabled"] else "[red]No[/red]",
            str(o["warn_threshold"]) if o["warn_threshold"] is not None else "[dim]—[/dim]",
            str(o["fail_threshold"]) if o["fail_threshold"] is not None else "[dim]—[/dim]",
        )

    console.print(table)


@config_app.command("reset")
def config_reset(
    rule_id: str = typer.Argument(help="Rule ID to reset (removes override)."),
) -> None:
    """Remove the override for a rule, reverting to defaults."""
    name = _require_active_project()
    rule_upper = rule_id.upper()

    db = get_db()
    db.delete_validation_override(name, rule_upper)

    console.print(
        f"[green]✓[/green] Override removed for [bold]{rule_upper}[/bold] "
        f"on project [bold]{name}[/bold] (using defaults).",
    )

