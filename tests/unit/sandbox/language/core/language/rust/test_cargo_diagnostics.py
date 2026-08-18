# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading cargo's own JSON, rather than piping it through a converter nobody installs.

`run_linter` and `run_complexity` piped clippy into `clippy-sarif`. That binary is not installed, is
declared in no manifest, and the executor's failure leaves stdout empty — which the caller then
guarded with `if stdout.strip():` and returned `error_count=0`. A clean lint verdict for code clippy
had just flagged.

Clippy already emits JSON, one object per line, under `--message-format=json`. Parsing it directly
removes the converter and the silence with it. Every sample below is copied from a real run.

Proves: TECH-031 FR-19
"""

from __future__ import annotations

from specweaver.sandbox.language.core.rust.cargo_diagnostics import parse_cargo_diagnostics

_WARNING = """{"reason":"compiler-artifact","package_id":"probe"}
{"reason":"compiler-message","message":{"level":"warning","message":"unneeded `return` statement",\
"code":{"code":"clippy::needless_return"},"spans":[{"file_name":"src/lib.rs","line_start":3}]}}
{"reason":"build-finished","success":true}
"""

_COMPLEXITY = """{"reason":"compiler-message","message":{"level":"warning",\
"message":"the function has a cognitive complexity of (11/10)",\
"code":{"code":"clippy::cognitive_complexity"},"spans":[{"file_name":"src/lib.rs","line_start":9}]}}
"""


class TestParseCargoDiagnostics:
    """One finding per diagnostic, with the file and line that make it actionable."""

    def test_a_warning_becomes_a_finding(self) -> None:
        findings = parse_cargo_diagnostics(_WARNING)

        assert len(findings) == 1
        assert findings[0].code == "clippy::needless_return"
        assert findings[0].file == "src/lib.rs"
        assert findings[0].line == 3
        assert "unneeded `return`" in findings[0].message

    def test_lines_that_are_not_diagnostics_are_ignored(self) -> None:
        """cargo interleaves artifact and build-finished records in the same stream."""
        assert len(parse_cargo_diagnostics(_WARNING)) == 1

    def test_a_clean_run_yields_nothing(self) -> None:
        """The control: silence has to remain possible, or every project lints dirty."""
        assert parse_cargo_diagnostics('{"reason":"build-finished","success":true}\n') == []

    def test_malformed_lines_do_not_break_the_run(self) -> None:
        """cargo can interleave progress on the same stream; a bad line is not a lint verdict."""
        assert len(parse_cargo_diagnostics("not json\n" + _WARNING)) == 1

    def test_complexity_findings_are_separable_from_the_rest(self) -> None:
        """`run_complexity` reports these and `run_linter` must not, or each is counted twice."""
        findings = parse_cargo_diagnostics(_COMPLEXITY)

        assert len(findings) == 1
        assert "cognitive_complexity" in findings[0].code
