# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A README's counts update with no person: `sw run` fills its marked block from a script.

Proves: C-EXEC-08 FR-3

| Bucket | Case |
|---|---|
| Happy | `update_counts` prints a count, run in place and in its own worktree; the block holds it, the rest of `README.md` is unchanged, the run completes |
| Boundary | not applicable — marker shapes are proven by the unit and integration tests |
| Degradation | not applicable — a file without markers is proven by the integration tests |
| Hostile | not applicable — a non-bash block step and protected files are proven by the integration tests |
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_DOCS = '[[docs.block]]\nfile = "README.md"\nname = "counts"\nstep = "update_counts"\n'
_PIPELINE = """name: counts
version: "1.0"
steps:
  - name: update_counts
    action: bash
    target: script
    use_worktree: {isolated}
    params: {{script: count.sh}}
"""
_README = "# Project\n\n<!-- sw:block counts -->\nold\n<!-- sw:end counts -->\n\nHuman text.\n"


@pytest.mark.parametrize("isolated", ["false", "true"])
@pytest.mark.usefixtures("_mock_db")
def test_the_count_lands_in_the_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated: str
) -> None:
    """With `use_worktree: true` the block reaches the repo through the merge."""
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "counts-journey", "--path", str(project)]).exit_code == 0
    (project / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    script = project / ".specweaver" / "scripts" / "count.sh"
    script.write_text('echo "**$(ls specs | wc -l) specs**"\n', encoding="utf-8")
    (project / "README.md").write_text(_README, encoding="utf-8")
    (project / "specweaver.toml").write_text(_DOCS, encoding="utf-8")
    (project / "counts.yaml").write_text(_PIPELINE.format(isolated=isolated), encoding="utf-8")
    for args in (["init"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project, check=True, capture_output=True)
    monkeypatch.chdir(project)

    result = runner.invoke(
        app, ["run", "counts.yaml", "specs/a_spec.md", "--project", str(project)]
    )

    assert result.exit_code == 0, result.output
    specs = len(list((project / "specs").iterdir()))
    assert (project / "README.md").read_text(encoding="utf-8") == _README.replace(
        "old", f"**{specs} specs**"
    )
