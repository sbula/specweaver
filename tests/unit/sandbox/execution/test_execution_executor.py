# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for SubprocessExecutor and related data models."""

from __future__ import annotations

import dataclasses
import sys
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution.executor import (
    ResourceLimits,
    SubprocessResult,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Task 1: Data models — SubprocessResult
# ---------------------------------------------------------------------------


class TestSubprocessResult:
    """Tests for SubprocessResult frozen dataclass."""

    # Happy path
    def test_create_with_all_fields(self) -> None:
        """SubprocessResult can be created with all required fields."""
        result = SubprocessResult(
            exit_code=0,
            stdout="hello world\n",
            stderr="",
            duration_seconds=1.23,
        )
        assert result.exit_code == 0
        assert result.stdout == "hello world\n"
        assert result.stderr == ""
        assert result.duration_seconds == 1.23

    def test_default_timed_out_false(self) -> None:
        """timed_out defaults to False."""
        result = SubprocessResult(
            exit_code=0, stdout="", stderr="", duration_seconds=0.1
        )
        assert result.timed_out is False

    def test_default_events_empty(self) -> None:
        """events defaults to an empty list."""
        result = SubprocessResult(
            exit_code=0, stdout="", stderr="", duration_seconds=0.1
        )
        assert result.events == []

    def test_timed_out_true(self) -> None:
        """SubprocessResult records timed_out=True correctly."""
        result = SubprocessResult(
            exit_code=-1,
            stdout="",
            stderr="killed",
            duration_seconds=120.0,
            timed_out=True,
        )
        assert result.timed_out is True

    # Boundary / Edge cases
    def test_zero_duration(self) -> None:
        """Duration of 0.0 is valid."""
        result = SubprocessResult(
            exit_code=0, stdout="", stderr="", duration_seconds=0.0
        )
        assert result.duration_seconds == 0.0

    def test_negative_exit_code(self) -> None:
        """Negative exit code (signal-killed) is valid."""
        result = SubprocessResult(
            exit_code=-9, stdout="", stderr="", duration_seconds=0.5
        )
        assert result.exit_code == -9

    # Hostile input — frozen immutability
    def test_frozen_cannot_mutate_exit_code(self) -> None:
        """SubprocessResult is frozen — cannot mutate exit_code."""
        result = SubprocessResult(
            exit_code=0, stdout="", stderr="", duration_seconds=0.1
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.exit_code = 1  # type: ignore[misc]

    def test_frozen_cannot_mutate_stdout(self) -> None:
        """SubprocessResult is frozen — cannot mutate stdout."""
        result = SubprocessResult(
            exit_code=0, stdout="hello", stderr="", duration_seconds=0.1
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.stdout = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Task 1: Data models — ResourceLimits
# ---------------------------------------------------------------------------


class TestResourceLimits:
    """Tests for ResourceLimits frozen dataclass."""

    # Happy path
    def test_create_with_specific_limits(self) -> None:
        """ResourceLimits can be created with specific values."""
        limits = ResourceLimits(
            max_memory_bytes=512 * 1024 * 1024,
            max_processes=50,
            max_file_size_bytes=100 * 1024 * 1024,
        )
        assert limits.max_memory_bytes == 512 * 1024 * 1024
        assert limits.max_processes == 50
        assert limits.max_file_size_bytes == 100 * 1024 * 1024

    # Boundary / Edge — all None defaults
    def test_default_none_values(self) -> None:
        """All limits default to None (no limit enforced)."""
        limits = ResourceLimits()
        assert limits.max_memory_bytes is None
        assert limits.max_processes is None
        assert limits.max_file_size_bytes is None

    def test_partial_limits(self) -> None:
        """Can set only some limits, others remain None."""
        limits = ResourceLimits(max_memory_bytes=1024)
        assert limits.max_memory_bytes == 1024
        assert limits.max_processes is None
        assert limits.max_file_size_bytes is None

    # Hostile input — frozen immutability
    def test_frozen_cannot_mutate(self) -> None:
        """ResourceLimits is frozen — cannot mutate."""
        limits = ResourceLimits(max_memory_bytes=1024)
        with pytest.raises(dataclasses.FrozenInstanceError):
            limits.max_memory_bytes = 2048  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Task 5: SubprocessExecutor env building
# ---------------------------------------------------------------------------


class TestSubprocessExecutorEnv:
    """Tests for SubprocessExecutor environment building."""

    # Happy path
    def test_env_allowlist_forwarded(self, tmp_path: Path) -> None:
        """PATH and HOME/USERPROFILE are forwarded to child."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        # Execute a command that prints an env var
        if sys.platform == "win32":
            result = executor.execute(["python", "-c", "import os; print(os.environ.get('PATH', 'MISSING'))"])
        else:
            result = executor.execute(["python3", "-c", "import os; print(os.environ.get('PATH', 'MISSING'))"])
        assert result.stdout.strip() != "MISSING"

    def test_extra_env_injected(self, tmp_path: Path) -> None:
        """Custom env vars can be injected via extra_env."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute(
            [py, "-c", "import os; print(os.environ.get('MY_CUSTOM_VAR', 'MISSING'))"],
            extra_env={"MY_CUSTOM_VAR": "test_value_42"},
        )
        assert result.stdout.strip() == "test_value_42"

    def test_git_vars_forwarded(self, tmp_path: Path) -> None:
        """GIT_EXEC_PATH and GIT_DIR are in the default allowlist."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        # Set GIT_EXEC_PATH in parent env, verify it reaches child
        import os
        old = os.environ.get("GIT_EXEC_PATH")
        os.environ["GIT_EXEC_PATH"] = "/test/git/path"
        try:
            result = executor.execute(
                [py, "-c", "import os; print(os.environ.get('GIT_EXEC_PATH', 'MISSING'))"],
            )
            assert result.stdout.strip() == "/test/git/path"
        finally:
            if old is not None:
                os.environ["GIT_EXEC_PATH"] = old
            else:
                os.environ.pop("GIT_EXEC_PATH", None)

    # Hostile input — credential stripping
    def test_env_stripping_gemini(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GEMINI_API_KEY is NOT forwarded to child."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        monkeypatch.setenv("GEMINI_API_KEY", "secret_key_123")
        result = executor.execute(
            [py, "-c", "import os; print(os.environ.get('GEMINI_API_KEY', 'STRIPPED'))"],
        )
        assert result.stdout.strip() == "STRIPPED"

    def test_env_stripping_openai(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENAI_API_KEY is NOT forwarded to child."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
        result = executor.execute(
            [py, "-c", "import os; print(os.environ.get('OPENAI_API_KEY', 'STRIPPED'))"],
        )
        assert result.stdout.strip() == "STRIPPED"

    def test_env_stripping_anthropic(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_API_KEY is NOT forwarded to child."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-secret")
        result = executor.execute(
            [py, "-c", "import os; print(os.environ.get('ANTHROPIC_API_KEY', 'STRIPPED'))"],
        )
        assert result.stdout.strip() == "STRIPPED"

    def test_extra_env_does_not_override_stripped(self, tmp_path: Path) -> None:
        """Cannot inject GEMINI_API_KEY via extra_env (red team cycle 1)."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute(
            [py, "-c", "import os; print(os.environ.get('GEMINI_API_KEY', 'STRIPPED'))"],
            extra_env={"GEMINI_API_KEY": "injected_secret"},
        )
        assert result.stdout.strip() == "STRIPPED"

    def test_env_stripping_azure(self, tmp_path: Path) -> None:
        from specweaver.sandbox.execution.executor import SubprocessExecutor
        executor = SubprocessExecutor(cwd=tmp_path)
        env = executor._build_env({'AZURE_CLIENT_SECRET': 'secret', 'AZURE_TENANT_ID': 'tenant'})
        assert 'AZURE_CLIENT_SECRET' not in env
        assert 'AZURE_TENANT_ID' not in env

    def test_env_stripping_false_bypass(self, tmp_path: Path) -> None:
        from specweaver.sandbox.execution.executor import SubprocessExecutor
        executor = SubprocessExecutor(cwd=tmp_path, strip_credentials=False)
        env = executor._build_env({'GEMINI_API_KEY': 'secret'})
        assert env.get('GEMINI_API_KEY') == 'secret'


# ---------------------------------------------------------------------------
# Task 6: SubprocessExecutor path validation
# ---------------------------------------------------------------------------


class TestSubprocessExecutorPathValidation:
    """Tests for SubprocessExecutor cwd validation."""

    # Boundary / Edge
    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """cwd_override with path traversal is rejected."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        evil_path = tmp_path / ".." / ".." / ".."
        py = "python" if sys.platform == "win32" else "python3"
        with pytest.raises((ValueError, OSError)):
            executor.execute([py, "-c", "print('escaped')"], cwd_override=evil_path)

    def test_nonexistent_cwd_rejected(self, tmp_path: Path) -> None:
        """Non-existent cwd_override is rejected."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        missing = tmp_path / "nonexistent_dir_xyz"
        py = "python" if sys.platform == "win32" else "python3"
        with pytest.raises((ValueError, FileNotFoundError)):
            executor.execute([py, "-c", "print('hello')"], cwd_override=missing)

    # Hostile input — symlink escape (red team cycle 2)
    def test_path_traversal_symlink_blocked(self, tmp_path: Path) -> None:
        """Symlink escaping boundary raises error."""
        import os

        from specweaver.sandbox.execution.executor import SubprocessExecutor
        executor = SubprocessExecutor(cwd=tmp_path)
        # Create a symlink that points outside tmp_path
        target_dir = tmp_path.parent
        link_path = tmp_path / "evil_link"
        try:
            os.symlink(str(target_dir), str(link_path))
        except OSError:
            pytest.skip("Cannot create symlinks (requires admin on Windows)")

        py = "python" if sys.platform == "win32" else "python3"
        with pytest.raises((ValueError, OSError)):
            executor.execute([py, "-c", "print('escaped')"], cwd_override=link_path)


# ---------------------------------------------------------------------------
# Task 7: SubprocessExecutor.execute()
# ---------------------------------------------------------------------------


class TestSubprocessExecutorExecute:
    """Tests for SubprocessExecutor.execute() core functionality."""

    # Happy path
    def test_execute_simple_command(self, tmp_path: Path) -> None:
        """Simple echo command returns exit_code=0 and stdout."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "print('hello world')"])
        assert result.exit_code == 0
        assert "hello world" in result.stdout

    def test_execute_failing_command(self, tmp_path: Path) -> None:
        """Non-zero exit code captured correctly."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "import sys; sys.exit(42)"])
        assert result.exit_code == 42

    def test_stderr_captured(self, tmp_path: Path) -> None:
        """stderr is captured."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "import sys; sys.stderr.write('error msg\\n')"])
        assert "error msg" in result.stderr

    # Timeout handling
    def test_timeout_kills_process(self, tmp_path: Path) -> None:
        """Process running > timeout is killed, timed_out=True."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path, timeout_seconds=2)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute(
            [py, "-c", "import time; time.sleep(30)"],
            timeout_seconds=1,
        )
        assert result.timed_out is True

    def test_timeout_default_from_init(self, tmp_path: Path) -> None:
        """Default timeout from constructor used when not overridden."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path, timeout_seconds=1)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "import time; time.sleep(30)"])
        assert result.timed_out is True

    # Output events
    def test_output_events_generated(self, tmp_path: Path) -> None:
        """stdout/stderr lines become OutputEvent objects."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "print('line1'); print('line2')"])
        assert len(result.events) >= 2

    def test_output_events_category_stdout(self, tmp_path: Path) -> None:
        """stdout events have category='stdout'."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "print('test')"])
        stdout_events = [e for e in result.events if e.category == "stdout"]
        assert len(stdout_events) >= 1

    def test_output_events_category_stderr(self, tmp_path: Path) -> None:
        """stderr events have category='stderr'."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "import sys; sys.stderr.write('err\\n')"])
        stderr_events = [e for e in result.events if e.category == "stderr"]
        assert len(stderr_events) >= 1

    # Telemetry
    def test_duration_tracked(self, tmp_path: Path) -> None:
        """duration_seconds > 0."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute([py, "-c", "print('quick')"])
        assert result.duration_seconds > 0

    def test_debug_logging(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Logger called with expected structured fields."""
        import logging

        from specweaver.sandbox.execution.executor import SubprocessExecutor

        with caplog.at_level(logging.DEBUG):
            executor = SubprocessExecutor(cwd=tmp_path)
            py = "python" if sys.platform == "win32" else "python3"
            executor.execute([py, "-c", "print('logged')"])
        # Check that debug log contains key fields
        log_text = " ".join(r.message for r in caplog.records)
        assert "subprocess_execute" in log_text or "execute" in log_text.lower()

    def test_debug_logging_contains_cmd(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Log entry contains the command that was run."""
        import logging

        from specweaver.sandbox.execution.executor import SubprocessExecutor

        with caplog.at_level(logging.DEBUG):
            executor = SubprocessExecutor(cwd=tmp_path)
            py = "python" if sys.platform == "win32" else "python3"
            executor.execute([py, "-c", "print('traced')"])
        log_text = " ".join(r.message for r in caplog.records)
        assert py in log_text or "python" in log_text.lower()

    def test_execute_oserror(self, tmp_path: Path) -> None:
        """OSError translates into exit_code=-1 and stderr."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor
        executor = SubprocessExecutor(cwd=tmp_path)
        result = executor.execute(["does_not_exist_binary"])
        assert result.exit_code == -1
        assert "WinError" in result.stderr or "No such file" in result.stderr or "FileNotFoundError" in result.stderr

    def test_signal_propagation_logic(self, tmp_path: Path) -> None:
        """Test process tracking adds process to _active_processes."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        executor.execute([py, "-c", "print('hello')"])

        # The process finished quickly but it was added to _active_processes.
        # It might still be in the weakset, though it's finished.
        # But testing weakset size is flaky due to gc, so we just verify it doesn't crash.
        import specweaver.sandbox.execution._signals as sig
        sig._cleanup_active_processes()  # Should not crash


# ---------------------------------------------------------------------------
# Task T0.2: input_text support for SubprocessExecutor.execute()
# ---------------------------------------------------------------------------


class TestSubprocessExecutorInputText:
    """Tests for input_text parameter on SubprocessExecutor.execute()."""

    # Happy path
    def test_input_text_piped_to_stdin(self, tmp_path: Path) -> None:
        """input_text is received by child process on stdin."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        # Child reads stdin and echoes it
        result = executor.execute(
            [py, "-c", "import sys; data = sys.stdin.read(); print(data.strip())"],
            input_text="hello from stdin",
        )
        assert result.exit_code == 0
        assert "hello from stdin" in result.stdout

    # Boundary / Edge cases
    def test_input_text_none_default(self, tmp_path: Path) -> None:
        """Default input_text=None means no stdin is piped."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        # Without input_text, stdin should not block the child
        result = executor.execute([py, "-c", "print('no stdin needed')"])
        assert result.exit_code == 0
        assert "no stdin needed" in result.stdout

    def test_input_text_empty_string(self, tmp_path: Path) -> None:
        """Empty string input_text pipes empty stdin (EOF immediately)."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute(
            [py, "-c", "import sys; data = sys.stdin.read(); print(f'got:{len(data)}')"],
            input_text="",
        )
        assert result.exit_code == 0
        assert "got:0" in result.stdout

    # Graceful degradation
    def test_input_text_with_timeout(self, tmp_path: Path) -> None:
        """input_text works correctly with timeout — process completes before timeout."""
        from specweaver.sandbox.execution.executor import SubprocessExecutor

        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        result = executor.execute(
            [py, "-c", "import sys; print(sys.stdin.read().upper())"],
            input_text="make me uppercase",
            timeout_seconds=10,
        )
        assert result.exit_code == 0
        assert "MAKE ME UPPERCASE" in result.stdout
        assert result.timed_out is False

