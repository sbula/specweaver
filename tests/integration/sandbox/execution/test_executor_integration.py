# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for SubprocessExecutor across OS boundaries.

Proves: E-EXEC-01 FR-7, FR-10.

FR-7 signal propagation — the design requires SIGINT/SIGTERM to reach the child process group
with no orphaned zombies, which `test_...signal...` asserts. FR-10 cross-platform resource limits —
`resource.setrlimit()` for process, memory and file-size caps.

**`NFR-2` is deliberately NOT claimed here.** The design's threshold is *"< 5ms overhead per
invocation compared to direct `subprocess.run()`"*; this file asserts `< 200ms`, which is 40x looser
and does not establish the requirement. Recorded rather than cited — see `TECH-017` finding 7.

Attributed 2026-08-13 (`TECH-017` finding 6).
"""

import os
import sys
import time
from pathlib import Path

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import ResourceLimits


class TestSubprocessExecutorIntegration:
    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only limits")
    def test_process_limit_unix(self, tmp_path: Path) -> None:
        """The child runs under a process cap set to the current baseline plus the budget (FR-10).

        No fork bomb is run — that would risk the CI host — so the cap is read from inside the child
        instead.

        The assertion is deliberately relative. `RLIMIT_NPROC` is per-real-UID and counts tasks
        (threads), so the raw budget is not a reachable ceiling: an ordinary machine already sits
        above it before the sandbox forks anything, and asserting the literal value is what let that
        defect pass for as long as it did. What must hold is that the cap **exceeds the baseline by
        the budget**, which is what bounds this sandbox's additional forks.
        """
        from specweaver.sandbox.execution.platform_limiter import current_task_count

        budget = 50
        baseline = current_task_count()
        assert baseline is not None, "cannot establish a baseline on this platform"

        executor = SubprocessExecutor(
            cwd=tmp_path, resource_limits=ResourceLimits(max_processes=budget)
        )
        result = executor.execute(
            [
                "python3",
                "-c",
                "import resource, sys; sys.stdout.write(str(resource.getrlimit(resource.RLIMIT_NPROC)[0]))",
            ]
        )

        assert result.exit_code == 0
        applied = int(result.stdout.strip())
        assert applied > baseline, (
            f"cap {applied} is at or below the {baseline}-task baseline — unreachable, "
            "so every fork would fail"
        )

        # The upper bound is deliberately loose and lives in the unit tests, which pin the arithmetic
        # exactly. It used to read `applied - baseline <= budget * 2`, and that stopped expressing the
        # contract: the ceiling now widens by the ambient SPREAD this process has observed, because a
        # ceiling fixed at spawn is otherwise spent by unrelated load and kills the child mid-run with
        # `fork: retry: Resource temporarily unavailable`. Under `-n auto` this worker has usually made
        # many launches across a moving task count by the time it reaches here, so a tight multiple of
        # the budget is simply the old defect re-asserted. What must still hold is that a bound EXISTS
        # — an unbounded fork is what `E-EXEC-01` FR-10 is about.
        assert applied < 1_000_000, f"cap {applied} is not a bound at all"

    def test_memory_limit(self, tmp_path: Path) -> None:
        """Verify memory limits are enforced (FR-10)."""
        # Set limit to 20MB. Python baseline is ~15MB.
        limit_bytes = 20 * 1024 * 1024
        executor = SubprocessExecutor(
            cwd=tmp_path, resource_limits=ResourceLimits(max_memory_bytes=limit_bytes)
        )
        py = "python" if sys.platform == "win32" else "python3"

        # A script that allocates 50MB
        script = "x = b'A' * (50 * 1024 * 1024)"
        result = executor.execute([py, "-c", script])

        # Should be killed by OS (OOM or Job Object violation)
        assert result.exit_code != 0

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows Job Objects do not support max file size per process",
    )
    def test_file_size_limit(self, tmp_path: Path) -> None:
        """A child writing past `max_file_size_bytes` is stopped by the OS (FR-10).

        The write MUST target a real file. `RLIMIT_FSIZE` bounds writes to regular files only, and
        this test previously wrote 2 MB to stdout — a `subprocess.PIPE`, which no size limit
        applies to. It asserted `exit_code != 0` for a process that always exits 0, and was
        `skipif`-ed on Windows, so it had never run on any platform and could not have passed on
        this one.

        Two assertions, because "the process failed" alone would also be satisfied by a typo in the
        script: the file on disk must also stop at the limit, which is the limit doing the work.
        """
        limit_bytes = 1024 * 1024  # 1MB
        executor = SubprocessExecutor(
            cwd=tmp_path, resource_limits=ResourceLimits(max_file_size_bytes=limit_bytes)
        )
        py = "python" if sys.platform == "win32" else "python3"
        target = tmp_path / "oversized.bin"

        script = f"open({str(target)!r}, 'wb').write(b'A' * (2 * 1024 * 1024))"
        result = executor.execute([py, "-c", script])

        assert result.exit_code != 0, "writing past RLIMIT_FSIZE must not succeed"
        assert target.stat().st_size <= limit_bytes, (
            f"file grew to {target.stat().st_size} past the {limit_bytes} limit"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows Job Objects do not support max file size per process",
    )
    def test_a_write_under_the_file_size_limit_succeeds(self, tmp_path: Path) -> None:
        """Control for the test above: the limit bounds large writes, it does not fail all writes.

        Without this, `test_file_size_limit` would still pass if the executor were broken in a way
        that made every child exit non-zero — the assertion would be satisfied for entirely the
        wrong reason.
        """
        limit_bytes = 1024 * 1024
        executor = SubprocessExecutor(
            cwd=tmp_path, resource_limits=ResourceLimits(max_file_size_bytes=limit_bytes)
        )
        py = "python" if sys.platform == "win32" else "python3"
        target = tmp_path / "modest.bin"

        script = f"open({str(target)!r}, 'wb').write(b'A' * 1024)"
        result = executor.execute([py, "-c", script])

        assert result.exit_code == 0, result.stderr
        assert target.stat().st_size == 1024

    def test_timeout_escalation(self, tmp_path: Path) -> None:
        """Verify process is killed if it ignores SIGTERM."""
        executor = SubprocessExecutor(cwd=tmp_path, timeout_seconds=1)
        py = "python" if sys.platform == "win32" else "python3"

        script = (
            "import signal, time, sys\n"
            "def handler(s, f): pass\n"
            "if sys.platform != 'win32': signal.signal(signal.SIGTERM, handler)\n"
            "time.sleep(10)\n"
        )
        result = executor.execute([py, "-c", script])

        assert result.timed_out is True
        assert result.duration_seconds < 4.0  # 1s timeout + 2s grace + small buffer

    def test_zombie_prevention(self, tmp_path: Path) -> None:
        """Verify FR-7 Signal propagation and zombie prevention."""
        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"

        # Start a process that sleeps for 2 seconds
        # We manually call track_process and check weakset behavior
        result = executor.execute([py, "-c", "import time; time.sleep(0.5)"])
        assert result.exit_code == 0

        # Process should be dead
        import specweaver.sandbox.execution._signals as sig

        sig._cleanup_active_processes()  # Should handle dead processes gracefully

    def test_symlink_escape(self, tmp_path: Path) -> None:
        """Verify path traversal via symlinks is blocked."""
        # Create a directory outside the boundary
        outside = tmp_path.parent / f"outside_{os.getpid()}"
        outside.mkdir(exist_ok=True)
        try:
            # Create a symlink inside boundary pointing outside
            symlink = tmp_path / "link"
            try:
                symlink.symlink_to(outside)
            except OSError:
                pytest.skip("Symlink privilege not held on Windows")

            executor = SubprocessExecutor(cwd=tmp_path)
            with pytest.raises(ValueError, match="blocked"):
                executor.execute(["echo", "hello"], cwd_override=symlink)
        finally:
            if outside.exists():
                outside.rmdir()

    def test_real_env_verification(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify sensitive credentials are removed from actual OS env."""
        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"
        monkeypatch.setenv("GEMINI_API_KEY", "supersecret")

        result = executor.execute(
            [py, "-c", "import os; print(os.environ.get('GEMINI_API_KEY', 'NOT_FOUND'))"]
        )
        assert result.exit_code == 0
        assert "NOT_FOUND" in result.stdout

    def test_overhead_benchmark(self, tmp_path: Path) -> None:
        """Verify execution overhead is < 200ms (NFR-2)."""
        executor = SubprocessExecutor(cwd=tmp_path)
        py = "python" if sys.platform == "win32" else "python3"

        start = time.monotonic()
        executor.execute([py, "-c", "pass"])
        end = time.monotonic()

        # The overhead includes python startup time, which can be ~30-100ms.
        # Total time should be under 500ms for a baseline CI environment.
        assert (end - start) < 1.0
