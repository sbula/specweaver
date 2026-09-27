# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI commands for LLM cost and usage tracking."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import anyio
import typer
from rich.table import Table

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.bootstrap.llm_settings_writer import clear_model_price, set_model_price
from specweaver.core.config.llm_settings import (
    SettingsFileError,
    format_money,
    resolve_roles,
    to_usd,
)
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from specweaver.core.config.llm_settings import (
        Currency,
        LlmSettingsFiles,
        ModelFacts,
        ResolvedRole,
    )

logger = logging.getLogger(__name__)


costs_app = typer.Typer(
    name="costs",
    help="Model prices and this month's spend, in your currency.",
    invoke_without_command=True,
)
# costs_app will be mounted by main.py


@costs_app.callback(invoke_without_command=True)
def costs(ctx: typer.Context) -> None:
    """Show each model your roles use: its price per 1M tokens and this month's spend."""
    if ctx.invoked_subcommand is not None:
        return
    project = _core._require_active_project()
    files = _core.load_active_llm_settings(project)
    try:
        roles = resolve_roles(files)
    except SettingsFileError as err:
        _core.console.print("Error:", str(err), style="red", markup=False, highlight=False)
        raise typer.Exit(code=1) from err
    currency = files.machine.currency
    _say(_currency_line(currency))
    spend = _month_spend(project)
    for (model, server), role_names in sorted(_models_in_use(roles).items()):
        kind = files.machine.servers[server].kind
        facts = shipped_catalogue().facts(kind, model, files.machine.models)
        price_in = facts.usd_per_million_input if facts else None
        price_out = facts.usd_per_million_output if facts else None
        spent, unpriced = spend.get(model, (None, 0))
        month = format_money(spent or 0.0, currency) + (
            f" + {unpriced} unknown" if unpriced else ""
        )
        _say(
            f"{model}@{server} ({', '.join(role_names)}): "
            f"input {format_money(price_in, currency, places=4)}, "
            f"output {format_money(price_out, currency, places=4)} per 1M tokens"
            f" — {_price_source(model, facts, files)}; this month {month}"
        )


@costs_app.command("set")
def costs_set(
    model: str = typer.Argument(help="Model name, as a role names it."),
    input_price: float = typer.Argument(help="Price per 1M input tokens, in your currency."),
    output_price: float = typer.Argument(help="Price per 1M output tokens, in your currency."),
) -> None:
    """Set a model's price in the machine settings file.

    Example: sw costs set qwen3-coder-next 0.8 1.6
    """
    currency = _machine_currency()
    try:
        path = set_model_price(model, to_usd(input_price, currency), to_usd(output_price, currency))
    except SettingsFileError as err:
        _core.console.print("Error:", str(err), style="red", markup=False, highlight=False)
        raise typer.Exit(code=1) from err
    code = currency.code if currency else "USD"
    _say(
        f"Price for {model}: input {code} {input_price}, output {code} {output_price} per 1M tokens ({path})"
    )


@costs_app.command("reset")
def costs_reset(
    model: str = typer.Argument(help="Model whose price to remove."),
) -> None:
    """Remove a model's price from the machine settings file; the catalogue's applies again.

    Example: sw costs reset qwen3-coder-next
    """
    if clear_model_price(model):
        _say(f"Price for {model} removed; the catalogue's price applies.")
    else:
        _say(f"No price was set for {model}.")


def _say(line: str) -> None:
    _core.console.print(line, markup=False, highlight=False)


def _currency_line(currency: Currency | None) -> str:
    if currency is None:
        return "Amounts in USD — no [currency] set in the machine settings file."
    return (
        f"Amounts in {currency.code}, {currency.per_usd:g} per USD, rate of {currency.rate_date}."
    )


def _machine_currency() -> Currency | None:
    try:
        return load_llm_settings(None).machine.currency
    except SettingsFileError as err:
        _core.console.print("Error:", str(err), style="red", markup=False, highlight=False)
        raise typer.Exit(code=1) from err


def _models_in_use(roles: dict[str, ResolvedRole]) -> dict[tuple[str, str], list[str]]:
    used: dict[tuple[str, str], list[str]] = {}
    for name, setting in sorted(roles.items()):
        used.setdefault((setting.model, setting.server), []).append(name)
    return used


def _price_source(model: str, facts: ModelFacts | None, files: LlmSettingsFiles) -> str:
    own = files.machine.models.get(model)
    if own is not None and own.usd_per_million_input is not None:
        return "your settings file"
    if facts is not None and facts.usd_per_million_input is not None:
        return "catalogue"
    return "no price known"


def _month_spend(project: str) -> dict[str, tuple[float | None, int]]:
    """This calendar month's spend per model (UTC): USD known, and how many calls had no price."""
    now = datetime.now(UTC)
    since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db = _core.get_db()

    async def _read() -> list[dict[str, Any]]:
        async with db.async_session_scope() as session:
            return await LlmRepository(session).get_usage_summary(project=project, since=since)

    spend: dict[str, tuple[float | None, int]] = {}
    for row in anyio.run(_read):
        spent, unpriced = spend.get(row["model"], (None, 0))
        if row["total_cost"] is not None:
            spent = (spent or 0.0) + row["total_cost"]
        spend[row["model"]] = (spent, unpriced + (row["unpriced_calls"] or 0))
    return spend


usage_app = typer.Typer(
    name="usage",
    help="View LLM token usage statistics.",
    invoke_without_command=True,
)
# usage_app will be mounted by main.py


def _parse_since(since: str | None) -> datetime | None:
    """Validate `--since` here, where the user can be told what went wrong.

    Two failures would otherwise reach the user raw, both reading as *"telemetry is broken"* rather
    than *"the date was wrong"* — on the one command whose whole job is answering what a run cost:

    * an unparseable value raises `ValueError` from `fromisoformat`;
    * a **naive** value parses fine and dies deeper down as
      `StatementError: StrictISODateTime must be timezone-aware`, a SQLAlchemy type error. Guarding
      only the parse leaves the second one live.

    A naive value is refused rather than assumed UTC: silently choosing a timezone mis-filters by
    up to a day at the boundary, and the user cannot see that it happened.

    `fromisoformat` is kept rather than Typer's native `datetime` type, which accepts only its three
    default formats and would have rejected `2026-03-27T11:00:00+02:00` — narrowing what already
    worked in the course of fixing a crash.
    """
    if not since:
        return None
    try:
        parsed = datetime.fromisoformat(since)
    except ValueError as exc:
        _core.console.print(
            f"[red]Error:[/red] --since {since!r} is not an ISO timestamp. "
            "Try [bold]2026-08-16T00:00:00Z[/bold].",
        )
        raise typer.Exit(code=1) from exc
    if parsed.tzinfo is None:
        _core.console.print(
            f"[red]Error:[/red] --since {since!r} has no timezone, and usage records are stored "
            "with one. Add an offset — [bold]2026-08-16T00:00:00Z[/bold] or "
            "[bold]2026-08-16T00:00:00+02:00[/bold].",
        )
        raise typer.Exit(code=1)
    return parsed


@usage_app.callback(invoke_without_command=True)
def usage(
    all_projects: bool = typer.Option(
        False,
        "--all",
        help="Show usage across all projects (not just active).",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Filter records after this ISO timestamp.",
    ),
) -> None:
    """Show LLM usage summary for the active project.

    Displays token counts, estimated costs, and call counts grouped
    by task type and model.
    """
    db = _core.get_db()
    currency = _machine_currency()

    project: str | None = None
    if not all_projects:
        project = _core.run_repo_op(lambda r: r.get_active_project())
        if not project:
            _core.console.print(
                "[yellow]No active project.[/yellow] "
                "Use [bold]sw use <name>[/bold] or pass [bold]--all[/bold].",
            )
            raise typer.Exit(code=0)

    parsed_since = _parse_since(since)

    async def _get_usage() -> None:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            rows = await repo.get_usage_summary(project=project, since=parsed_since)

            code = currency.code if currency else "USD"
            if not rows:
                label = f" for [bold]{project}[/bold]" if project else ""
                _core.console.print(f"[dim]No usage data recorded{label}.[/dim]")
                return

            table = Table(
                title=f"LLM Usage — {project or 'all projects'} ({code})",
            )
            table.add_column("Task Type", style="cyan")
            table.add_column("Model")
            table.add_column("Calls", justify="right")
            table.add_column("Prompt Tokens", justify="right")
            table.add_column("Completion Tokens", justify="right")
            table.add_column("Total Tokens", justify="right")
            table.add_column(f"Cost ({code})", justify="right")
            table.add_column("Duration (s)", justify="right")

            for r in rows:
                duration_s = (r["total_duration_ms"] or 0) / 1000
                table.add_row(
                    str(r["task_type"]),
                    str(r["model"]),
                    str(r["call_count"]),
                    f"{r['total_prompt_tokens'] or 0:,}",
                    f"{r['total_completion_tokens'] or 0:,}",
                    f"{r['total_tokens'] or 0:,}",
                    _usage_cost(r, currency),
                    f"{duration_s:.1f}",
                )

            _core.console.print(table)

    anyio.run(_get_usage)


def _usage_cost(row: dict[str, Any], currency: Currency | None) -> str:
    """The row's known cost, and how many of its calls had no price — never 0 for unknown."""
    unpriced = row["unpriced_calls"] or 0
    if row["total_cost"] is None:
        return "unknown" if unpriced else format_money(0.0, currency, places=4)
    known = format_money(row["total_cost"], currency, places=4)
    return f"{known} + {unpriced} unknown" if unpriced else known
