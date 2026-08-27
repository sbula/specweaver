# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The seam between the collection rule and the gate that runs it. TECH-051 CB-3.

Proves: TECH-051 FR-1, TECH-051 FR-3, TECH-051 FR-5, TECH-051 FR-6, TECH-051 FR-7

**Why FR-5 and FR-6 are cited here and not in the files they describe.** They are about
`tests/unit/sandbox/protocol/` — the misplaced test moved home, the nine stubs filled — and those
files cite `A-VAL-01`, the capability they prove. `check_fr_coverage` reads text rather than
intent: a file naming two stories credits **each** story with **every** FR number in it, so adding
`TECH-051 FR-6` to a file that also says `A-VAL-01 FR-3` invented a dangling sixth FR against
that capability — which declares five — and,
worse, a silent false credit of `A-VAL-01 FR-5` to a gRPC parser test that proves nothing about
contract drift. One story per file. What proves FR-5 and FR-6 from here is
`test_a_clean_tree_exits_zero` against the live repo: those twelve files are why the tree is clean.

`test_check_test_collection.py` proves the rule; `test_quality_runner.py` proves the MATRIX lists
it. Neither proves the two halves meet — that `quality.py quick` actually invokes the script and
that a finding actually fails the gate. Per `ADR-003` that seam belongs to the boundary that creates
it, and this is it.

**Why this cannot be a unit test.** Everything asserted here happens in a subprocess: `quality.py`
shells out to the check with the venv interpreter, buffers its output, and maps its exit code onto
the gate's. Mocking any of that would test the mock. So this runs the real runner over a real
throwaway tree and reads the real exit code.

**There is deliberately no e2e.** The tier rule is that a journey across capabilities gets an e2e —
and `quality.py` is a developer gate, not a `sw` command. Its user is the person who typed
`python scripts/quality.py quick`, which is exactly what this test does. An e2e here would be the
same subprocess call in a different directory, and `check_proof_tier.py` counts tiers precisely so
that padding is visible rather than rewarded.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]

_HIDDEN = """# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.


class QARunnerTelemetryFlush:
    def test_flush_called_on_failed_run(self):
        assert True
"""


def _run_check(root: Path) -> subprocess.CompletedProcess[str]:
    """The check as `quality.py` invokes it: same interpreter, same argv shape, real exit code."""
    return subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "check_test_collection.py"),
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class TestTheGateRunsTheCheck:
    """FR-1 — a finding reaches the gate's exit code, not just the script's return value."""

    def test_quality_quick_includes_the_collection_check(self) -> None:
        """[Happy] the registration is real, not merely present in a table.

        Asserted through the runner's own resolution rather than by reading `MATRIX`, because a
        check can be listed and still fail to resolve — a missing `_quality_checks` entry would do
        exactly that, and the table would still look right.
        """
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "quality.py"),
                "quick",
                "--only",
                "test_collection",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "test_collection" in result.stdout

    def test_a_hidden_class_makes_the_check_exit_non_zero(self, tmp_path: Path) -> None:
        """[Happy] the shape that started the ticket, run through the real script."""
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_hidden.py").write_text(_HIDDEN, encoding="utf-8")

        result = _run_check(tmp_path)

        assert result.returncode == 1, result.stdout
        assert "test_hidden.py" in result.stdout
        assert "QARunnerTelemetryFlush" in result.stdout

    def test_a_clean_tree_exits_zero(self, tmp_path: Path) -> None:
        """[Boundary] the gate must not fail on a tree that is fine, or it will be switched off."""
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_fine.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

        result = _run_check(tmp_path)

        assert result.returncode == 0, result.stdout

    def test_a_missing_tests_directory_exits_two_not_zero(self, tmp_path: Path) -> None:
        """[Hostile] `TECH-032` — a checker that cannot find its subject must not report success.

        Two rather than one, so the gate can tell "your tree is broken" from "I could not look".
        """
        result = _run_check(tmp_path / "nowhere")

        assert result.returncode == 2
        assert "could not run" in result.stderr

    def test_the_output_tells_the_reader_not_to_delete_the_file(self, tmp_path: Path) -> None:
        """[Graceful degradation] the cheapest way to green is `rm`, and it is almost always wrong.

        Nine such stubs turned out to be the only visible trace that `A-VAL-01`, a delivered DAL-A
        capability, had no tests. The remedy has to be in the message, because whoever hits this
        gate at 2am will not read the design document.
        """
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_stub.py").write_text("", encoding="utf-8")

        result = _run_check(tmp_path)

        assert result.returncode == 1
        assert "Deleting the file is almost never right" in result.stdout


class TestProtocolCoverageStaysAttributed:
    """FR-7 — the attribution this ticket added stays attributed."""

    def test_the_protocol_ledger_still_exits_zero(self) -> None:
        """[Happy] `check_fr_coverage.py A-VAL-01` reports 5 of 5, and keeps reporting it.

        `TECH-051` CB-2 took `A-VAL-01` from **0 of 5 FRs proven** — on a capability marked ✅ at
        DAL-A — to 5 of 5, partly by writing tests and partly by citing tests that already existed
        and pointed at nothing. Citations are one careless docstring edit from vanishing, and the
        ledger is story-scoped: it only fires when somebody remembers to pass the story. Nobody
        remembered for `A-VAL-01` between its delivery and this ticket.

        So the remembering is delegated to a test. This is the one assertion here that is about the
        repo's state rather than the checker's behaviour, and it is deliberate: a regression would
        be silent everywhere else.
        """
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_fr_coverage.py"), "A-VAL-01"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "every declared FR is planned and cited" in result.stdout
