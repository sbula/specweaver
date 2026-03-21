# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CLI commands for validation: check, list-rules."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from specweaver.cli import _core
from specweaver.cli._helpers import _display_results, _print_summary

if TYPE_CHECKING:
    from specweaver.config.settings import ValidationSettings


def _apply_override(
    settings: ValidationSettings,
    item: str,
) -> None:
    """Parse and apply a single RULE.FIELD=VALUE override, or exit on error."""
    from specweaver.config.settings import RuleOverride

    if "=" not in item or "." not in item.split("=", 1)[0]:
        _core.console.print(
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
            _core.console.print(
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
            _core.console.print(
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
    db = _core.get_db()
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


def _resolve_pipeline_name(
    level: str,
    pipeline: str | None,
    active_project: str | None = None,
) -> str:
    """Resolve the YAML pipeline name from --pipeline, --level, or active profile.

    Precedence (highest to lowest):
    1. ``--pipeline`` flag — explicit override, always wins.
    2. ``--level feature`` — always uses feature pipeline, ignores profile.
       (Feature specs and project domains are orthogonal concerns.)
    3. Active project domain profile — auto-selects profile pipeline YAML.
    4. ``--level component`` / ``--level code`` — default YAML.

    Raises ``typer.Exit`` for unknown level values.
    """
    if pipeline:
        return pipeline
    if level == "feature":
        return "validation_spec_feature"
    if level == "code":
        return "validation_code_default"
    if level == "component":
        # Check for an active domain profile
        if active_project:
            from specweaver.config.profiles import profile_to_pipeline_name
            db = _core.get_db()
            import contextlib
            with contextlib.suppress(ValueError):
                profile_name = db.get_domain_profile(active_project)
                if profile_name:
                    return profile_to_pipeline_name(profile_name)
        return "validation_spec_default"
    from specweaver.cli import _core as _c
    _c.console.print(
        f"[red]Error:[/red] Unknown level '{level}'."
        " Use 'feature', 'component', or 'code'.",
    )
    raise typer.Exit(code=1)


def _build_result_label(level: str, pipeline: str | None, pipeline_name: str) -> str:
    """Return a human-readable label for the validation result output."""
    if pipeline:
        return pipeline_name
    if level == "feature":
        return "Feature"
    if level == "code":
        return "Code"
    return "Spec"


@_core.app.command()
def check(
    target: str = typer.Argument(
        help="Path to the spec or code file to check.",
    ),
    level: str = typer.Option(
        "component",
        "--level",
        "-l",
        help=(
            "Validation level: feature (spec, feature thresholds), "
            "component (spec, default thresholds), or code."
        ),
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
        _core.console.print(f"[red]Error:[/red] File not found: {target}")
        raise typer.Exit(code=1)

    try:
        content = target_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _core.console.print(
            f"[red]Error:[/red] Cannot read '{target}': file is not valid UTF-8 text.",
        )
        raise typer.Exit(code=1) from None
    project_dir = Path(project) if project else None

    # Determine active project for profile-aware pipeline selection
    active = _core.get_db().get_active_project()
    pipeline_name = _resolve_pipeline_name(level, pipeline, active_project=active)

    try:
        resolved = load_pipeline_yaml(pipeline_name, project_dir=project_dir)
    except FileNotFoundError as exc:
        _core.console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Apply --set / DB overrides to pipeline step params
    settings = _load_check_settings(set_overrides)
    if settings is not None:
        from specweaver.validation.executor import apply_settings_to_pipeline
        resolved = apply_settings_to_pipeline(resolved, settings)

    results = execute_validation_pipeline(resolved, content, target_path)

    label = _build_result_label(level, pipeline, pipeline_name)
    _display_results(results, f"{label} Validation: {target_path.name}")
    _print_summary(results, strict=strict)


@_core.app.command("list-rules")
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
            _core.console.print(f"[yellow]Pipeline '{pname}' not found, skipping.[/yellow]")
            continue

        _core.console.print(f"\n[bold cyan]{resolved.name}[/bold cyan]", highlight=False)
        if resolved.description:
            _core.console.print(f"  [dim]{resolved.description.strip()}[/dim]")
        _core.console.print()

        for i, step in enumerate(resolved.steps, 1):
            params_str = ""
            if step.params:
                params_str = "  " + " ".join(
                    f"[dim]{k}={v}[/dim]" for k, v in step.params.items()
                )
            _core.console.print(f"  {i:>2}. [green]{step.rule}[/green]  {step.name}{params_str}")

        _core.console.print(f"\n  [dim]{len(resolved.steps)} rules total[/dim]")
