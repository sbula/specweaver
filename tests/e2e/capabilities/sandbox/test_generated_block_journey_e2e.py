# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A README's counts update with no person: `sw run` fills its marked block from a script.

Proves: C-EXEC-08 FR-3

| Bucket | Case |
|---|---|
| Happy | `update_counts` prints a count; the block holds it, the rest of `README.md` is unchanged, the run completes |
| Boundary | not applicable — marker shapes are proven by the unit and integration tests |
| Degradation | not applicable — a file without markers is proven by the integration tests |
| Hostile | not applicable — a non-bash block step and protected files are proven by the integration tests |
"""

from __future__ import annotations

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
    params: {script: count.sh}
"""
_README = "# Project\n\n<!-- sw:block counts -->\nold\n<!-- sw:end counts -->\n\nHuman text.\n"


@pytest.mark.usefixtures("_mock_db")
def test_the_count_lands_in_the_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "counts-journey", "--path", str(project)]).exit_code == 0
    (project / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    script = project / ".specweaver" / "scripts" / "count.sh"
    script.write_text('echo "**$(ls specs | wc -l) specs**"\n', encoding="utf-8")
    (project / "README.md").write_text(_README, encoding="utf-8")
    (project / "specweaver.toml").write_text(_DOCS, encoding="utf-8")
    (project / "counts.yaml").write_text(_PIPELINE, encoding="utf-8")
    monkeypatch.chdir(project)

    result = runner.invoke(
        app, ["run", "counts.yaml", "specs/a_spec.md", "--project", str(project)]
    )

    assert result.exit_code == 0, result.output
    specs = len(list((project / "specs").iterdir()))
    assert (project / "README.md").read_text(encoding="utf-8") == _README.replace(
        "old", f"**{specs} specs**"
    )
