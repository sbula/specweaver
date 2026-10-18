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
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.price_refresh import SOURCE, refresh_prices
from specweaver.infrastructure.llm.price_store import price_book
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from specweaver.core.config.llm_settings import (
        Currency,
        ResolvedRole,
    )
    from specweaver.infrastructure.llm.prices import Price, PriceBook

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
    _say(_catalogue_line(shipped_catalogue().checked))
    spend = _month_spend(project)
    db = _core.get_db()
    for (model, server), role_names in sorted(_models_in_use(roles).items()):
        book = price_book(
            db,
            shipped_catalogue(),
            server_name=server,
            server=files.machine.servers[server],
            model=model,
            overrides=files.machine.models,
        )
        price_in, price_out = (book.default(TokenKind.INPUT), book.default(TokenKind.OUTPUT))
        spent, unpriced = spend.get((model, server), (None, 0))
        _say(
            f"{model}@{server} ({', '.join(role_names)}): "
            f"input {format_money(_usd(price_in), currency, places=4)}, "
            f"output {format_money(_usd(price_out), currency, places=4)} per 1M tokens"
            f" — {_price_source(price_in)}{_cached_note(book)}; this month "
            f"{_month(spent, unpriced, currency)}"
        )
    for (old_model, where), (old_spent, old_unpriced) in sorted(
        spend.items(), key=lambda item: item[0][0]
    ):
        if where is None:  # recorded before the server was stored
            month = _month(old_spent, old_unpriced, currency)
            _say(f"{old_model}, server not recorded: this month {month}")
    for line in _status_lines(_status_totals(project, _month_start()), currency):
        _say(line)


def _month(spent: float | None, unpriced: int, currency: Currency | None) -> str:
    return format_money(spent or 0.0, currency) + (f" + {unpriced} unknown" if unpriced else "")


def _amount(totals: dict[str, Any], currency: Currency | None) -> str:
    """Known money, and how many calls had none; all unknown stays `unknown`, never 0."""
    unpriced = totals["unpriced_calls"] or 0
    if totals["cost"] is None:
        return "unknown"
    known = format_money(totals["cost"], currency)
    return f"{known} + {unpriced} unknown" if unpriced else known


def _calls(n: int) -> str:
    return f"{n} call" if n == 1 else f"{n} calls"


def _status_lines(totals: dict[str, dict[str, Any]], currency: Currency | None) -> list[str]:
    """Failed calls, which the totals hold; unfinished ones, which they do not."""
    lines = []
    if failed := totals.get("failed"):
        lines.append(f"  of which failed: {_calls(failed['calls'])}, {_amount(failed, currency)}")
    if pending := totals.get("pending"):
        lines.append(
            "  not finished (running now, or the process was killed): "
            f"{_calls(pending['calls'])}, at most {pending['tokens'] or 0:,} tokens, "
            f"{_amount(pending, currency)}"
        )
    return lines


def _status_totals(project: str | None, since: datetime | None) -> dict[str, dict[str, Any]]:
    db = _core.get_db()

    async def _read() -> dict[str, dict[str, Any]]:
        async with db.async_session_scope() as session:
            return await LlmRepository(session).get_status_totals(project, since)

    return anyio.run(_read)


def _month_start() -> datetime:
    """The start of this calendar month, UTC."""
    return datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


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
        _core.refuse_llm_settings(err)
    code = currency.code if currency else "USD"
    _say(
        f"Price for {model}: input {code} {input_price}, output {code} {output_price} per 1M tokens ({path})"
    )


@costs_app.command("refresh")
def costs_refresh() -> None:
    """Fetch the prices of the models your roles use from models.dev now, and say what changed.

    A command that calls a model does this by itself once a day.
    """
    project = _core._require_active_project()
    files = _core.load_active_llm_settings(project)
    result = refresh_prices(_core.get_db(), files, force=True)
    for line in result.changes:
        _say(f"Changed: {line}")
    for line in result.problems:
        _say(f"Not refreshed: {line}")
    if not result.changes and not result.problems:
        _say("No price changed.")


@costs_app.command("reset")
def costs_reset(
    model: str = typer.Argument(help="Model whose price to remove."),
) -> None:
    """Remove a model's price from the machine settings file; the catalogue's applies again.

    Example: sw costs reset qwen3-coder-next
    """
    try:
        cleared = clear_model_price(model)
    except SettingsFileError as err:
        _core.refuse_llm_settings(err)
    if cleared:
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


def _currency_or_usd() -> Currency | None:
    """The currency to show past spend in; a broken settings file must not hide that spend."""
    try:
        return load_llm_settings(None).machine.currency
    except SettingsFileError as err:
        _core.console.print(
            f"Settings file not read ({err}); amounts are in USD.",
            style="yellow",
            markup=False,
            highlight=False,
        )
        return None


def _models_in_use(roles: dict[str, ResolvedRole]) -> dict[tuple[str, str], list[str]]:
    used: dict[tuple[str, str], list[str]] = {}
    for name, setting in sorted(roles.items()):
        used.setdefault((setting.model, setting.server), []).append(name)
    return used


def _catalogue_line(checked: str) -> str:
    return f"Prices from the shipped list, checked {checked}."


def _usd(price: Price | None) -> float | None:
    return price.usd_per_million if price else None


def _cached_note(book: PriceBook) -> str:
    """Says so when a hosted model's cached reads have no price of their own."""
    if book.local or book.current(TokenKind.CACHED_READ):
        return ""
    return ", cached reads billed as input"


def _price_source(price: Price | None) -> str:
    if price is None:
        return "no price known"
    return {"settings": "your settings file", SOURCE: SOURCE}.get(price.source, "catalogue")


def _month_spend(project: str) -> dict[tuple[str, str | None], tuple[float | None, int]]:
    """This calendar month's spend per model and server (UTC): USD known, and calls with no price."""
    since = _month_start()
    db = _core.get_db()

    async def _read() -> list[dict[str, Any]]:
        async with db.async_session_scope() as session:
            return await LlmRepository(session).get_spend_by_server(project, since)

    return {
        (row["model"], row["server"]): (row["total_cost"], row["unpriced_calls"] or 0)
        for row in anyio.run(_read)
    }


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
    currency = _currency_or_usd()

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
            table.add_column("Task", style="cyan")
            table.add_column("Model")
            table.add_column("Calls", justify="right")
            table.add_column("Prompt", justify="right")
            table.add_column("Cached", justify="right")
            table.add_column("Output", justify="right")
            table.add_column("Total", justify="right")
            table.add_column(f"Cost ({code})", justify="right")
            table.add_column("Secs", justify="right")

            for r in rows:
                duration_s = (r["total_duration_ms"] or 0) / 1000
                table.add_row(
                    str(r["task_type"]),
                    str(r["model"]),
                    str(r["call_count"]),
                    f"{r['total_prompt_tokens'] or 0:,}",
                    _cached_cell(r),
                    f"{r['total_completion_tokens'] or 0:,}",
                    f"{r['total_tokens'] or 0:,}",
                    _usage_cost(r, currency),
                    f"{duration_s:.1f}",
                )

            _core.console.print(table)

    anyio.run(_get_usage)
    for line in _status_lines(_status_totals(project, parsed_since), currency):
        _core.console.print(line, markup=False, highlight=False)


def _cached_cell(row: dict[str, Any]) -> str:
    """The prompt tokens the group read from a cache, and how many calls did not say — never 0."""
    unknown = row.get("unknown_cached") or 0
    if row.get("total_cached") is None:
        return "unknown"
    known = f"{row['total_cached']:,}"
    return f"{known} + {unknown} unknown" if unknown else known


def _usage_cost(row: dict[str, Any], currency: Currency | None) -> str:
    """The row's known cost, and how many of its calls had no price — never 0 for unknown.

    A local call with no price costs *not applicable*, which is not unknown.
    """
    unpriced = row["unpriced_calls"] or 0
    if row["total_cost"] is None:
        if unpriced:
            return "unknown"
        return "n/a" if row.get("local_calls") else format_money(0.0, currency, places=4)
    known = format_money(row["total_cost"], currency, places=4)
    return f"{known} + {unpriced} unknown" if unpriced else known
