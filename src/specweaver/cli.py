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
import logging
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
    from specweaver.graph.topology import TopologyGraph
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

logger = logging.getLogger(__name__)

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
    """SpecWeaver — Specification-driven development lifecycle tool."""
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
    logger.debug("CLI invoked — active project: %s", active or "(none)")


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


def _load_topology(project_path: Path) -> TopologyGraph | None:
    """Try to load the project's topology graph from context.yaml files.

    Returns ``None`` (with a dim console note) if no context.yaml files
    are found — this keeps all LLM commands usable without context.
    """
    from specweaver.graph.topology import TopologyGraph

    graph = TopologyGraph.from_project(project_path, auto_infer=False)
    if not graph.nodes:
        console.print(
            "[dim]No context.yaml files found — topology context disabled.[/dim]",
        )
        return None
    console.print(
        f"[dim]Loaded topology: {len(graph.nodes)} modules.[/dim]",
    )
    return graph


# Selector name -> class mapping (configurable via --selector)
_SELECTOR_MAP: dict[str, type] = {}


def _get_selector_map() -> dict[str, type]:
    """Lazily populate and return the selector name->class mapping."""
    if not _SELECTOR_MAP:
        from specweaver.graph.selectors import (
            ConstraintOnlySelector,
            DirectNeighborSelector,
            ImpactWeightedSelector,
            NHopConstraintSelector,
        )

        _SELECTOR_MAP.update({
            "direct": DirectNeighborSelector,
            "nhop": NHopConstraintSelector,
            "constraint": ConstraintOnlySelector,
            "impact": ImpactWeightedSelector,
        })
    return _SELECTOR_MAP


def _select_topology_contexts(
    graph: TopologyGraph | None,
    module_name: str,
    *,
    selector_name: str = "direct",
) -> list | None:
    """Run a selector and return topology contexts, or None.

    Args:
        graph: The topology graph (None = no topology).
        module_name: Target module name (typically derived from spec/file stem).
        selector_name: One of 'direct', 'nhop', 'constraint', 'impact'.

    Returns:
        List of TopologyContext, or None if no graph or no related modules.
    """
    if graph is None:
        return None

    selector_map = _get_selector_map()
    selector_cls = selector_map.get(selector_name)
    if selector_cls is None:
        console.print(
            f"[yellow]Warning:[/yellow] Unknown selector '{selector_name}', "
            "falling back to 'direct'.",
        )
        from specweaver.graph.selectors import DirectNeighborSelector

        selector_cls = DirectNeighborSelector

    selector = selector_cls()
    related = selector.select(graph, module_name)
    if not related:
        return None

    contexts = graph.format_context_summary(module_name, related)
    console.print(
        f"[dim]Topology: {len(contexts)} related module(s) "
        f"via {selector_name} selector.[/dim]",
    )
    return contexts

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
            f"[green]Updated[/green] project [bold]{name}[/bold] path -> {value}",
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
        except Exception:
            rel = subdir.relative_to(project_path)
            console.print(f"  [red]✗[/red] {rel}/ — failed to infer")

    console.print(
        f"\n[bold]Scan complete[/bold]: "
        f"{existing} existing, {generated} generated, {skipped} skipped",
    )


# ---------------------------------------------------------------------------
# sw check
# ---------------------------------------------------------------------------


def _apply_override(
    settings: ValidationSettings,
    item: str,
) -> None:
    """Parse and apply a single RULE.FIELD=VALUE override, or exit on error."""
    from specweaver.config.settings import RuleOverride

    if "=" not in item or "." not in item.split("=", 1)[0]:
        console.print(
            f"[red]Error:[/red] Invalid --set format: '{item}'. "
            "Expected RULE.FIELD=VALUE (e.g. S08.fail_threshold=5).",
        )
        raise typer.Exit(code=1)

    key, value = item.split("=", 1)
    rule_id, field = key.rsplit(".", 1)
    rule_id = rule_id.upper()

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
            raise typer.Exit(code=1) from None
    else:
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


def _load_check_settings(
    set_overrides: list[str] | None,
) -> ValidationSettings | None:
    """Load ValidationSettings from DB + CLI --set overrides.

    Cascade: code defaults -> project DB overrides -> --set CLI flags.
    Returns None if no active project and no --set flags.
    """
    from specweaver.config.settings import ValidationSettings

    settings: ValidationSettings | None = None

    # 1. Try loading from DB for the active project
    db = get_db()
    active = db.get_active_project()
    if active:
        import contextlib

        with contextlib.suppress(ValueError):
            settings = db.load_validation_settings(active)

    # 2. Apply --set CLI overrides on top
    if set_overrides:
        if settings is None:
            settings = ValidationSettings()
        for item in set_overrides:
            _apply_override(settings, item)

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
        help="Validation level: feature (spec, feature thresholds), component (spec, default thresholds), or code.",
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
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        help="Name of the validation pipeline to use (e.g. validation_spec_library).",
    ),
    set_overrides: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--set",
        help="One-off override: RULE.FIELD=VALUE (e.g. S08.fail_threshold=5).",
    ),
) -> None:
    """Run validation rules against a spec or code file.

    Uses --level to determine which rule set to apply:
    - feature: Spec validation rules S01-S11 with feature-level thresholds
    - component: Spec validation rules S01-S11 with component-level thresholds (default)
    - code: Code validation rules C01-C08

    Use --pipeline to choose a specific validation pipeline by name.

    Override cascade: pipeline YAML defaults -> project DB overrides -> --set flags.
    """
    # Trigger auto-registration of built-in rules
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.executor import execute_validation_pipeline
    from specweaver.validation.pipeline_loader import load_pipeline_yaml

    target_path = Path(target)
    if not target_path.exists():
        console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    try:
        content = target_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        console.print(
            f"[red]Error:[/red] Cannot read '{target}': file is not valid UTF-8 text.",
        )
        raise typer.Exit(code=1) from None
    project_dir = Path(project) if project else None

    # Resolve pipeline name from --pipeline or --level
    if pipeline:
        pipeline_name = pipeline
    elif level == "component":
        pipeline_name = "validation_spec_default"
    elif level == "feature":
        pipeline_name = "validation_spec_feature"
    elif level == "code":
        pipeline_name = "validation_code_default"
    else:
        console.print(
            f"[red]Error:[/red] Unknown level '{level}'. Use 'feature', 'component', or 'code'.",
        )
        raise typer.Exit(code=1)

    try:
        resolved = load_pipeline_yaml(pipeline_name, project_dir=project_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Apply --set / DB overrides to pipeline step params
    settings = _load_check_settings(set_overrides)
    if settings is not None:
        from specweaver.validation.executor import apply_settings_to_pipeline
        resolved = apply_settings_to_pipeline(resolved, settings)

    results = execute_validation_pipeline(resolved, content, target_path)

    label = pipeline_name if pipeline else ("Feature" if level == "feature" else ("Code" if level == "code" else "Spec"))
    _display_results(results, f"{label} Validation: {target_path.name}")
    _print_summary(results, strict=strict)

# ---------------------------------------------------------------------------
# sw list-rules
# ---------------------------------------------------------------------------


@app.command("list-rules")
def list_rules(
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        help="Show rules for a specific pipeline only.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory (for project pipelines).",
    ),
) -> None:
    """List all validation rules, grouped by pipeline in execution order."""
    # Trigger auto-registration
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.pipeline_loader import load_pipeline_yaml

    project_dir = Path(project) if project else None

    # Determine which pipelines to show
    if pipeline:
        pipeline_names = [pipeline]
    else:
        pipeline_names = ["validation_spec_default", "validation_code_default"]

    for pname in pipeline_names:
        try:
            resolved = load_pipeline_yaml(pname, project_dir=project_dir)
        except FileNotFoundError:
            console.print(f"[yellow]Pipeline '{pname}' not found, skipping.[/yellow]")
            continue

        console.print(f"\n[bold cyan]{resolved.name}[/bold cyan]", highlight=False)
        if resolved.description:
            console.print(f"  [dim]{resolved.description.strip()}[/dim]")
        console.print()

        for i, step in enumerate(resolved.steps, 1):
            params_str = ""
            if step.params:
                params_str = "  " + " ".join(
                    f"[dim]{k}={v}[/dim]" for k, v in step.params.items()
                )
            console.print(f"  {i:>2}. [green]{step.rule}[/green]  {step.name}{params_str}")

        console.print(f"\n  [dim]{len(resolved.steps)} rules total[/dim]")


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
    selector: str = typer.Option(
        "direct",
        "--selector",
        help="Topology selector: direct, nhop, constraint, impact.",
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

    # Load topology context for the new component (best-effort)
    topo_graph = _load_topology(project_path)
    topo_contexts = _select_topology_contexts(
        topo_graph, name, selector_name=selector,
    )

    console.print(
        f"\n[bold]Drafting spec for[/bold] [cyan]{name}[/cyan]\n"
        "[dim]Answer questions below. Press Enter to skip.[/dim]\n",
    )

    result_path = asyncio.run(
        drafter.draft(name, specs_dir, topology_contexts=topo_contexts),
    )

    console.print(f"\n[green]Spec drafted:[/green] {result_path}")
    console.print("[dim]Run 'sw check' to validate the drafted spec.[/dim]")


# ---------------------------------------------------------------------------
# sw review
# ---------------------------------------------------------------------------



def _load_constitution_content(
    project_path: Path, spec_path: Path | None = None,
) -> str | None:
    """Load constitution content for the given project, or None."""
    from specweaver.project.constitution import find_constitution

    info = find_constitution(project_path, spec_path=spec_path)
    return info.content if info else None


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
    selector: str = typer.Option(
        "nhop",
        "--selector",
        help="Topology selector: direct, nhop, constraint, impact.",
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

    # Load topology context for the review target
    topo_graph = _load_topology(project_path)
    module_name = target_path.stem.removesuffix("_spec")
    topo_contexts = _select_topology_contexts(
        topo_graph, module_name, selector_name=selector,
    )

    console.print(f"\n[bold]Reviewing:[/bold] {target_path.name}")
    console.print("[dim]Sending to LLM for semantic review...[/dim]\n")

    result = _execute_review(
        reviewer, target_path, spec, topo_contexts,
        constitution=_load_constitution_content(
            project_path, spec_path=target_path,
        ),
    )
    _display_review_result(result)


def _execute_review(
    reviewer: object,
    target_path: Path,
    spec: str | None,
    topology_contexts: list | None = None,
    *,
    constitution: str | None = None,
) -> object:
    """Run the appropriate review (spec or code)."""
    if spec:
        spec_path = Path(spec)
        if not spec_path.exists():
            console.print(f"[red]Error:[/red] Spec not found: {spec}")
            raise typer.Exit(code=1)
        return asyncio.run(
            reviewer.review_code(
                target_path, spec_path,
                topology_contexts=topology_contexts,
                constitution=constitution,
            ),
        )
    return asyncio.run(
        reviewer.review_spec(
            target_path,
            topology_contexts=topology_contexts,
            constitution=constitution,
        ),
    )


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
    selector: str = typer.Option(
        "direct",
        "--selector",
        help="Topology selector: direct, nhop, constraint, impact.",
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

    # Load topology context for the implementation target
    topo_graph = _load_topology(project_path)
    module_name = spec_path.stem.removesuffix("_spec")
    topo_contexts = _select_topology_contexts(
        topo_graph, module_name, selector_name=selector,
    )

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

    # Load constitution for this project
    constitution_content = _load_constitution_content(
        project_path, spec_path=spec_path,
    )

    # Generate code
    console.print("[dim]Generating implementation code...[/dim]")
    asyncio.run(
        generator.generate_code(
            spec_path, code_path,
            topology_contexts=topo_contexts,
            constitution=constitution_content,
        ),
    )
    console.print(f"  [green]✓[/green] {code_path}")

    # Generate tests
    console.print("[dim]Generating test file...[/dim]")
    asyncio.run(
        generator.generate_tests(
            spec_path, test_path,
            topology_contexts=topo_contexts,
            constitution=constitution_content,
        ),
    )
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


@config_app.command("set-log-level")
def config_set_log_level(
    level: str = typer.Argument(
        help="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    ),
) -> None:
    """Set the log level for the active project."""
    name = _require_active_project()
    db = get_db()
    try:
        db.set_log_level(name, level)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]✓[/green] Log level set to [bold]{level.upper()}[/bold] "
        f"for project [bold]{name}[/bold].",
    )
    logger.info("Log level changed to %s for project %s", level.upper(), name)


@config_app.command("get-log-level")
def config_get_log_level() -> None:
    """Show the current log level for the active project."""
    name = _require_active_project()
    db = get_db()
    try:
        level = db.get_log_level(name)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.logging import get_log_path

    log_path = get_log_path(name)
    console.print(
        f"Log level for [bold]{name}[/bold]: [cyan]{level}[/cyan]\n"
        f"Log file: [dim]{log_path}[/dim]",
    )


@config_app.command("set-constitution-max-size")
def config_set_constitution_max_size(
    size: int = typer.Argument(
        help="Maximum constitution file size in bytes. Must be positive.",
    ),
) -> None:
    """Set the maximum allowed CONSTITUTION.md size for the active project."""
    name = _require_active_project()
    db = get_db()
    try:
        db.set_constitution_max_size(name, size)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]\u2713[/green] Constitution max size set to "
        f"[bold]{size}[/bold] bytes for project [bold]{name}[/bold].",
    )


@config_app.command("get-constitution-max-size")
def config_get_constitution_max_size() -> None:
    """Show the current constitution max size for the active project."""
    name = _require_active_project()
    db = get_db()
    try:
        max_size = db.get_constitution_max_size(name)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"Constitution max size for [bold]{name}[/bold]: "
        f"[cyan]{max_size}[/cyan] bytes",
    )


# -- Domain profile commands ------------------------------------------------


@config_app.command("profiles")
def config_profiles() -> None:
    """List all available domain profiles."""
    from specweaver.config.profiles import list_profiles

    profiles = list_profiles()

    table = Table(title="Available Domain Profiles")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Overrides", justify="right")

    for p in profiles:
        table.add_row(p.name, p.description, str(len(p.overrides)))

    console.print(table)


@config_app.command("show-profile")
def config_show_profile(
    profile_name: str = typer.Argument(help="Profile name to preview."),
) -> None:
    """Show the overrides a domain profile would apply."""
    from specweaver.config.profiles import get_profile

    profile = get_profile(profile_name)
    if profile is None:
        console.print(
            f"[red]Error:[/red] Unknown profile '{profile_name}'. "
            "Use 'sw config profiles' to list available profiles.",
        )
        raise typer.Exit(code=1)

    table = Table(title=f"Profile: {profile.name} -- {profile.description}")
    table.add_column("Rule", style="cyan")
    table.add_column("Warn", justify="right")
    table.add_column("Fail", justify="right")

    for rule_id, override in sorted(profile.overrides.items()):
        warn_str = str(override.warn_threshold) if override.warn_threshold is not None else "-"
        fail_str = str(override.fail_threshold) if override.fail_threshold is not None else "-"
        table.add_row(rule_id, warn_str, fail_str)

    console.print(table)
    console.print(
        "\n[dim]Rules not listed use code defaults.[/dim]",
    )


@config_app.command("set-profile")
def config_set_profile(
    profile_name: str = typer.Argument(help="Profile name to apply."),
) -> None:
    """Apply a domain profile to the active project.

    This clears all existing validation overrides and replaces them
    with the profile's preset values.
    """
    name = _require_active_project()
    db = get_db()
    try:
        db.set_domain_profile(name, profile_name)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.config.profiles import get_profile

    profile = get_profile(profile_name)
    count = len(profile.overrides) if profile else 0
    console.print(
        f"[green]\u2713[/green] Profile [bold]{profile_name}[/bold] applied to "
        f"project [bold]{name}[/bold] ({count} rule overrides set).",
    )


@config_app.command("get-profile")
def config_get_profile() -> None:
    """Show the active domain profile for the current project."""
    name = _require_active_project()
    db = get_db()
    try:
        profile_name = db.get_domain_profile(name)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if profile_name:
        console.print(
            f"Active profile for [bold]{name}[/bold]: "
            f"[cyan]{profile_name}[/cyan]",
        )
    else:
        console.print(
            f"[dim]No domain profile set for [bold]{name}[/bold] "
            f"(using defaults).[/dim]",
        )


@config_app.command("reset-profile")
def config_reset_profile() -> None:
    """Clear the domain profile and all validation overrides."""
    name = _require_active_project()
    db = get_db()
    try:
        db.clear_domain_profile(name)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[green]\u2713[/green] Profile and all overrides cleared "
        f"for project [bold]{name}[/bold].",
    )


# ---------------------------------------------------------------------------
# sw constitution
# ---------------------------------------------------------------------------

constitution_app = typer.Typer(
    name="constitution",
    help="Manage the project constitution (CONSTITUTION.md).",
    no_args_is_help=True,
)
app.add_typer(constitution_app, name="constitution")


@constitution_app.command("show")
def constitution_show(
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Display the current CONSTITUTION.md content."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.project.constitution import find_constitution

    info = find_constitution(project_path)
    if info is None:
        console.print(
            "[yellow]No CONSTITUTION.md found.[/yellow]\n"
            "[dim]Run 'sw constitution init' to create one.[/dim]",
        )
        raise typer.Exit(code=1)

    console.print(
        f"[bold]Constitution:[/bold] {info.path}\n"
        f"[dim]Size: {len(info.content)} bytes[/dim]\n",
    )
    console.print(info.content)


@constitution_app.command("check")
def constitution_check(
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Path to the target project directory.",
    ),
) -> None:
    """Validate the constitution against size limits."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    from specweaver.project.constitution import check_constitution, find_constitution

    info = find_constitution(project_path)
    if info is None:
        console.print(
            "[yellow]No CONSTITUTION.md found.[/yellow]\n"
            "[dim]Run 'sw constitution init' to create one.[/dim]",
        )
        raise typer.Exit(code=1)

    # Try to get the configured max size from DB
    max_size_kwargs: dict = {}
    try:
        db = get_db()
        active = db.get_active_project()
        if active:
            max_size_kwargs["max_size"] = db.get_constitution_max_size(active)
    except Exception:
        pass  # Fall back to default if DB unavailable

    errors = check_constitution(info.path, **max_size_kwargs)

    console.print(f"[bold]Constitution:[/bold] {info.path}")
    console.print(f"[dim]Size: {len(info.content)} bytes[/dim]")

    if "max_size" in max_size_kwargs:
        console.print(f"[dim]Max allowed: {max_size_kwargs['max_size']} bytes[/dim]")

    if not errors:
        console.print("\n[green]\u2713 Constitution is within size limits.[/green]")
    else:
        for err in errors:
            console.print(f"[red]\u2717[/red] {err}")
        raise typer.Exit(code=1)


@constitution_app.command("init")
def constitution_init(
    project: str | None = typer.Option(
        None, "--project", "-p",
        help="Path to the target project directory.",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite existing CONSTITUTION.md.",
    ),
) -> None:
    """Create or reset the CONSTITUTION.md template."""
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    constitution_path = project_path / "CONSTITUTION.md"

    if constitution_path.exists() and not force:
        console.print(
            "[yellow]CONSTITUTION.md already exists.[/yellow]\n"
            "[dim]Use --force to overwrite.[/dim]",
        )
        raise typer.Exit(code=1)

    if force and constitution_path.exists():
        constitution_path.unlink()

    from specweaver.project.constitution import generate_constitution

    project_name = project_path.name.lower().replace(" ", "-")
    result_path = generate_constitution(project_path, project_name)

    console.print(
        f"[green]\u2713[/green] Constitution created: [bold]{result_path}[/bold]",
    )


# ---------------------------------------------------------------------------
# sw pipelines
# ---------------------------------------------------------------------------


@app.command()
def pipelines() -> None:
    """List available pipeline templates."""
    from specweaver.flow.parser import list_bundled_pipelines

    bundled = list_bundled_pipelines()
    if not bundled:
        console.print("[dim]No pipeline templates found.[/dim]")
        return

    table = Table(title="Available Pipelines")
    table.add_column("Name", style="cyan bold")
    table.add_column("Source", style="dim")

    for name in bundled:
        table.add_row(name, "bundled")

    console.print(table)
    console.print(
        "\n[dim]Usage: sw run <pipeline> <spec_or_module>[/dim]",
    )


# ---------------------------------------------------------------------------
# sw run
# ---------------------------------------------------------------------------


_STATE_DB_PATH = Path.home() / ".specweaver" / "pipeline_state.db"


def _get_state_store():
    """Get the pipeline state store (lazy import)."""
    from specweaver.flow.store import StateStore
    return StateStore(_STATE_DB_PATH)


def _resolve_spec_path(
    pipeline_name: str,
    spec_or_module: str,
    project_path: Path,
) -> Path:
    """Resolve the spec argument based on pipeline type.

    For validate-style pipelines:  treat as direct file path.
    For new_feature-style:         treat as module name, derive spec path.
    """
    # If it looks like an existing file, use it directly
    spec_path = Path(spec_or_module)
    if spec_path.exists():
        return spec_path

    # For new_feature pipelines, derive from module name
    if pipeline_name == "new_feature":
        derived = project_path / "specs" / f"{spec_or_module}_spec.md"
        return derived

    # Try relative to project
    relative = project_path / spec_or_module
    if relative.exists():
        return relative

    # Fall back to the literal path (will fail later with clear message)
    return spec_path


def _create_display(
    *,
    use_json: bool = False,
    verbose: bool = False,
):
    """Create the appropriate display backend."""
    if use_json:
        from specweaver.flow.display import JsonPipelineDisplay
        return JsonPipelineDisplay()

    from specweaver.flow.display import RichPipelineDisplay
    return RichPipelineDisplay(console=console, verbose=verbose)


@app.command(name="run")
def run_pipeline(
    pipeline: str = typer.Argument(
        help="Pipeline name or YAML path (e.g. 'new_feature', 'validate_only').",
    ),
    spec_or_module: str = typer.Argument(
        help="Spec file path or module name (depends on pipeline type).",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the target project directory.",
    ),
    resume: str | None = typer.Option(
        None,
        "--resume",
        help="Resume a run by ID (or omit value for latest).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed handler output.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output NDJSON event stream (machine-readable).",
    ),
    selector: str = typer.Option(
        "direct",
        "--selector",
        help="Topology selector: direct, nhop, constraint, impact.",
    ),
) -> None:
    """Run a pipeline against a spec file or module.

    Load a pipeline definition and execute it step-by-step.
    Shows live progress with checkmarks for each step.

    Examples:
        sw run validate_only specs/calculator.md
        sw run new_feature greet_service
        sw run validate_only specs/calculator.md --verbose
        sw run validate_only specs/calculator.md --json
    """
    try:
        _execute_run(
            pipeline=pipeline,
            spec_or_module=spec_or_module,
            project=project,
            resume_id=resume,
            verbose=verbose,
            json_output=json_output,
            selector=selector,
        )
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Interrupted.[/yellow] "
            "[dim]Run state saved. Resume with: sw run --resume[/dim]",
        )
        raise typer.Exit(code=130) from None
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1) from None
    except Exception as exc:
        console.print(
            f"[red]Error:[/red] {type(exc).__name__}: {exc}\n"
            "[dim]Run with --verbose for full traceback.[/dim]",
        )
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1) from None


def _execute_run(  # noqa: C901
    *,
    pipeline: str,
    spec_or_module: str,
    project: str | None,
    resume_id: str | None,
    verbose: bool,
    json_output: bool,
    selector: str,
) -> None:
    """Core run logic — separated for testability."""
    from specweaver.flow.handlers import RunContext
    from specweaver.flow.parser import load_pipeline
    from specweaver.flow.runner import PipelineRunner

    # Resolve project path
    try:
        project_path = resolve_project_path(project)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Load pipeline definition
    pipeline_def = load_pipeline(Path(pipeline))

    # Resolve spec path based on pipeline type
    spec_path = _resolve_spec_path(pipeline_def.name, spec_or_module, project_path)

    # For pipelines that need an existing spec, check it exists
    spec_must_exist = pipeline_def.name not in ("new_feature",)
    if spec_must_exist and not spec_path.exists():
        console.print(f"[red]Error:[/red] Spec file not found: {spec_path}")
        raise typer.Exit(code=1)

    # Build display backend
    display = _create_display(use_json=json_output, verbose=verbose)

    # Build run context
    context = RunContext(
        project_path=project_path,
        spec_path=spec_path,
        output_dir=project_path / "src",
        constitution=_load_constitution_content(
            project_path, spec_path=spec_path,
        ),
    )

    # Wire up LLM if needed (non-validate-only pipelines)
    if pipeline_def.name != "validate_only":
        try:
            _, adapter, _gen_config = _require_llm_adapter(project_path)
            context.llm = adapter
        except (typer.Exit, SystemExit):
            if pipeline_def.name != "validate_only":
                console.print(
                    "[yellow]Warning:[/yellow] No LLM configured. "
                    "LLM-dependent steps will fail.",
                )

    # Load topology
    topo_graph = _load_topology(project_path)
    if topo_graph:
        module_name = spec_path.stem.removesuffix("_spec")
        topo_contexts = _select_topology_contexts(
            topo_graph, module_name, selector_name=selector,
        )
        context.topology = topo_contexts

    # Set up state store
    store = _get_state_store()

    # Build runner with display as event callback
    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=display,
    )

    # Initialize display
    step_info = [
        (step.name, step.description or "")
        for step in pipeline_def.steps
    ]
    display.start(pipeline_def.name, step_info)

    try:
        if resume_id is not None:
            # Resume mode
            final_run = asyncio.run(runner.resume(resume_id))
        else:
            # Fresh run
            final_run = asyncio.run(runner.run())
    except Exception:
        display.stop()
        raise
    finally:
        display.stop()

    # Exit code based on final status
    from specweaver.flow.state import RunStatus

    if final_run.status == RunStatus.FAILED:
        raise typer.Exit(code=1)
    if final_run.status == RunStatus.PARKED:
        raise typer.Exit(code=0)  # Not an error, just parked


# ---------------------------------------------------------------------------
# sw resume (convenience alias)
# ---------------------------------------------------------------------------


@app.command()
def resume(
    run_id: str | None = typer.Argument(
        None,
        help="Run ID to resume. If omitted, resumes the latest parked/failed run.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed handler output.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output NDJSON event stream (machine-readable).",
    ),
) -> None:
    """Resume a parked or failed pipeline run.

    If no run ID is given, finds the latest resumable run
    for the active project.

    Examples:
        sw resume
        sw resume abc12345-...
    """
    from specweaver.flow.handlers import RunContext
    from specweaver.flow.parser import load_pipeline
    from specweaver.flow.runner import PipelineRunner
    from specweaver.flow.state import RunStatus

    store = _get_state_store()

    if run_id is not None:
        # Explicit run ID
        run_state = store.load_run(run_id)
        if run_state is None:
            console.print(f"[red]Error:[/red] Run '{run_id}' not found.")
            raise typer.Exit(code=1)
    else:
        # Auto-detect: find latest resumable run for active project
        name = _require_active_project()
        db = get_db()
        proj = db.get_project(name)
        if not proj:
            console.print(f"[red]Error:[/red] Project '{name}' not found.")
            raise typer.Exit(code=1)

        # Try common pipeline names
        from specweaver.flow.parser import list_bundled_pipelines

        run_state = None
        for pipeline_name in list_bundled_pipelines():
            candidate = store.get_latest_run(name, pipeline_name)
            if candidate and candidate.status in (RunStatus.PARKED, RunStatus.FAILED):
                run_state = candidate
                break

        if run_state is None:
            console.print(
                "[dim]No resumable runs found for the active project.[/dim]",
            )
            raise typer.Exit(code=0)

    console.print(
        f"[bold]Resuming[/bold] run [cyan]{run_state.run_id[:8]}...[/cyan] "
        f"(pipeline: {run_state.pipeline_name}, "
        f"step {run_state.current_step + 1}/{len(run_state.step_records)})",
    )

    # Load the pipeline definition
    pipeline_def = load_pipeline(Path(run_state.pipeline_name))

    # Build context from stored state
    project_path = resolve_project_path(None)
    spec_path = Path(run_state.spec_path)

    context = RunContext(
        project_path=project_path,
        spec_path=spec_path,
        output_dir=project_path / "src",
        constitution=_load_constitution_content(
            project_path, spec_path=spec_path,
        ),
    )

    display = _create_display(use_json=json_output, verbose=verbose)

    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=display,
    )

    step_info = [
        (step.name, step.description or "")
        for step in pipeline_def.steps
    ]
    display.start(pipeline_def.name, step_info)

    try:
        final_run = asyncio.run(runner.resume(run_state.run_id))
    except KeyboardInterrupt:
        display.stop()
        console.print(
            "\n[yellow]Interrupted.[/yellow] "
            f"[dim]Resume with: sw resume {run_state.run_id}[/dim]",
        )
        raise typer.Exit(code=130) from None
    except Exception:
        display.stop()
        raise
    finally:
        display.stop()

    if final_run.status == RunStatus.FAILED:
        raise typer.Exit(code=1)
