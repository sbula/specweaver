# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A saved run answers *which criteria judged this verdict* — long after the run, from the run alone.

Proves: C-VAL-05 FR-4

`sw run` with a one-step review pipeline; only the model is doubled. The run is read back from the
real state store, as `GET /runs/<id>` and an audit would read it.

| Bucket | Case |
|---|---|
| Happy | the saved review step names the project's own rubric, its version and its checksum |
| Boundary | not applicable — which file wins is proven by the loader's tests |
| Degradation | not applicable — a missing rubric failing the step is proven by the seam's tests |
| Hostile | not applicable — the rubric is the project's own file |
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.core.config.paths import state_db_path
from specweaver.core.flow.engine.store import StateStore
from specweaver.interfaces.cli.main import app
from tests.scripted_llm import ScriptedLLM, doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_PIPELINE = """\
name: review_only
steps:
  - name: review_spec
    action: review
    target: spec
"""
_CRITERIA = "Every requirement names its owner.\n"


@pytest.mark.usefixtures("_mock_db")
def test_the_saved_run_names_the_rubric_that_judged_it(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "audited", "--path", str(project)]).exit_code == 0
    (project / "specs").mkdir(exist_ok=True)
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    rubrics = project / ".specweaver" / "rubrics"
    rubrics.mkdir(parents=True, exist_ok=True)
    (rubrics / "spec_review.md").write_text(f"---\nid: spec_review\nversion: 4\n---\n{_CRITERIA}")
    (project / "review_only.yaml").write_text(_PIPELINE, encoding="utf-8")

    with doubled_llm(ScriptedLLM(["VERDICT: ACCEPTED\n- Fine [confidence: 90]\nFine."])):
        done = runner.invoke(
            app,
            [
                "run",
                str(project / "review_only.yaml"),
                str(project / "specs" / "greeter_spec.md"),
                "--project",
                str(project),
            ],
        )

    assert done.exit_code == 0, done.output
    run = StateStore(state_db_path()).get_latest_run("audited", "review_only")
    assert run is not None
    assert run.step_records[0].result.output["rubric"] == {
        "id": "spec_review",
        "version": "4",
        "checksum": hashlib.sha256(_CRITERIA.encode("utf-8")).hexdigest(),
        "source": str(rubrics / "spec_review.md"),
    }
