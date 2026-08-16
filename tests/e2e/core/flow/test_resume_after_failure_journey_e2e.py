# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A pipeline runs, and its state survives into a resume. TECH-054 CB-1.

Proves: TECH-054 FR-1

`D-FLOW-01` — *"SQLite Pipeline Runner & State Persistence"* — is the capability underneath every
`sw run`, `sw resume` and `sw implement`, and that sentence is its **entire** written record: no
design document, no requirements, and therefore nothing `check_fr_sweep.py` can fail it on. This
file is the falsifiable claim it never had. `TECH-054` chose a journey over a reverse-engineered
design deliberately: an FR read off the code it describes restates the implementation, and a
restatement cannot fail.

**Two processes, not two `CliRunner` invocations.** The claim is *persistence*, so the process
boundary is the substance of it rather than a detail of the setup. In-process, a resume that
silently reused live objects would pass this file while the SQLite state was never read back.

**No LLM anywhere.** Both steps are `action: bash`, so the journey turns on state and nothing else.
A pipeline that needed a model to prove its state survives would be testing the model.

**How it fails.** `mark.sh` appends one line to `marks.txt`; `gate.sh` exits 3 until a sentinel file
appears. Run once and step 1 passes, step 2 fails, and the run is persisted as `failed`. Create the
sentinel, resume, and the run must complete **with `marks.txt` still one line long** — if the
resume restarted the pipeline rather than continuing it, the file has two.

**What it found on the first run, before this file existed.** `sw resume` with no argument
enumerated `list_bundled_pipelines()` and asked for the latest run of each
(`flow/interfaces/cli.py:471`), so a run of any pipeline loaded from a YAML path — which `sw run`
documents and accepts — was invisible to auto-detection: *"No resumable runs found for the active
project"*, with the failed row sitting in `flow_pipeline_runs` the whole time. `sw resume <run-id>`
worked, because `load_run` has no such filter, which is how the gap survived. The same three lines
also returned the first *bundled-list* entry rather than the most recent run, one line under a
docstring promising "the newest resumable one".
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

#: The project directory name and the registered project name must agree: `sw run` records the run
#: against the project it resolves from the working directory, and `sw resume` looks it up by the
#: name in `workspace_active_state`. A mismatch makes this file green for the wrong reason.
PROJECT = "resumejourney"

#: Not a bundled pipeline, on purpose — a YAML path is a documented input to `sw run`, and it is the
#: input auto-detection could not see.
PIPELINE = textwrap.dedent("""\
    name: resume_journey
    description: two bash steps; the second is blocked until a sentinel appears
    version: "1.0"
    steps:
      - name: mark
        action: bash
        target: script
        description: "append exactly one line to marks.txt"
        params:
          script: mark.sh
        gate:
          type: auto
          condition: all_passed
          on_fail: abort
      - name: gate
        action: bash
        target: script
        description: "exits 3 until the sentinel exists"
        params:
          script: gate.sh
        gate:
          type: auto
          condition: all_passed
          on_fail: abort
    """)


def _sw(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """One `sw` invocation in its own process, inheriting the isolated `SPECWEAVER_DATA_DIR`."""
    return subprocess.run(
        [sys.executable, "-m", "specweaver.interfaces.cli.main", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env={**os.environ, "COLUMNS": "200"},
        check=False,
        timeout=300,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """An initialised project with the two scripts and the pipeline the journey runs."""
    root = tmp_path / PROJECT
    root.mkdir()

    init = _sw("init", PROJECT, "--path", str(root), cwd=tmp_path)
    assert init.returncode == 0, init.stdout + init.stderr

    scripts = root / ".specweaver" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    # Absolute paths: the atom may run the script from a worktree, and the point of `marks.txt` is
    # to count executions across processes, not to test where bash resolves a relative path.
    (scripts / "mark.sh").write_text(
        f'#!/usr/bin/env bash\necho ran >> "{root}/marks.txt"\n', encoding="utf-8"
    )
    # Step 2 leaves its own trace. Without it the journey passes vacuously: `sw resume` exits 0
    # when it finds NOTHING to resume, so "exit 0 and marks.txt still has one line" is satisfied
    # perfectly by a resume that did not happen. Caught by running this file before the fix.
    (scripts / "gate.sh").write_text(
        f'#!/usr/bin/env bash\ntest -f "{root}/unblock" || exit 3\necho ok >> "{root}/gates.txt"\n',
        encoding="utf-8",
    )
    for script in scripts.iterdir():
        script.chmod(0o755)

    (root / "resume_journey.yaml").write_text(PIPELINE, encoding="utf-8")
    (root / "specs").mkdir(exist_ok=True)
    (root / "specs" / "subject.md").write_text("# Subject\n", encoding="utf-8")
    return root


def _marks(root: Path) -> int:
    return len((root / "marks.txt").read_text(encoding="utf-8").splitlines())


class TestAPipelineResumesWhereItStopped:
    """The journey, and the only test in this file that is allowed to be slow."""

    def test_a_resumed_run_does_not_re_execute_a_step_that_already_passed(
        self, project: Path
    ) -> None:
        """[Happy] the whole claim: run, fail, fix, resume — in four separate processes.

        `marks.txt` is the assertion. Step 1 appends to it, so its line count is a count of how
        many times step 1 ran, and it is the one observation a resume that quietly restarted the
        pipeline could not fake.
        """
        first = _sw("run", "resume_journey.yaml", "specs/subject.md", cwd=project)

        assert first.returncode != 0, f"step 2 must fail the first time:\n{first.stdout}"
        assert _marks(project) == 1, "step 1 must have run exactly once"
        assert not (project / "gates.txt").exists(), "step 2 must not have succeeded yet"

        (project / "unblock").touch()
        resumed = _sw("resume", cwd=project)

        assert resumed.returncode == 0, (
            "`sw resume` must find and finish the failed run:\n" + resumed.stdout + resumed.stderr
        )
        assert (project / "gates.txt").exists(), (
            "step 2 never ran, so nothing was resumed — and `sw resume` exits 0 when it finds "
            f"nothing, which is why the return code alone proves nothing:\n{resumed.stdout}"
        )
        assert _marks(project) == 1, (
            "step 1 ran again — the resume restarted the pipeline instead of continuing it, so "
            f"the persisted state was not honoured (marks.txt has {_marks(project)} lines)"
        )

    def test_the_failed_run_is_offered_without_being_named(self, project: Path) -> None:
        """[Boundary] auto-detection, which is the half that was broken.

        `sw resume <run-id>` never used the bundled-pipeline loop, so it worked throughout; only the
        no-argument form — the one a developer actually types — could not see the run.
        """
        _sw("run", "resume_journey.yaml", "specs/subject.md", cwd=project)

        found = _sw("resume", cwd=project)

        assert "No resumable runs found" not in found.stdout, (
            "the failed run is in `flow_pipeline_runs` and auto-detection missed it:\n"
            + found.stdout
        )
