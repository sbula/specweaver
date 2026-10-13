# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's domain profile sets the spec limits in `sw check` and in a run alike.

Proves: C-VAL-02 FR-6

`library` fails S08 above 5 weasel words, the default above 8; the 9-word spec names the limit used.

| Bucket | Case |
|---|---|
| Happy | `sw run validate_only` uses the profile, as `sw check` does |
| Boundary | `--pipeline` still wins over the profile |
| Degradation | not applicable — a project without a profile is the default path |
| Hostile | `sw check --project B` uses B's profile, not the active project's |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e
runner = CliRunner()

_WEASEL = (
    "# A\n\n## 1. Purpose\n\nIt should work properly and efficiently, with reasonable and "
    "adequate speed, seamlessly. It might, could or may be fast.\n"
)


def _project(root: Path, name: str, profile: str | None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    assert runner.invoke(app, ["init", name, "--path", str(root)]).exit_code == 0
    if profile:
        assert runner.invoke(app, ["config", "set-profile", profile]).exit_code == 0
    spec = root / "specs" / "a_spec.md"
    spec.write_text(_WEASEL, encoding="utf-8")
    return spec


def test_a_run_uses_the_profile(tmp_path: Path) -> None:
    spec = _project(tmp_path, "prof-run", "library")

    result = runner.invoke(
        app, ["run", "validate_only", str(spec), "--json", "--project", str(tmp_path)]
    )

    s08 = [
        r
        for line in result.output.splitlines()
        if line.startswith("{") and '"S08"' in line
        for r in json.loads(line).get("result", {}).get("output", {}).get("results", [])
        if r.get("rule_id") == "S08"
    ]
    assert s08 and "(max: 5)" in s08[0]["message"], result.output


def test_check_uses_the_named_projects_profile(tmp_path: Path) -> None:
    strict = _project(tmp_path / "b", "prof-b", "library")
    _project(tmp_path / "a", "prof-a", None)  # active now, no profile

    result = runner.invoke(app, ["check", str(strict), "--project", str(tmp_path / "b")])

    assert shows(result.output, "(max: 5)"), result.output


def test_an_explicit_pipeline_wins_over_the_profile(tmp_path: Path) -> None:
    spec = _project(tmp_path, "prof-pipe", "library")

    result = runner.invoke(
        app,
        ["check", str(spec), "--pipeline", "validation_spec_default", "--project", str(tmp_path)],
    )

    assert shows(result.output, "(max: 8)"), result.output
