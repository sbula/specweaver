# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What `sw run` shows at its end: whose tests cover each requirement, and spec problems found."""

from __future__ import annotations

from typing import Any

from rich.markup import escape

from specweaver.interfaces.cli import _core

_COVERED_BY = {"both": "both", "coder": "coder only", "scenario": "scenario only"}


def _outputs(final_run: Any) -> list[dict[str, Any]]:
    return [record.result.output or {} for record in final_run.step_records if record.result]


def show_coverage(final_run: Any) -> None:
    """Per requirement, whose tests cover it, from the last step that reported it."""
    reports = [output.get("requirement_coverage") for output in _outputs(final_run)]
    coverage = next((report for report in reversed(reports) if report), None)
    if not coverage:
        return
    _core.console.print("[bold]Test coverage per requirement[/bold]")
    for rid, side in coverage.items():
        _core.console.print(f"  {escape(str(rid))}  {_COVERED_BY.get(side, 'none')}")


def show_problems(final_run: Any) -> None:
    """The spec or contract problems the scenario agent named, each once."""
    problems = list(
        dict.fromkeys(
            str(p) for output in _outputs(final_run) for p in output.get("problems") or []
        )
    )
    if not problems:
        return
    _core.console.print("[bold]Spec or contract problems the scenario agent found[/bold]")
    for problem in problems:
        _core.console.print(f"  - {escape(problem)}")


def show_models(final_run: Any) -> None:
    """A dual run whose two sides could not be told to use different models."""
    for output in _outputs(final_run):
        if output.get("one_model"):
            model = escape(str(output["one_model"]))
            _core.console.print(
                f"[yellow]Both sides used one model, {model}: the settings name only one.[/yellow]"
            )
            return
        if output.get("models") == "unknown":
            _core.console.print("[yellow]The models of the two sides are unknown.[/yellow]")
            return


def show_acceptance(report: dict[str, Any]) -> None:
    """The kept scenario checks: what passed, which requirements failed, which sets are stale."""
    from specweaver.core.flow.handlers.acceptance import acceptance_lines

    for line in acceptance_lines(report):
        _core.console.print(line)


def show_run_summary(final_run: Any) -> None:
    show_coverage(final_run)
    show_problems(final_run)
    show_models(final_run)
    for output in _outputs(final_run):
        show_acceptance(output.get("acceptance") or {})
