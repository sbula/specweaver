# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""HITL interactive reviewer for auto-discovered coding standards.

Provides a Rich-based combined review where the user can Accept, Edit,
or Reject each category across all scopes in one session.

Usage::

    from specweaver.standards.reviewer import StandardsReviewer

    reviewer = StandardsReviewer()
    accepted = reviewer.review(scope_results, existing=old_standards)
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

if TYPE_CHECKING:
    from specweaver.standards.analyzer import CategoryResult

logger = logging.getLogger(__name__)


class StandardsReviewer:
    """Rich interactive reviewer for standards HITL.

    Presents a combined review table for all scopes, with per-category
    actions: ``a`` (Accept), ``e`` (Edit JSON), ``r`` (Reject),
    ``A`` (Accept All), ``S`` (Skip scope).
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    def review(
        self,
        scope_results: dict[str, list[CategoryResult]],
        *,
        existing: dict[str, list[dict[str, object]]],
    ) -> dict[str, list[CategoryResult]]:
        """Run combined HITL review across all scopes.

        Args:
            scope_results: Map of scope name → list of CategoryResults.
            existing: Map of scope name → list of existing DB records
                (dicts with ``category``, ``data``, ``confidence``,
                ``confirmed_by``).

        Returns:
            Map of scope name → list of accepted/edited CategoryResults.
            Rejected categories are excluded.
        """
        if not scope_results:
            return {}

        accepted: dict[str, list[CategoryResult]] = {}

        for scope in sorted(scope_results):
            results = scope_results[scope]
            scope_existing = existing.get(scope, [])
            scope_accepted: list[CategoryResult] = []

            # Build lookup of existing by category
            existing_by_cat: dict[str, dict[str, object]] = {
                str(e["category"]): e for e in scope_existing
            }

            skip_scope = False

            for result in results:
                if skip_scope:
                    break

                # Auto-accept if unchanged AND already HITL-confirmed
                if self._should_auto_accept(result, existing_by_cat):
                    scope_accepted.append(result)
                    continue

                # Show diff if re-scan
                old = existing_by_cat.get(result.category)
                if old:
                    self._show_diff(scope, result.category, old, result)

                # Show the result table
                self._show_category(scope, result)

                # Prompt for action
                action = self._prompt_action()
                stop = self._handle_result_action(
                    action, result, results, scope_accepted,
                )
                if stop == "skip_scope":
                    skip_scope = True

            accepted[scope] = scope_accepted

        return accepted

    def _should_auto_accept(
        self, result: CategoryResult, existing_by_cat: dict[str, dict[str, object]],
    ) -> bool:
        """Check if a result is unchanged and already HITL-confirmed."""
        old = existing_by_cat.get(result.category)
        if not old or old.get("confirmed_by") != "hitl":
            return False
        old_data = (
            json.loads(old["data"])
            if isinstance(old["data"], str)
            else old["data"]
        )
        return bool(old_data == result.dominant)

    def _handle_result_action(
        self,
        action: str,
        result: CategoryResult,
        all_results: list[CategoryResult],
        scope_accepted: list[CategoryResult],
    ) -> str | None:
        """Process user action on a result. Returns 'skip_scope' to stop."""
        if action == "a":
            scope_accepted.append(result)
        elif action == "A":
            # Accept all remaining in this scope
            scope_accepted.append(result)
            idx = all_results.index(result)
            scope_accepted.extend(all_results[idx + 1:])
            return "skip_scope"  # Break out of inner loop
        elif action == "e":
            edited = self._edit_data(result)
            scope_accepted.append(edited)
        elif action == "r":
            pass  # Rejected — skip
        elif action == "S":
            return "skip_scope"
        return None

    def _show_category(
        self, scope: str, result: CategoryResult,
    ) -> None:
        """Display a single category result."""
        table = Table(title=f"Scope: {scope}")
        table.add_column("Category", style="green")
        table.add_column("Dominant")
        table.add_column("Confidence", justify="right")

        patterns = ", ".join(f"{k}={v}" for k, v in result.dominant.items())

        # UI Enhancement: Append color-coded text for deviations
        if result.conflicts:
            issues = " ".join(result.conflicts)
            patterns += f"\n[red]⚠️ Deviation: {issues}[/red]"

        table.add_row(result.category, patterns, f"{result.confidence:.0%}")
        self._console.print(table)

    def _show_diff(
        self,
        scope: str,
        category: str,
        old: dict[str, object],
        new: CategoryResult,
    ) -> None:
        """Show what changed between old and new standards."""
        old_data = (
            json.loads(old["data"])
            if isinstance(old["data"], str)
            else old["data"]
        )
        self._console.print(f"\n[bold]Diff for [{scope}/{category}]:[/bold]")
        self._console.print(f"  [red]Old: {old_data}[/red]")
        self._console.print(f"  [green]New: {new.dominant}[/green]")

    def _prompt_action(self) -> str:
        """Prompt the user for an action."""
        return Prompt.ask(
            "[a]ccept / [e]dit / [r]eject / [A]ccept All / [S]kip scope",
            choices=["a", "e", "r", "A", "S"],
            default="a",
        )

    def _edit_data(self, result: CategoryResult) -> CategoryResult:
        """Prompt user to edit the JSON data dict.

        Retries on invalid JSON until valid input is provided.

        Returns:
            New CategoryResult with updated dominant dict.
        """
        current_json = json.dumps(result.dominant)
        self._console.print(f"[dim]Current: {current_json}[/dim]")

        while True:
            raw = Prompt.ask("Enter new JSON data")
            try:
                new_data = json.loads(raw)
                if not isinstance(new_data, dict):
                    self._console.print("[red]Must be a JSON object (dict).[/red]")
                    continue
                return replace(result, dominant=new_data)
            except json.JSONDecodeError:
                self._console.print("[red]Invalid JSON. Try again.[/red]")
