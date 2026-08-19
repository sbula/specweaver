# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the reader is told when pytest is not in the environment the run used.

This is the majority path, not an edge case. Measured across the 150 most-downloaded PyPI packages
(`docs/analysis/dependency_layout_corpus_2026-08-18.md`), 101 of 121 resolvable repositories would
arrive at the sandbox without pytest reachable — 81 never name it in `pyproject.toml` at all. So the
message this produces is what most first runs against a new target will say.

Before this, they said:

    pytest did not run: /cache/venv/bin/python: No module named pytest

which is the last line of stderr forwarded verbatim. It names `/cache/venv`, a path inside our own
sandbox that appears nowhere in the reader's project, and it says nothing about why pytest is absent
or what would make it present. A reader who has never seen the container layout has no way to tell
this from a broken test.

Proves: TECH-031 FR-9
"""

from __future__ import annotations

import pytest

from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.python.toolchain_absence import (
    absent_module,
    why_it_did_not_run,
)


def _result(stderr: str, exit_code: int = 1, stdout: str = "") -> SubprocessResult:
    return SubprocessResult(
        exit_code=exit_code, stdout=stdout, stderr=stderr, duration_seconds=0.01
    )


class TestAbsentModule:
    """The explanation replaces a forwarded stderr line, and must earn the replacement."""

    _CONTAINER = "/cache/venv/bin/python: No module named pytest"
    _HOST = "/usr/bin/python3: No module named pytest"

    @pytest.mark.parametrize("stderr", [_CONTAINER, _HOST], ids=["container", "host"])
    def test_it_names_the_module_and_calls_this_a_setup_failure(self, stderr: str) -> None:
        message = absent_module(_result(stderr))

        assert message is not None
        assert "pytest" in message
        # The distinction that sends the reader to the right place. Without it the reader debugs
        # their tests, which are fine, instead of their manifest, which is not.
        assert "not a test failure" in message.lower()

    @pytest.mark.parametrize("stderr", [_CONTAINER, _HOST], ids=["container", "host"])
    def test_it_says_what_would_make_the_module_present(self, stderr: str) -> None:
        """A diagnosis without a remedy is the same dead end in better prose.

        Asserted as the instruction, not as the word `uv.lock` appearing somewhere: the sentence
        describing where the environment comes from already contains that token, so a weaker check
        passed with the remedy deleted entirely.
        """
        message = absent_module(_result(stderr))

        assert message is not None
        assert "group" in message.lower(), message
        assert "Declare pytest" in message, (
            f"the message diagnoses but does not instruct:\n{message}"
        )
        assert "commit the lockfile" in message, message
        # Both worlds get an answer: the sandbox builds from the manifest, a host run does not.
        assert "virtualenv" in message, f"a host run is left without a remedy:\n{message}"

    def test_it_does_not_leak_the_sandbox_interpreter_path(self) -> None:
        """`/cache/venv` exists only inside our container and means nothing to the reader."""
        message = absent_module(_result(self._CONTAINER))

        assert message is not None
        assert "/cache" not in message, f"an internal path reached the user:\n{message}"

    def test_a_module_other_than_pytest_is_named_accurately(self) -> None:
        """The shape is `No module named X`; the explanation must not hardcode one X."""
        message = absent_module(_result("/usr/bin/python3: No module named nox"))

        assert message is not None
        assert "nox" in message
        assert "pytest" not in message, "the message named a module the interpreter did not"

    @pytest.mark.parametrize(
        "stderr",
        [
            "",
            "PermissionError: [Errno 13] Permission denied: '/workspace/tests'",
            "OCI runtime error: container init failed",
        ],
        # Explicit ids because the default ones are the strings themselves, and a node id with a
        # space in it cannot be re-run from a `FAILED` line — the corpus truncates it there and
        # reports a confirmed kill as flaky.
        ids=["empty", "permission-denied", "oci-error"],
    )
    def test_an_unrelated_failure_is_left_alone(self, stderr: str) -> None:
        """The control. Claiming a missing module for every silent failure would be a worse lie
        than the vague message it replaces — the caller falls back to the raw stderr instead."""
        assert absent_module(_result(stderr)) is None

    def test_a_run_that_produced_output_is_not_diagnosed(self) -> None:
        """pytest can mention a missing module in a collection error while running perfectly well.

        The absence check only applies to a run that produced nothing; a run with stdout reached a
        verdict, and overriding it here would turn real test failures into setup failures.
        """
        result = _result("ModuleNotFoundError: No module named pytest", stdout="1 failed in 0.1s")

        assert absent_module(result) is None


class TestWhyItDidNotRun:
    """The wrapper the runner actually calls: `did_not_run`, with the common case explained."""

    def test_a_run_that_reached_a_verdict_is_still_not_a_failure(self) -> None:
        """Delegation, and the whole gate depends on it: exit 5 with output is a real verdict."""
        assert (
            why_it_did_not_run(_result("", exit_code=5, stdout="no tests ran in 0.01s"), "pytest")
            is None
        )

    def test_a_missing_module_is_explained_rather_than_forwarded(self) -> None:
        message = why_it_did_not_run(
            _result("/cache/venv/bin/python: No module named ruff"), "ruff"
        )

        assert message is not None
        assert "/cache" not in message
        assert "not a test failure" in message.lower()

    def test_anything_else_keeps_the_shared_wording(self) -> None:
        """The fallback must survive, or unrecognised failures lose their only detail."""
        message = why_it_did_not_run(_result("OCI runtime error: container init failed"), "tach")

        assert message is not None
        assert message.startswith("tach did not run:")
        assert "OCI runtime error" in message


class TestPythonQARunnerSurfacesTheExplanation:
    """The functions above are pure; passing them proves nothing about what the runner reports.

    Every tool this runner drives goes through `python -m`, so each one fails this way when the
    prepared environment is incomplete — and each one used to forward the same unreadable line.
    """

    @staticmethod
    def _runner(tmp_path, stderr: str):
        from unittest.mock import MagicMock

        from specweaver.sandbox.execution.executor import SubprocessExecutor
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = SubprocessResult(
            exit_code=1, stdout="", stderr=stderr, duration_seconds=0.01
        )
        return PythonQARunner(cwd=tmp_path, executor=executor)

    def test_a_test_run_without_pytest_explains_itself(self, tmp_path) -> None:
        runner = self._runner(tmp_path, "/cache/venv/bin/python: No module named pytest")

        result = runner.run_tests(".")

        assert result.errors == 1, "a missing toolchain must not read as a clean run"
        message = result.failures[0].message
        assert "/cache" not in message, f"an internal path reached the user:\n{message}"
        assert "not a test failure" in message.lower(), message
        assert "uv.lock" in message, message

    def test_a_lint_run_without_ruff_explains_itself(self, tmp_path) -> None:
        """pytest is not a special case — the runner drives ruff through `python -m` too."""
        runner = self._runner(tmp_path, "/cache/venv/bin/python: No module named ruff")

        result = runner.run_linter(".")

        assert result.error_count >= 1
        message = " ".join(e.message for e in result.errors)
        assert "/cache" not in message, f"an internal path reached the user:\n{message}"
        assert "ruff is not installed" in message, message
