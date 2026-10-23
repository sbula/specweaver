# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A CLI command's model options: `--model`, and the missing-calls line at its end."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import click
import typer
from pydantic import ValidationError
from rich.console import Console

from specweaver.core.config.llm_settings import RoleEntry
from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.router import ModelRouter

logger = logging.getLogger(__name__)


def run_model_option(value: str | None) -> RoleEntry | None:
    """The `--model <model@server>` value; a malformed one stops the command before any call."""
    if value is None:
        return None
    try:
        return RoleEntry.model_validate(value)
    except ValidationError as err:
        message = err.errors()[0]["msg"].removeprefix("Value error, ")
        _core.console.print(f"Error: --model {value}: {message}", style="red", markup=False)
        raise typer.Exit(code=1) from err


def tell_missing_at_end(router: ModelRouter) -> ModelRouter:
    """At the command's end, also after an exit, say on stderr how many calls the ledger misses."""
    context = click.get_current_context(silent=True)
    if context is not None:
        context.call_on_close(lambda: _tell_missing(router))
    return router


def _tell_missing(router: ModelRouter) -> None:
    try:
        missing = router.unwritten()
    except Exception:
        logger.warning("Could not count the calls missing from the cost ledger")
        return
    if missing:
        calls = (
            "1 call of this command is" if missing == 1 else f"{missing} calls of this command are"
        )
        was = "was" if missing == 1 else "were"
        Console(stderr=True).print(
            f"{calls} missing from the cost ledger or {was} not closed in it; "
            "sw usage and sw costs do not show their full spend.",
            style="yellow",
            markup=False,
            highlight=False,
        )
