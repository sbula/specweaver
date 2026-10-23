# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw draft` is a command of the drafting workflow, under the same name.

Proves: TECH-077 FR-11

| Bucket | Case |
|---|---|
| Happy | `sw draft` is registered from the drafting workflow's CLI |
| Boundary | the review CLI no longer defines it |
| Degradation | not applicable — registration either happens or does not |
| Hostile | not applicable — no input reaches registration |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import typer

pytestmark = pytest.mark.integration


def _names(app: typer.Typer) -> set[str]:
    return {command.name for command in app.registered_commands}


def test_draft_is_a_drafting_command() -> None:
    from specweaver.workflows.drafting.interfaces.cli import drafting_cli

    assert "draft" in _names(drafting_cli)


def test_the_review_cli_no_longer_defines_draft() -> None:
    from specweaver.workflows.review.interfaces.cli import review_cli

    assert "draft" not in _names(review_cli)
    assert "review" in _names(review_cli)


def test_sw_draft_is_still_a_command() -> None:
    from typer.testing import CliRunner

    from specweaver.interfaces.cli.main import app

    result = CliRunner().invoke(app, ["draft", "--help"])

    assert result.exit_code == 0, result.output
