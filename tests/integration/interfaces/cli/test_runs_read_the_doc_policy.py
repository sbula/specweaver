# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run`, `sw resume` and `sw implement` read the project's doc policy before a step runs.

Proves: C-EXEC-08 NFR-1
Proves: C-EXEC-08 FR-1

The policy rides on the run's isolation policy, where the grant and the merge read it. A broken
`[docs]` stops the command naming the file and the line, and no step runs.

| Bucket | Case |
|---|---|
| Happy | a project's `[docs]` rule is on the context `sw run` and `sw resume` start from, and on `sw implement`'s |
| Boundary | no `specweaver.toml`: the empty policy, the built-in rules |
| Degradation | not applicable — a missing file is the boundary case; a broken one is hostile |
| Hostile | an unknown access stops `sw run` and `sw implement`, naming the line; the run's step never runs |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration
runner = CliRunner()

_GOOD = '[[docs.rule]]\npaths = ["docs/user_guides/**"]\naccess = "open"\n'
_BROKEN = '[[docs.rule]]\npaths = ["docs/**"]\naccess = "wide"\n'
_PIPELINE = """name: one_step
version: "1.0"
steps:
  - name: only
    action: bash
    target: script
    params: {script: s.sh, args: ["ran"]}
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    root = tmp_path / "proj"
    root.mkdir()
    assert runner.invoke(app, ["init", "docs_proj", "--path", str(root)]).exit_code == 0
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    script = root / ".specweaver" / "scripts" / "s.sh"
    script.write_text('#!/usr/bin/env bash\necho "$1" >> steps.log\n', encoding="utf-8")
    (root / "one_step.yaml").write_text(_PIPELINE, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def _context_of(project: Path) -> Any:
    from specweaver.core.flow.engine.parser import load_pipeline
    from specweaver.core.flow.interfaces.cli import _build_run_context

    pipeline = load_pipeline(project / "one_step.yaml")
    return _build_run_context(project, project / "specs" / "greeter_spec.md", pipeline)


def test_the_run_context_carries_the_projects_rules(project: Path) -> None:
    (project / "specweaver.toml").write_text(_GOOD, encoding="utf-8")

    rules = _context_of(project).isolation.doc_policy.rule

    assert [(rule.paths, rule.access) for rule in rules] == [(["docs/user_guides/**"], "open")]


def test_no_settings_file_is_the_empty_policy(project: Path) -> None:
    assert _context_of(project).isolation.doc_policy.rule == []


def test_a_broken_docs_section_stops_sw_run_naming_the_line(project: Path) -> None:
    (project / "specweaver.toml").write_text(_BROKEN, encoding="utf-8")

    result = runner.invoke(
        app, ["run", "one_step.yaml", "specs/greeter_spec.md", "--project", str(project)]
    )

    assert result.exit_code == 1, result.output
    assert shows(result.output, "docs.rule.0.access")
    assert shows(result.output, "specweaver.toml:3:")
    assert not (project / "steps.log").exists()


def _implement(project: Path) -> Any:
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.core.flow.engine.state import RunStatus

    adapter = MagicMock()
    adapter.available.return_value = True
    adapter.generate = AsyncMock()
    with (
        doubled_llm(adapter),
        patch(
            "specweaver.core.config.bootstrap.settings_loader.load_settings",
            return_value=SpecWeaverSettings(),
        ),
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class,
    ):
        state = MagicMock()
        state.status = RunStatus.COMPLETED
        state.step_records = []
        runner_class.return_value.run = AsyncMock(return_value=state)
        result = runner.invoke(
            app, ["implement", "specs/greeter_spec.md", "--project", str(project)]
        )
    return result, runner_class


def test_sw_implement_carries_the_projects_rules(project: Path) -> None:
    (project / "specweaver.toml").write_text(_GOOD, encoding="utf-8")

    result, runner_class = _implement(project)

    assert runner_class.called, result.output
    rules = runner_class.call_args.args[1].isolation.doc_policy.rule
    assert [rule.access for rule in rules] == ["open"]


def test_a_broken_docs_section_stops_sw_implement(project: Path) -> None:
    (project / "specweaver.toml").write_text(_BROKEN, encoding="utf-8")

    result, runner_class = _implement(project)

    assert result.exit_code == 1, result.output
    assert shows(result.output, "docs.rule.0.access")
    assert not runner_class.called
