# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading what `cargo test` actually prints on stable Rust.

The runner asked cargo for JSON and piped it into `cargo2junit`. Measured against the real cargo on
2026-08-18, none of that could ever have worked:

- `cargo test --format=json -q`, the exact command, fails with
  `error: unexpected argument '--format' found` — `--format` is a libtest flag and belongs after `--`.
- Placed correctly, `cargo test -- --format=json` fails with *"The `json` format is only accepted on
  the nightly compiler with -Z unstable-options"*. The parser was built on output stable Rust does
  not emit.
- `cargo2junit` is not installed and is declared in no manifest.

The unit test asserted `--format=json` was in the command, so the mock pinned the broken form. Every
sample below is copied from a real run rather than written from memory, which is the only reason the
two-summary case below is here at all.

Proves: TECH-031 FR-11
"""

from __future__ import annotations

from specweaver.sandbox.language.core.rust.cargo_output import parse_cargo_test

#: A passing crate. Two `test result:` lines, because cargo reports doc-tests as a separate suite —
#: taking the first would report 1 passed and taking the last would report 0.
_PASSING = """
running 1 test
test t::works ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests probe

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
"""

#: Real output from a crate with one unit test and one doc-test — both suites report `1 passed`, so
#: summing and taking-the-first give different answers. That is the point of it.
_PASSING_WITH_DOCTEST = """
running 1 test
test t::works ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests docprobe

running 1 test
test src/lib.rs - twice (line 3) ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.05s
"""

_FAILING = """
running 3 tests
test t::skipped ... ignored
test t::ok_one ... ok
test t::broken ... FAILED

failures:

---- t::broken stdout ----

thread 't::broken' (78879) panicked at src/lib.rs:8:19:
assertion `left == right` failed
  left: 41
 right: 42
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace


failures:
    t::broken

test result: FAILED. 1 passed; 1 failed; 1 ignored; 0 measured; 0 filtered out; finished in 0.00s
"""


class TestParseCargoTest:
    """Stable text output, which is the only machine-readable form cargo offers without nightly."""

    def test_a_passing_run_is_counted_across_every_suite(self) -> None:
        """Doc-tests are a second suite in the same stream, and both summaries are real.

        The sample has a passing unit test **and** a passing doc-test, which is what makes this
        discriminate. An earlier version used a crate whose doc-test suite was empty — so reading
        only the first summary gave the same answer, and a mutant that did exactly that survived.
        """
        outcome = parse_cargo_test(_PASSING_WITH_DOCTEST)

        assert outcome is not None
        assert outcome.passed == 2, (
            f"the unit suite and the doc-test suite each passed one test: {outcome}"
        )
        assert (outcome.failed, outcome.skipped) == (0, 0)
        assert outcome.failures == []

    def test_a_failing_run_reports_the_test_and_its_panic(self) -> None:
        outcome = parse_cargo_test(_FAILING)

        assert outcome is not None
        assert (outcome.passed, outcome.failed, outcome.skipped) == (1, 1, 1)
        assert [f.nodeid for f in outcome.failures] == ["t::broken"]
        # The panic is the whole diagnostic value; a failure with an empty message sends the reader
        # back to the terminal to re-run it by hand.
        assert "assertion `left == right` failed" in outcome.failures[0].message
        assert "left: 41" in outcome.failures[0].message

    def test_output_with_no_summary_is_not_a_zero_result(self) -> None:
        """The control, and the reason this returns an optional.

        `cargo test` with a bad flag prints usage to stderr and nothing to stdout. Parsing that as
        `0 passed, 0 failed` is exactly the vacuous success the QA gate exists to prevent — it has
        to be distinguishable from a suite that genuinely has no tests.
        """
        assert parse_cargo_test("error: unexpected argument '--format' found") is None
        assert parse_cargo_test("") is None

    def test_a_genuinely_empty_suite_is_a_real_zero(self) -> None:
        """Distinct from the above: cargo *did* run and reported nothing to run."""
        outcome = parse_cargo_test(
            "\nrunning 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored;"
            " 0 measured; 0 filtered out; finished in 0.00s\n"
        )

        assert outcome is not None
        assert outcome.total == 0
        assert outcome.failed == 0
