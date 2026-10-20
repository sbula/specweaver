# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run` refuses an agentic step on a project that never named its agentic ceiling.

Proves: C-FLOW-11 FR-2

| Bucket | Case |
|---|---|
| Happy | not applicable — an agentic run with a ceiling needs the coder, proven by `SF-02` |
| Boundary | not applicable — the shapes of the policy are proven by the unit tests |
| Degradation | not applicable — a broken `[autonomy]` is proven by the run-root tests |
| Hostile | `mode: agentic` with no `agentic_max_dal`: exit 1, the setting named, the step before it never ran |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_PIPELINE = """name: agentic_code
version: "1.0"
steps:
  - name: first
    action: bash
    target: script
    params: {script: s.sh}
  - name: write_code
    action: generate
    target: code
    mode: agentic
"""


@pytest.mark.usefixtures("_mock_db")
def test_an_agentic_step_without_a_ceiling_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "no-ceiling", "--path", str(project)]).exit_code == 0
    (project / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    script = project / ".specweaver" / "scripts" / "s.sh"
    script.write_text("echo ran >> steps.log\n", encoding="utf-8")
    (project / "specweaver.toml").write_text('[autonomy]\nmode = "oneshot"\n', encoding="utf-8")
    (project / "agentic_code.yaml").write_text(_PIPELINE, encoding="utf-8")
    monkeypatch.chdir(project)

    model = MagicMock()
    model.available.return_value = True
    model.generate = AsyncMock()
    with doubled_llm(model):
        result = runner.invoke(
            app, ["run", "agentic_code.yaml", "specs/a_spec.md", "--project", str(project)]
        )

    assert result.exit_code == 1, result.output
    assert shows(result.output, "[autonomy] agentic_max_dal")
    assert not (project / "steps.log").exists()
