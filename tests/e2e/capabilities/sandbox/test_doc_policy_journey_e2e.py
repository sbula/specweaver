# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's `[docs]` rules decide which step may change which doc, through `sw run`.

Proves: C-EXEC-08 FR-1
Proves: C-EXEC-08 FR-7
Proves: C-EXEC-08 FR-8

Two `bash` steps, each in its own worktree. `update_api_docs` is named by a `step` rule and its doc
lands; `other` changes `README.md`, which stays human: the change is kept as a proposal and the run
completes.

| Bucket | Case |
|---|---|
| Happy | the named step's `docs/api/x.md` lands |
| Boundary | not applicable — the rule shapes are proven by the policy and merge tests |
| Degradation | not applicable — a broken `[docs]` is proven by the run-root tests |
| Hostile | another step's `README.md` change does not land; it is in `doc_updates.md`, and the run completes |
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(shutil.which("git") is None, reason="git required"),
]

_DOCS = '[[docs.rule]]\npaths = ["docs/api/**"]\naccess = "step"\nsteps = ["update_api_docs"]\n'
_PIPELINE = """name: docs_journey
version: "1.0"
steps:
  - name: update_api_docs
    action: bash
    target: script
    use_worktree: true
    params: {script: api.sh}
  - name: other
    action: bash
    target: script
    use_worktree: true
    params: {script: readme.sh}
"""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.usefixtures("_mock_db")
def test_the_named_step_lands_its_doc_and_another_steps_readme_is_proposed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "docs-journey", "--path", str(project)]).exit_code == 0
    (project / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    scripts = project / ".specweaver" / "scripts"
    (scripts / "api.sh").write_text("mkdir -p docs/api\necho api > docs/api/x.md\n")
    (scripts / "readme.sh").write_text("echo changed > README.md\n")
    (project / "README.md").write_text("seed\n", encoding="utf-8")
    (project / "specweaver.toml").write_text(_DOCS, encoding="utf-8")
    (project / "docs_journey.yaml").write_text(_PIPELINE, encoding="utf-8")
    _git(project, "init")
    _git(project, "config", "user.email", "t@t")
    _git(project, "config", "user.name", "t")
    _git(project, "add", "-A")
    _git(project, "commit", "-m", "init")
    monkeypatch.chdir(project)

    result = runner.invoke(
        app, ["run", "docs_journey.yaml", "specs/a_spec.md", "--project", str(project)]
    )

    assert result.exit_code == 0, result.output
    assert (project / "docs" / "api" / "x.md").read_text(encoding="utf-8") == "api\n"
    assert (project / "README.md").read_text(encoding="utf-8") == "seed\n"
    proposals = (project / "doc_updates.md").read_text(encoding="utf-8")
    assert "README.md" in proposals
    assert "+changed" in proposals
