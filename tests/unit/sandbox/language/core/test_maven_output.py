# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading Maven's console output: the compiler's diagnostics, and the program's own words.

Two surfaces returned something true but useless. `run_compiler` detected a broken build and
reported `error_count=1` with an empty message, so a caller knew a build failed and nothing else.
`run_debugger` returned Maven's entire log as the program's output, so the one line the program
actually printed arrived buried in build chatter and JVM deprecation warnings.

Maven writes both on stdout, prefixed. The samples below are copied from real runs, ANSI codes and
all, because the colouring is what a naive prefix match trips over.

Proves: TECH-031 FR-20
"""

from __future__ import annotations

from specweaver.sandbox.language.core.maven_output import compile_errors, program_output

_COMPILE_FAILURE = (
    "[\x1b[1;31mERROR\x1b[m] COMPILATION ERROR : \n"
    "[\x1b[1;31mERROR\x1b[m] /w/src/main/java/App.java:[3,34] incompatible types: "
    "java.lang.String cannot be converted to int\n"
    "[\x1b[1;31mERROR\x1b[m] Failed to execute goal "
    "org.apache.maven.plugins:maven-compiler-plugin:3.13.0:compile (default-compile)\n"
    # Maven prints each diagnostic twice — once as it compiles, once in the failure summary.
    "[\x1b[1;31mERROR\x1b[m] /w/src/main/java/App.java:[3,34] incompatible types: "
    "java.lang.String cannot be converted to int\n"
)

_RUN = (
    "[INFO] Scanning for projects...\n"
    # javac echoes these with no prefix at all, which is why filtering by prefix is not enough —
    # they are indistinguishable from a line the program printed.
    "  not setting the location of system modules may lead to class files that cannot run\n"
    "    --release 17 is recommended instead of -source 17 -target 17\n"
    "[INFO] --- exec:3.6.3:java (default-cli) @ probe ---\n"
    "WARNING: A terminally deprecated method in sun.misc.Unsafe has been called\n"
    "WARNING: sun.misc.Unsafe::objectFieldOffset will be removed in a future release\n"
    "hello from java\n"
    "[INFO] BUILD SUCCESS\n"
)


class TestCompileErrors:
    """One error per diagnostic, with the file and line that make it fixable."""

    def test_a_compilation_error_carries_its_message(self) -> None:
        errors = compile_errors(_COMPILE_FAILURE)

        assert len(errors) == 1, errors
        assert errors[0].file.endswith("App.java")
        assert errors[0].line == 3
        assert errors[0].column == 34
        assert "cannot be converted to int" in errors[0].message

    def test_a_repeated_diagnostic_is_reported_once(self) -> None:
        """Maven prints each one twice: as it compiles, and again in the failure summary. Counting
        both doubles every error a caller sees."""
        assert len(compile_errors(_COMPILE_FAILURE)) == 1

    def test_maven_own_failure_lines_are_not_diagnostics(self) -> None:
        """`Failed to execute goal …` names no source location and fixes nothing."""
        assert all(
            "Failed to execute goal" not in e.message for e in compile_errors(_COMPILE_FAILURE)
        )

    def test_a_clean_build_reports_nothing(self) -> None:
        """The control: a compiler that invents errors would pass the test above."""
        assert compile_errors("[INFO] BUILD SUCCESS\n") == []


class TestProgramOutput:
    """What the program printed, separated from what the build tool said about it."""

    def test_the_programs_own_line_survives(self) -> None:
        assert "hello from java" in program_output(_RUN)

    def test_maven_chatter_is_dropped(self) -> None:
        out = program_output(_RUN)

        assert "Scanning for projects" not in out
        assert "BUILD SUCCESS" not in out

    def test_unprefixed_compiler_warnings_are_dropped(self) -> None:
        """javac writes these with no prefix, before the program runs. Everything before Maven
        hands over to `exec:java` belongs to the build, whatever it looks like."""
        out = program_output(_RUN)

        assert "not setting the location" not in out
        assert "--release 17" not in out

    def test_jvm_warnings_are_dropped(self) -> None:
        """These come from the JVM, not the program, and there are four of them on every run."""
        assert "terminally deprecated" not in program_output(_RUN)

    def test_a_silent_program_yields_nothing_rather_than_the_log(self) -> None:
        """The control. Returning the build log for a program that printed nothing is exactly the
        noise this separates out."""
        assert program_output("[INFO] Scanning for projects...\n[INFO] BUILD SUCCESS\n") == ""
