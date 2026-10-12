# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run` with an `action: bash` step: the script runs, its exit code routes, mistakes stop early.

Proves: C-EXEC-02 FR-1
Proves: C-EXEC-02 FR-5
Proves: C-EXEC-02 FR-7
Proves: C-EXEC-02 FR-9
Proves: C-EXEC-02 FR-10
Proves: TECH-011 FR-1
Proves: TECH-011 FR-2

Real `sw init`, real scripts in `.specweaver/scripts/`, real bash.

| Bucket | Case |
|---|---|
| Happy | a script passes; a router sends exit 0 and exit 3 to different steps |
| Boundary | a step over its timeout fails and says it timed out |
| Degradation | a failing script fails the run with its stderr |
| Hostile | `../` in the script name, a `PATH` override, a key beside `params:` — refused at load |
"""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash on PATH"),
]
runner = CliRunner()

_GREET = '#!/usr/bin/env bash\necho "hello $1"\necho "to err" >&2\nexit ${2:-0}\n'


@pytest.fixture
def project(tmp_path: Path) -> Path:
    assert runner.invoke(app, ["init", "bash-journey", "--path", str(tmp_path)]).exit_code == 0
    scripts = tmp_path / ".specweaver" / "scripts"
    (scripts / "greet.sh").write_text(_GREET, encoding="utf-8")
    (scripts / "slow.sh").write_text("#!/usr/bin/env bash\nsleep 5\n", encoding="utf-8")
    (scripts / "mark.sh").write_text('#!/usr/bin/env bash\necho "$1 ran"\n', encoding="utf-8")
    (tmp_path / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    return tmp_path


def _run(project: Path, steps: str):
    pipeline = project / "p.yaml"
    pipeline.write_text(f'name: p\nversion: "1.0"\nsteps:\n{steps}', encoding="utf-8")
    return runner.invoke(
        app,
        [
            "run",
            str(pipeline),
            str(project / "specs" / "a_spec.md"),
            "--json",
            "--project",
            str(project),
        ],
    )


def _events(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def _step(params: str, extra: str = "") -> str:
    return f"  - name: greet\n    action: bash\n    target: script\n    params: {params}\n{extra}"


def test_a_passing_script_passes_the_run(project: Path) -> None:
    result = _run(project, _step('{script: greet.sh, args: ["world"]}'))

    assert result.exit_code == 0, result.output
    assert "hello world" in result.output


def test_a_failing_script_fails_the_run_with_its_stderr(project: Path) -> None:
    result = _run(project, _step('{script: greet.sh, args: ["world", "3"]}'))

    assert result.exit_code == 1
    assert "exited 3. stderr: to err" in result.output


def test_a_script_over_its_timeout_says_so(project: Path) -> None:
    result = _run(project, _step("{script: slow.sh, timeout_seconds: 1}"))

    assert result.exit_code == 1
    assert "timed out after 1 s" in result.output


@pytest.mark.parametrize(("code", "ran"), [("0", "on_success"), ("3", "on_failure")])
def test_the_exit_code_routes_the_run(project: Path, code: str, ran: str) -> None:
    router = (
        "    gate: {on_fail: continue}\n    router:\n      default_target: on_failure\n"
        '      rules:\n        - field: exit_code\n          operator: "=="\n'
        "          value: 0\n          target: on_success\n"
    )
    branches = "".join(
        f"  - name: {name}\n    action: bash\n    target: script\n"
        f"    params: {{script: mark.sh, args: [{name}]}}\n"
        for name in ("on_failure", "on_success")
    )
    result = _run(project, _step(f'{{script: greet.sh, args: ["x", "{code}"]}}', router) + branches)

    started = [e["step_name"] for e in _events(result.output) if e.get("event") == "step_started"]
    assert started[:2] == ["greet", ran], started


@pytest.mark.parametrize(
    ("steps", "says"),
    [
        (_step("{script: ../../outside.sh}"), "Invalid script name"),
        (_step("{script: greet.sh, env: {Path: /tmp}}"), "may not set PATH"),
        ("  - name: greet\n    action: bash\n    target: script\n    script: greet.sh\n", "params"),
        (_step("{args: [x]}"), "script"),
    ],
)
def test_a_wrong_step_is_refused_before_anything_runs(project: Path, steps: str, says: str) -> None:
    result = _run(project, steps)

    assert result.exit_code == 1
    assert "Invalid pipeline" in result.output and says in result.output, result.output
    assert not [e for e in _events(result.output) if e.get("event") == "step_started"]
