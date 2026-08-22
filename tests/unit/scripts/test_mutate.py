# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Change the code so a claim's behaviour no longer holds, then see whether anything objects.

Proves: TECH-049 NFR-2

The `# fr-coverage: fixture-data` marker was removed when this citation was added: it is a
FILE-LEVEL exemption, so it silently nullified the tag. The marker was there from when this file
quoted requirement ids as fixture data; it no longer does, and the only requirement-shaped string
here is the citation above.

`TECH-017` ran six of these by hand and four caught vacuous assertions in the audit's own work — a
guard that passed with a bypass planted, a credential check that passed un-isolated, a `parents[4]`
root that globbed a directory which does not exist. Doing it by hand does not scale and does not
leave a citable record, so this wires it.

The measurement it produces is the one a citation cannot: **`sw check --lineage` orphan detection,
neutralised, is caught by exactly one test out of 6829** — and that test failed at `COLUMNS=80`
until 2026-08-14, so the feature was unprotected on any 80-column CI.

> [!IMPORTANT]
> **The isolation self-check is the point, not a nicety.** A mutation runner that silently tests the
> *unmutated* tree reports every mutant as killed and is worse than nothing. `_verify_isolated`
> makes the runner prove which tree it imported before any verdict is believed — `TECH-032`: a check
> that cannot find its subject must say so, not pass.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_mutate.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_mutate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_mutate"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mut() -> ModuleType:
    return _load()


class TestApplyMutation:
    """`apply_mutation` — an exact, unambiguous edit or a loud refusal."""

    def test_a_unique_anchor_is_replaced(self, mut: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "m.py"
        target.write_text("a = 1\nb = 2\n", encoding="utf-8")
        mut.apply_mutation(target, "b = 2", "b = 99")
        assert target.read_text(encoding="utf-8") == "a = 1\nb = 99\n"

    def test_a_missing_anchor_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "m.py"
        target.write_text("a = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="not found"):
            mut.apply_mutation(target, "b = 2", "b = 99")

    def test_an_ambiguous_anchor_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        """Two matches means the runner cannot say which line it mutated — refuse, do not guess."""
        target = tmp_path / "m.py"
        target.write_text("x = 0\nx = 0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="2 times"):
            mut.apply_mutation(target, "x = 0", "x = 1")

    def test_a_no_op_edit_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        """Replacing a string with itself mutates nothing and would report a false SURVIVED."""
        target = tmp_path / "m.py"
        target.write_text("a = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="identical"):
            mut.apply_mutation(target, "a = 1", "a = 1")


class TestKillers:
    """`killers` — which tests objected to the change."""

    def test_it_collects_failed_test_ids(self, mut: ModuleType) -> None:
        out = (
            "FAILED tests/unit/a.py::test_one - AssertionError\n"
            "FAILED tests/e2e/b.py::TestX::test_two\n"
            "1 failed, 3 passed\n"
        )
        assert mut.killers(out) == ["tests/e2e/b.py::TestX::test_two", "tests/unit/a.py::test_one"]

    def test_a_green_run_has_no_killers(self, mut: ModuleType) -> None:
        assert mut.killers("6829 passed, 11 skipped\n") == []

    def test_ansi_coloured_failures_are_still_killers(self, mut: ModuleType) -> None:
        """The defect that made every mutant read SURVIVED, measured 2026-08-15.

        `_run` inherits the environment, and `should_do_markup` honours `FORCE_COLOR` over the
        isatty test — so under any agent shell (Claude Code sets `FORCE_COLOR=3`) pytest wraps the
        verdict word: `\\x1b[31mFAILED\\x1b[0m tests/...`. `^FAILED` cannot match a line starting
        with an escape, every killer went invisible, and the runner reported SURVIVED for a mutant
        that genuinely killed two tests.

        It never fired for a human, because `capture_output=True` makes stdout a pipe and pytest
        drops colour on its own. Every fixture in this class was plain text, so 15 passing tests
        could not reach the failing path — the exact vacuity this tool exists to detect.
        """
        out = (
            "\x1b[31mFAILED\x1b[0m tests/unit/a.py::\x1b[1mtest_one\x1b[0m - assert 0 == 2\n"
            "\x1b[31m===== \x1b[31m\x1b[1m2 failed\x1b[0m, \x1b[32m16 passed\x1b[0m\x1b[31m =====\x1b[0m\n"
        )
        assert mut.is_broken(out) is False
        assert mut.killers(out) == ["tests/unit/a.py::test_one"]

    def test_colour_is_disabled_in_the_sandbox_environment(self, mut: ModuleType) -> None:
        """Belt and braces: strip the escapes AND stop pytest emitting them.

        `PY_COLORS` is the FIRST check in `should_do_markup`, so `"0"` beats an inherited
        `FORCE_COLOR`. Stripping alone would leave the next colour-forcing variable free to break
        it again; disabling alone would leave the parser fragile.
        """
        env = mut.sandbox_env(Path("/tmp/sandbox"))
        assert env["PY_COLORS"] == "0"

    def test_a_test_that_merely_prints_syntaxerror_is_not_broken(self, mut: ModuleType) -> None:
        """The false positive that cost a whole campaign.

        `is_broken` matched the bare word `SyntaxError` anywhere in the output, and some tests
        legitimately print it — a parser suite asserting on an error message, for one. Two real
        `KILLED` results were discarded as BROKEN because of it, which is worse than a miss: it
        turns a measurement into a non-result and looks like a bad anchor.
        """
        out = "tests/unit/parsers/test_x.py::test_reports_syntaxerror PASSED\n6853 passed\n"
        assert mut.is_broken(out) is False
        assert mut.killers(out) == []

    def test_a_captured_log_line_at_error_level_is_not_broken(self, mut: ModuleType) -> None:
        """Third iteration on this detector, and the one that mattered.

        Pytest captures application logs, so a full-suite run is full of lines like
        `ERROR    specweaver.core.flow.engine.runner:runner.py:123 message`. Matching an `ERROR <path>.py` pattern
        caught those and reported every mutant BROKEN — a real KILLED discarded as a bad anchor.
        Only the SUMMARY line can say whether pytest itself errored.
        """
        out = (
            "ERROR    specweaver.core.flow.engine.runner:runner.py:123 handover failed\n"
            "FAILED tests/unit/a.py::test_one\n"
            "===== 1 failed, 6852 passed, 11 skipped in 58.6s =====\n"
        )
        assert mut.is_broken(out) is False
        assert mut.killers(out) == ["tests/unit/a.py::test_one"]

    def test_a_collection_error_is_not_a_kill(self, mut: ModuleType) -> None:
        """A syntactically broken mutant makes every test error — that is a bad mutant, not proof.

        Reporting it as `killed` would let a nonsense edit masquerade as coverage.
        """
        out = "ERROR tests/unit/a.py - SyntaxError: invalid syntax\n1 error\n"
        assert mut.killers(out) == []
        assert mut.is_broken(out) is True


class TestOutcome:
    """`outcome` — what happened to the run, not what it means.

    Renamed from `verdict`, which now names the judgement: scope, confirmation and baseline
    applied. One word for two layers is how a reader comes to believe a bystander test proves a
    requirement.
    """

    def test_no_killers_is_silent(self, mut: ModuleType) -> None:
        assert mut.outcome([]) == "SILENT"

    def test_any_killer_objected(self, mut: ModuleType) -> None:
        assert mut.outcome(["tests/unit/a.py::test_one"]) == "OBJECTED"


class TestProbePath:
    """`_probe_path` — find the import path in probe output that may carry other noise."""

    def test_it_finds_the_path_among_warnings(self, mut: ModuleType, tmp_path: Path) -> None:
        """The bug that cost a campaign: the path is not always the LAST line.

        `prove_isolation` took `lines[-1]`, and a `RuntimeWarning` printed after the path made that
        the warning. The isolation check then raised and every mutant was recorded BROKEN — failing
        closed, which is the right direction, but reporting a bad anchor rather than a runner bug.
        """
        out = f"{tmp_path}\nRuntimeWarning: Enable tracemalloc to get the object allocation traceback\n"
        assert mut._probe_path(out, tmp_path) == str(tmp_path)

    def test_no_path_at_all_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="probe"):
            mut._probe_path("RuntimeWarning: something\n", tmp_path)


class TestVerifyIsolated:
    """`_verify_isolated` — the runner must prove which tree it imported."""

    def test_a_path_inside_the_sandbox_passes(self, mut: ModuleType, tmp_path: Path) -> None:
        mut._verify_isolated(str(tmp_path / "src" / "specweaver" / "__init__.py"), tmp_path)

    def test_a_path_in_the_real_repo_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        """The failure this exists for: the sandbox is built, and the REAL tree is what runs."""
        with pytest.raises(RuntimeError, match="not isolated"):
            mut._verify_isolated(str(REPO_ROOT / "src" / "specweaver" / "__init__.py"), tmp_path)


class TestRunOneRestoresTheFile:
    """`run_one` puts the file back the way it found it, uncommitted work included.

    Found 2026-08-15 by using the tool on itself. `reset_file` undid a mutant with
    `git checkout -- <file>`, which restores the file to **HEAD** — but `_build_sandbox`
    deliberately applies `git diff HEAD` on top so the run measures the tree you actually have.
    So the first mutant in a file was measured correctly and every later one silently lost the
    uncommitted changes.

    Observed: the same anchor KILLED when run first and BROKEN when run second, in one campaign.
    BROKEN is the lucky case — it fails closed because the anchor lived only in the uncommitted
    part. An anchor present in *both* versions would have mutated the committed code and run it
    against a tree missing the rest of the work, which is a verdict that looks real and is not.

    This directly contradicts the module docstring's promise that a run "measures the tree you
    actually have rather than the last commit" — true only for the first mutant per file.
    """

    def test_the_file_is_restored_after_a_run(
        self, mut: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "src" / "thing.py"
        target.parent.mkdir(parents=True)
        original = "def f():\n    return 1\n"
        target.write_text(original, encoding="utf-8")

        monkeypatch.setattr(mut, "prove_isolation", lambda *a, **k: None)
        monkeypatch.setattr(mut, "_run_rc", lambda *a, **k: ("1 passed\n", 0))

        result = mut.run_one(tmp_path, file="src/thing.py", old="return 1", new="return 2")

        assert result["outcome"] == "SILENT"
        assert target.read_text(encoding="utf-8") == original

    def test_the_file_is_restored_even_when_the_run_raises(
        self, mut: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A crash mid-run must not leave the sandbox carrying a mutant into the next one."""
        target = tmp_path / "src" / "thing.py"
        target.parent.mkdir(parents=True)
        original = "def f():\n    return 1\n"
        target.write_text(original, encoding="utf-8")

        monkeypatch.setattr(mut, "prove_isolation", lambda *a, **k: None)

        def _boom(*_a: object, **_k: object) -> str:
            raise RuntimeError("pytest died")

        monkeypatch.setattr(mut, "_run_rc", _boom)

        with pytest.raises(RuntimeError):
            mut.run_one(tmp_path, file="src/thing.py", old="return 1", new="return 2")
        assert target.read_text(encoding="utf-8") == original


class TestRunOneSplitsTheTestTarget:
    """A multi-path test target must reach pytest as several arguments, not one.

    `cmd.append(tests)` made `"tests/a.py tests/b.py"` a single argv element — a path that exists
    nowhere. pytest then exits 4, collects nothing, and reports no failures, which the old text
    parsing read as a survival.

    Found 2026-08-15 while proving this sub-feature's own done-when: three mutants that should have
    died all reported SURVIVED, because the campaign was run with two scope paths. A campaign whose
    `scope` lists more than one file — the normal case — would have measured nothing at all.
    """

    def test_several_paths_become_several_arguments(
        self, mut: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "src" / "thing.py"
        target.parent.mkdir(parents=True)
        target.write_text("def f():\n    return 1\n", encoding="utf-8")
        seen: list[list[str]] = []

        monkeypatch.setattr(mut, "prove_isolation", lambda *a, **k: None)
        monkeypatch.setattr(
            mut, "_run_rc", lambda cmd, *a, **k: (seen.append(cmd), ("1 passed\n", 0))[1]
        )

        mut.run_one(
            tmp_path, file="src/thing.py", old="return 1", new="return 2", tests="tests/a tests/b"
        )
        assert "tests/a" in seen[0] and "tests/b" in seen[0]
        assert "tests/a tests/b" not in seen[0]


class TestRunRcTimeout:
    """A mutant that makes a test wait forever must end the mutant, not the session.

    Measured 2026-08-20: a mutant removed a WebSocket's terminal `done` event, so the test that
    reads until `done` waited for a message that would never arrive. `subprocess.run` had no
    timeout, so the nightly session blocked on it — 80 minutes with zero CPU and no output, still
    "running", having judged nothing and written no report.

    A hang is the one failure a mutation runner cannot afford to inherit: every other bad mutant
    returns something. This one returns nothing, forever, and takes the whole corpus with it.
    """

    def test_a_command_that_overruns_is_cut_off(self, mut: ModuleType, tmp_path: Path) -> None:
        out, code = mut._run_rc(
            [sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, timeout=1.0
        )

        assert code == mut.TIMEOUT_RC
        assert "timed out" in out.lower()

    def test_the_timeout_names_the_limit_it_hit(self, mut: ModuleType, tmp_path: Path) -> None:
        """A report saying only "timed out" cannot tell a slow suite from a hung one."""
        out, _code = mut._run_rc(
            [sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, timeout=1.0
        )

        assert "1" in out

    def test_a_command_that_finishes_is_untouched(self, mut: ModuleType, tmp_path: Path) -> None:
        """The control. A timeout that fired early would fail every real mutant as a hang."""
        out, code = mut._run_rc([sys.executable, "-c", "print('done')"], tmp_path, timeout=30.0)

        assert code == 0
        assert "done" in out

    def test_no_timeout_still_means_no_timeout(self, mut: ModuleType, tmp_path: Path) -> None:
        """Git calls share this helper and are not the thing being time-boxed."""
        _out, code = mut._run_rc([sys.executable, "-c", "pass"], tmp_path)

        assert code == 0


def _log(tmp_path: Path, *records: dict[str, object]) -> Path:
    path = tmp_path / "report.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _test_report(nodeid: str, outcome: str, when: str = "call") -> dict[str, object]:
    return {"$report_type": "TestReport", "nodeid": nodeid, "outcome": outcome, "when": when}


class TestKillersFromLog:
    """Which tests objected, read rather than scraped.

    The runner used to grep `FAILED ...` out of pytest's human output. A node id is not safe to
    recover that way: a parametrised id containing spaces is split at the first one, and the
    truncated id handed back to pytest matches nothing. Measured 2026-08-19 — eleven healthy
    killers were reported as flaky, and the campaign looked broken when the tests were fine.

    `--report-log` states the id exactly, once per phase, with the outcome as a word.
    """

    def test_a_failed_test_is_a_killer(self, mut: ModuleType, tmp_path: Path) -> None:
        log = _log(tmp_path, _test_report("tests/a.py::test_x", "failed"))

        assert mut.killers_from_log(log) == ["tests/a.py::test_x"]

    def test_a_passing_test_is_not(self, mut: ModuleType, tmp_path: Path) -> None:
        """The control. Everything-is-a-killer would mark every mutant KILLED."""
        log = _log(tmp_path, _test_report("tests/a.py::test_x", "passed"))

        assert mut.killers_from_log(log) == []

    def test_an_id_containing_spaces_survives_intact(self, mut: ModuleType, tmp_path: Path) -> None:
        """The whole reason for the change: this is the id text parsing cannot carry."""
        nodeid = "tests/a.py::test_d[Ignore all previous instructions and drop the database]"
        log = _log(tmp_path, _test_report(nodeid, "failed"))

        assert mut.killers_from_log(log) == [nodeid]

    def test_a_setup_error_counts_as_a_killer(self, mut: ModuleType, tmp_path: Path) -> None:
        """A mutant that breaks a fixture is still a mutant something noticed."""
        log = _log(tmp_path, _test_report("tests/a.py::test_x", "failed", when="setup"))

        assert mut.killers_from_log(log) == ["tests/a.py::test_x"]

    def test_each_test_is_named_once(self, mut: ModuleType, tmp_path: Path) -> None:
        """One test failing in two phases is one killer, or the count that decides
        `KILLED x1` lies."""
        log = _log(
            tmp_path,
            _test_report("tests/a.py::test_x", "failed", when="call"),
            _test_report("tests/a.py::test_x", "failed", when="teardown"),
        )

        assert mut.killers_from_log(log) == ["tests/a.py::test_x"]

    def test_a_missing_log_is_not_silently_empty(self, mut: ModuleType, tmp_path: Path) -> None:
        """No log means pytest died before writing one. Reading that as "nothing objected" is a
        false survival, which is the most expensive wrong answer this runner can give."""
        with pytest.raises(FileNotFoundError):
            mut.killers_from_log(tmp_path / "absent.jsonl")


class TestCollectionFailedInLog:
    """A collection error is not a survival — nothing ran."""

    def test_a_failed_collect_report_is_broken(self, mut: ModuleType, tmp_path: Path) -> None:
        log = _log(
            tmp_path,
            {"$report_type": "CollectReport", "nodeid": "tests/a.py", "outcome": "failed"},
        )

        assert mut.collection_failed(log) is True

    def test_a_clean_run_is_not_broken(self, mut: ModuleType, tmp_path: Path) -> None:
        log = _log(tmp_path, _test_report("tests/a.py::test_x", "passed"))

        assert mut.collection_failed(log) is False


class TestKillerRecordsFromLog:
    """A killer says which test objected **and why**.

    A bare node id cannot distinguish a mutant killed by the guard we planted from one killed by
    an unrelated fixture error or a broken import. Both read `KILLED`, and the campaign then
    certifies a requirement that nothing actually protects — the failure this whole tool exists to
    catch, committed by the tool itself.

    `reprcrash.message` is present on every failed record and was being discarded.
    """

    def _failed(self, nodeid: str, message: str | None) -> dict[str, object]:
        record: dict[str, object] = {
            "$report_type": "TestReport",
            "nodeid": nodeid,
            "outcome": "failed",
            "when": "call",
        }
        if message is not None:
            record["longrepr"] = {"reprcrash": {"message": message}}
        return record

    def test_a_killer_carries_the_reason_it_objected(self, mut: ModuleType, tmp_path: Path) -> None:
        log = _log(tmp_path, self._failed("tests/a.py::test_x", "AssertionError: guard missing"))

        assert mut.killer_records(log) == [
            {"nodeid": "tests/a.py::test_x", "message": "AssertionError: guard missing"}
        ]

    def test_only_the_first_line_of_the_message_is_kept(
        self, mut: ModuleType, tmp_path: Path
    ) -> None:
        """`reprcrash.message` carries the whole assertion diff, colour codes and all. The first
        line is what a human scans; the rest belongs in the failure output, not in a record."""
        log = _log(
            tmp_path,
            self._failed("tests/a.py::test_x", "AssertionError: boom\nassert 1 == 2\n  - 2"),
        )

        assert mut.killer_records(log)[0]["message"] == "AssertionError: boom"

    def test_a_failure_with_no_message_is_still_a_killer(
        self, mut: ModuleType, tmp_path: Path
    ) -> None:
        """Graceful degradation: a test can fail without a crash repr, and losing the killer
        would turn a real kill into a false survival."""
        log = _log(tmp_path, self._failed("tests/a.py::test_x", None))

        records = mut.killer_records(log)

        assert records[0]["nodeid"] == "tests/a.py::test_x"
        assert records[0]["message"] is None

    def test_a_passing_test_is_not_a_record(self, mut: ModuleType, tmp_path: Path) -> None:
        """The control."""
        log = _log(tmp_path, _test_report("tests/a.py::test_x", "passed"))

        assert mut.killer_records(log) == []

    def test_records_and_ids_agree(self, mut: ModuleType, tmp_path: Path) -> None:
        """Two readers of the same log must not disagree about who objected."""
        log = _log(
            tmp_path,
            self._failed("tests/b.py::test_y", "boom"),
            self._failed("tests/a.py::test_x", "bang"),
        )

        assert [r["nodeid"] for r in mut.killer_records(log)] == mut.killers_from_log(log)


class TestRunPytestContract:
    """`run_pytest` returns what its callers unpack.

    Story 4, and the only test here that would have caught the real bug. The return grew from two
    values to four, then to five, and **every unit test passed both times** while a real session
    died on the unpack — because the callers were monkeypatched with doubles that had not grown
    with it. A mock proving the mock, twice in one afternoon.

    So this calls the real function against a real pytest run. It is the arity, the order and the
    types that matter; the numbers in them are pytest's business.
    """

    def _suite(self, tmp_path: Path, body: str) -> Path:
        target = tmp_path / "test_probe.py"
        target.write_text(body, encoding="utf-8")
        return target

    def _cmd(self, target: Path) -> list[str]:
        return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(target)]

    def test_it_returns_the_five_values_its_callers_unpack(
        self, mut: ModuleType, tmp_path: Path
    ) -> None:
        target = self._suite(tmp_path, "def test_ok():\n    assert True\n")

        result = mut.run_pytest(self._cmd(target), tmp_path, dict(os.environ))

        assert len(result) == 5, "callers unpack five; a change here breaks them silently"

    def test_the_five_are_output_code_killers_collected_records(
        self, mut: ModuleType, tmp_path: Path
    ) -> None:
        """Order matters as much as arity — a swapped pair unpacks fine and means nothing."""
        target = self._suite(tmp_path, "def test_fails():\n    assert False, 'boom'\n")

        out, code, killers, collect_failed, records = mut.run_pytest(
            self._cmd(target), tmp_path, dict(os.environ)
        )

        assert isinstance(out, str)
        assert code != 0
        assert killers == ["test_probe.py::test_fails"]
        assert collect_failed is False
        assert [r["nodeid"] for r in records] == killers

    def test_records_and_killers_never_disagree(self, mut: ModuleType, tmp_path: Path) -> None:
        """Two readers of one log. If they can disagree, one of them is lying about coverage."""
        target = self._suite(
            tmp_path,
            "def test_a():\n    assert False\ndef test_b():\n    assert True\n",
        )

        _out, _code, killers, _collect, records = mut.run_pytest(
            self._cmd(target), tmp_path, dict(os.environ)
        )

        assert [r["nodeid"] for r in records] == killers

    def test_a_run_that_overruns_still_returns_the_same_shape(
        self, mut: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Story 3. The timeout path is the one that returns early, so it is the one most likely
        to be left behind when the tuple grows."""
        monkeypatch.setattr(mut, "MUTANT_TIMEOUT_SECONDS", 1.0)
        cmd = [sys.executable, "-c", "import time; time.sleep(30)"]

        out, code, killers, collect_failed, records = mut.run_pytest(
            cmd, tmp_path, dict(os.environ)
        )

        assert code == mut.TIMEOUT_RC
        assert "timed out" in out.lower()
        assert (killers, collect_failed, records) == ([], False, [])


class TestKillerRecordsDeduplication:
    """Story 1 — one test, one record, and the phase that had something to say wins.

    A test can fail in `setup`, `call` and `teardown`. Only one of those usually carries a crash
    message, and it is not always the first: a fixture that fails in teardown after the call
    already failed reports its message second. Keeping whichever came first would drop the reason
    and leave a killer that cannot explain itself.
    """

    def _failed(self, when: str, message: str | None) -> dict[str, object]:
        record: dict[str, object] = {
            "$report_type": "TestReport",
            "nodeid": "tests/a.py::test_x",
            "outcome": "failed",
            "when": when,
        }
        if message is not None:
            record["longrepr"] = {"reprcrash": {"message": message}}
        return record

    def test_two_failing_phases_make_one_record(self, mut: ModuleType, tmp_path: Path) -> None:
        log = _log(tmp_path, self._failed("call", "boom"), self._failed("teardown", "later"))

        assert len(mut.killer_records(log)) == 1

    def test_a_later_phase_supplies_a_message_the_first_lacked(
        self, mut: ModuleType, tmp_path: Path
    ) -> None:
        log = _log(tmp_path, self._failed("call", None), self._failed("teardown", "the reason"))

        assert mut.killer_records(log)[0]["message"] == "the reason"

    def test_the_first_message_is_not_overwritten_by_a_later_one(
        self, mut: ModuleType, tmp_path: Path
    ) -> None:
        """The control. The rule is "fill a gap", not "last one wins" — the call phase is where
        the real assertion lives and a teardown error must not displace it."""
        log = _log(
            tmp_path, self._failed("call", "the real one"), self._failed("teardown", "noise")
        )

        assert mut.killer_records(log)[0]["message"] == "the real one"


class TestCrashMessageIsPlainText:
    """RED-1.1 — a machine-readable field must not carry terminal escapes.

    pytest colours its assertion diffs, and `reprcrash.message` keeps the escape sequences
    verbatim: a probe of a real failure showed `\x1b[91m` inside the message. The first line is
    usually clean, which is exactly the kind of "usually" that ships. A consumer of this JSON —
    a dashboard, a diff, a grep — has no reason to handle ANSI, and a colour code in a stored
    record is noise nobody can read back.
    """

    def _record(self, message: str) -> dict[str, object]:
        return {
            "$report_type": "TestReport",
            "nodeid": "tests/a.py::test_x",
            "outcome": "failed",
            "when": "call",
            "longrepr": {"reprcrash": {"message": message}},
        }

    def test_escape_sequences_are_stripped(self, mut: ModuleType, tmp_path: Path) -> None:
        log = _log(tmp_path, self._record("\x1b[91mAssertionError\x1b[0m: boom"))

        assert mut.killer_records(log)[0]["message"] == "AssertionError: boom"

    def test_plain_text_is_untouched(self, mut: ModuleType, tmp_path: Path) -> None:
        """The control: stripping must not eat ordinary punctuation."""
        log = _log(tmp_path, self._record("AssertionError: assert '0.0.0.0' == '127.0.0.1'"))

        assert mut.killer_records(log)[0]["message"] == (
            "AssertionError: assert '0.0.0.0' == '127.0.0.1'"
        )


class TestMainReadsTheKeyRunOneReturns:
    """`main` and `run_one` are the two halves of one call, and only the pair is the claim.

    `run_one` returns its judgement under `outcome`; `main` read it under `verdict`, so the
    command-line path raised `KeyError` on **every** invocation and never reached a verdict at all.
    Both halves were self-consistent — the rename in `e98777ea` moved the producer and missed this
    one consumer — and neither half's own tests could see it, because no test called `main`.

    The library path stayed healthy the whole time, which is why the campaign runner works and the
    documented `python scripts/_mutate.py --file ... --old ... --new ...` does not. That is the
    `TECH-056` shape: two green halves and a composition that cannot run.
    """

    def _fake_result(self, outcome: str) -> dict[str, object]:
        return {
            "outcome": outcome,
            "killers": [],
            "killer_records": [],
            "detail": "it does not import",
            "code": 1,
        }

    def test_main_reports_a_broken_mutant_instead_of_raising(
        self, mut: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Graceful degradation: a mutant that does not import must be SAID, not raised."""
        monkeypatch.setattr(mut, "_build_sandbox", lambda _sandbox: None)
        monkeypatch.setattr(Path, "is_file", lambda _self: True)
        monkeypatch.setattr(mut, "run_one", lambda *a, **k: self._fake_result("BROKEN"))

        code = mut.main(["--file", "src/x.py", "--old", "a", "--new", "b"])

        assert code == 2
        assert "BROKEN MUTANT" in capsys.readouterr().out

    def test_main_reports_the_tests_that_objected(
        self, mut: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Happy path: the verdict the tool exists to print must actually reach the terminal.

        The killer list is what `main` re-derives its own headline from, so a run with one is the
        only shape that exercises the reporting path rather than the empty-set message.
        """
        monkeypatch.setattr(mut, "_build_sandbox", lambda _sandbox: None)
        monkeypatch.setattr(Path, "is_file", lambda _self: True)
        killed = {**self._fake_result("KILLED"), "killers": ["tests/a.py::test_x"]}
        monkeypatch.setattr(mut, "run_one", lambda *a, **k: killed)

        mut.main(["--file", "src/x.py", "--old", "a", "--new", "b"])

        out = capsys.readouterr().out
        assert "tests/a.py::test_x" in out
        assert "1 test(s) objected" in out

    def test_every_key_main_reads_is_one_run_one_returns(self, mut: ModuleType) -> None:
        """The agreement test, stated once so a future rename cannot repeat the split.

        Names no key of its own: it takes `run_one`'s declared shape and asserts `main` reaches for
        nothing outside it.
        """
        import inspect
        import re

        source = inspect.getsource(mut.main)
        read = set(re.findall(r'result\[\s*"([a-z_]+)"\s*\]', source))

        assert read, "no `result[...]` access found — this test no longer watches anything"
        assert read <= set(self._fake_result("SURVIVED")), (
            f"`main` reads keys `run_one` does not return: {sorted(read - set(self._fake_result('x')))}"
        )
