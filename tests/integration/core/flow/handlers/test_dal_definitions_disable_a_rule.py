# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's own `dal_definitions.yaml` decides which rules run against it.

Proves: C-VAL-03 FR-4

FR-4's outcome is *"rules can be augmented or disabled (`Rule_X: null`)"*. Its citation stopped one
layer short of that: `test_dal_merge.py` writes the file, loads settings, and asserts the override
was **parsed and attached** — `is_enabled("S01") is False` on a settings object. Nothing asserted the
rule then fails to run.

That is `TECH-041`'s thesis, which named this capability: *proven link by link, never as a chain*.
The links are real — the loader reads the file, `_resolve_merged_settings` merges the tier's
constraints over the settings, and the executor honours `enabled` — and no test crossed them.

Measured 2026-08-19 before this was written: the same module validates against 10 rules with no
`dal_definitions.yaml` and 9 with one disabling `C08`. So the chain works; it was unproven.

**Both directions are asserted.** A merge that dropped every override would satisfy a
"C08 is absent" test only if the rule vanished for another reason, and a pipeline that ran nothing
would satisfy it trivially.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import yaml

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.bootstrap.settings_loader import load_settings
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

#: Disabled for the tier the fixture declares. `C08` is a pure-AST rule with no toolchain of its own,
#: so its absence is the override rather than an environment difference.
DISABLED_RULE = "C08"

SOURCE = '''"""A widget."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''


def _project(tmp_path: Path, *, disable: bool) -> Path:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / ".specweaver").mkdir()
    (root / "src" / "context.yaml").write_text(
        "name: widget\npurpose: Adds numbers.\narchetype: pure-logic\n"
        "operational:\n  dal_level: DAL_E\n",
        encoding="utf-8",
    )
    (root / "src" / "widget.py").write_text(SOURCE, encoding="utf-8")
    (root / "tests" / "test_widget.py").write_text(
        "def test_add():\n    assert True\n", encoding="utf-8"
    )
    # Named for the module: C02 derives the expected test file from the SPEC stem.
    (root / "widget.md").write_text("# Widget\n", encoding="utf-8")
    if disable:
        (root / ".specweaver" / "dal_definitions.yaml").write_text(
            yaml.dump(
                {
                    "matrix": {
                        "DAL_E": {
                            "overrides": {
                                DISABLED_RULE: {"rule_id": DISABLED_RULE, "enabled": False}
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
    return root


async def _rules_that_ran(tmp_path: Path, *, disable: bool) -> list[str]:
    root = _project(tmp_path, disable=disable)
    bootstrap_database(str(root / "state.db"))
    db = Database(root / "state.db")
    register_test_project(db, "demo", str(root))

    context = RunContext(project_path=root, spec_path=root / "widget.md")
    context.settings = load_settings(db, "demo")
    step = PipelineStep(
        name="validate_code",
        action=StepAction.VALIDATE,
        target=StepTarget.CODE,
        params={"target": "src/widget.py"},
    )

    result: Any = await ValidateCodeHandler().execute(step, context)
    return [row["rule_id"] for row in result.output.get("results", [])]


async def test_a_disabled_rule_does_not_run(tmp_path: Path) -> None:
    ran = await _rules_that_ran(tmp_path, disable=True)

    assert DISABLED_RULE not in ran, ran


async def test_without_the_override_the_same_rule_runs(tmp_path: Path) -> None:
    """The control. Without it, a rule absent for any other reason reads as the override working."""
    ran = await _rules_that_ran(tmp_path, disable=False)

    assert DISABLED_RULE in ran, ran


async def test_only_that_rule_is_removed(tmp_path: Path) -> None:
    """A merge that emptied the pipeline would satisfy both tests above."""
    with_override = await _rules_that_ran(tmp_path / "on", disable=True)
    without = await _rules_that_ran(tmp_path / "off", disable=False)

    assert set(without) - set(with_override) == {DISABLED_RULE}
