# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for PlatformLimiter strategy hierarchy."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from specweaver.sandbox.execution.models import ResourceLimits
from specweaver.sandbox.execution.platform_limiter import (
    NoOpLimiter,
    PlatformLimiter,
    get_platform_limiter,
)

# ---------------------------------------------------------------------------
# Task 2: PlatformLimiter ABC + NoOpLimiter
# ---------------------------------------------------------------------------


class TestNoOpLimiter:
    """Tests for the fallback NoOpLimiter."""

    # Happy path
    def test_is_platform_limiter(self) -> None:
        """NoOpLimiter is a PlatformLimiter subclass."""
        limiter = NoOpLimiter()
        assert isinstance(limiter, PlatformLimiter)

    def test_preexec_fn_returns_none(self) -> None:
        """NoOpLimiter.make_preexec_fn always returns None."""
        limiter = NoOpLimiter()
        limits = ResourceLimits(max_memory_bytes=1024)
        assert limiter.make_preexec_fn(limits) is None

    def test_apply_post_start_is_noop(self) -> None:
        """NoOpLimiter.apply_post_start does nothing (no exception)."""
        limiter = NoOpLimiter()
        limits = ResourceLimits(max_memory_bytes=1024)
        mock_proc = MagicMock()
        # Should not raise
        limiter.apply_post_start(mock_proc, limits)

    # Graceful degradation
    def test_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """NoOpLimiter logs a warning about unsupported platform."""
        import logging

        with caplog.at_level(logging.WARNING):
            limiter = NoOpLimiter()
            limits = ResourceLimits(max_memory_bytes=1024)
            limiter.apply_post_start(MagicMock(), limits)
        assert any("unsupported" in r.message.lower() or "no-op" in r.message.lower() for r in caplog.records)

    def test_noop_limiter_no_logs_if_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """NoOpLimiter does not log if limits are None."""
        import logging
        with caplog.at_level(logging.WARNING):
            limiter = NoOpLimiter()
            limits = ResourceLimits()  # All None
            limiter.apply_post_start(MagicMock(), limits)
        assert len(caplog.records) == 0


class TestGetPlatformLimiterUnknown:
    """Tests for get_platform_limiter() on unknown platforms."""

    def test_returns_noop_on_unknown_platform(self) -> None:
        """Unknown platform (e.g. freebsd) returns NoOpLimiter."""
        with patch("specweaver.sandbox.execution.platform_limiter.sys") as mock_sys:
            mock_sys.platform = "freebsd"
            limiter = get_platform_limiter()
        assert isinstance(limiter, NoOpLimiter)


# ---------------------------------------------------------------------------
# Task 3: UnixLimiter
# ---------------------------------------------------------------------------


class TestUnixLimiter:
    """Tests for UnixLimiter (resource.setrlimit via preexec_fn)."""

    def test_is_platform_limiter(self) -> None:
        """UnixLimiter is a PlatformLimiter subclass."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        limiter = UnixLimiter()
        assert isinstance(limiter, PlatformLimiter)

    def test_preexec_fn_returns_callable_with_memory_limit(self) -> None:
        """make_preexec_fn returns a callable when max_memory_bytes is set."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        limiter = UnixLimiter()
        limits = ResourceLimits(max_memory_bytes=512 * 1024 * 1024)
        fn = limiter.make_preexec_fn(limits)
        assert callable(fn)

    def test_preexec_fn_calls_setrlimit_memory(self) -> None:
        """preexec_fn calls resource.setrlimit with RLIMIT_AS."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        limiter = UnixLimiter()
        limits = ResourceLimits(max_memory_bytes=512 * 1024 * 1024)
        fn = limiter.make_preexec_fn(limits)
        assert fn is not None
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        with patch.dict("sys.modules", {"resource": mock_resource}):
            fn()
            mock_resource.setrlimit.assert_any_call(5, (512 * 1024 * 1024, 512 * 1024 * 1024))

    def test_preexec_fn_calls_setrlimit_nproc(self) -> None:
        """preexec_fn calls resource.setrlimit with RLIMIT_NPROC."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        limiter = UnixLimiter()
        limits = ResourceLimits(max_processes=50)
        fn = limiter.make_preexec_fn(limits)
        assert fn is not None
        mock_resource = MagicMock()
        mock_resource.RLIMIT_NPROC = 6
        with patch.dict("sys.modules", {"resource": mock_resource}):
            fn()
            mock_resource.setrlimit.assert_any_call(6, (50, 50))

    def test_preexec_fn_calls_setrlimit_fsize(self) -> None:
        """preexec_fn calls resource.setrlimit with RLIMIT_FSIZE."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        limiter = UnixLimiter()
        limits = ResourceLimits(max_file_size_bytes=1024)
        fn = limiter.make_preexec_fn(limits)
        assert fn is not None
        mock_resource = MagicMock()
        mock_resource.RLIMIT_FSIZE = 7
        with patch.dict("sys.modules", {"resource": mock_resource}):
            fn()
            mock_resource.setrlimit.assert_any_call(7, (1024, 1024))

    def test_preexec_fn_skips_none_limits(self) -> None:
        """Does not call setrlimit when all limits are None."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        limiter = UnixLimiter()
        limits = ResourceLimits()  # All None
        fn = limiter.make_preexec_fn(limits)
        # Should return None when no limits are specified
        assert fn is None

    def test_apply_post_start_is_noop(self) -> None:
        """apply_post_start does nothing on Unix (limits pre-applied)."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        limiter = UnixLimiter()
        limits = ResourceLimits(max_memory_bytes=1024)
        mock_proc = MagicMock()
        limiter.apply_post_start(mock_proc, limits)
        # No exception, no side effects

    def test_get_platform_limiter_linux(self) -> None:
        """get_platform_limiter returns UnixLimiter on linux."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        with patch("specweaver.sandbox.execution.platform_limiter.sys") as mock_sys:
            mock_sys.platform = "linux"
            limiter = get_platform_limiter()
        assert isinstance(limiter, UnixLimiter)

    def test_get_platform_limiter_darwin(self) -> None:
        """get_platform_limiter returns UnixLimiter on macOS (darwin)."""
        from specweaver.sandbox.execution.platform_limiter import UnixLimiter

        with patch("specweaver.sandbox.execution.platform_limiter.sys") as mock_sys:
            mock_sys.platform = "darwin"
            limiter = get_platform_limiter()
        assert isinstance(limiter, UnixLimiter)


# ---------------------------------------------------------------------------
# Task 4: WindowsLimiter
# ---------------------------------------------------------------------------


class TestWindowsLimiter:
    """Tests for WindowsLimiter (Win32 Job Objects via ctypes)."""

    def test_is_platform_limiter(self) -> None:
        """WindowsLimiter is a PlatformLimiter subclass."""
        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter

        limiter = WindowsLimiter()
        assert isinstance(limiter, PlatformLimiter)

    def test_make_preexec_fn_returns_none(self) -> None:
        """Windows preexec_fn is always None (limits applied post-start)."""
        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter

        limiter = WindowsLimiter()
        limits = ResourceLimits(max_memory_bytes=512 * 1024 * 1024)
        assert limiter.make_preexec_fn(limits) is None

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_apply_post_start_creates_job_object(self) -> None:
        """apply_post_start creates a Win32 Job Object."""
        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter

        limiter = WindowsLimiter()
        limits = ResourceLimits(max_memory_bytes=512 * 1024 * 1024)
        mock_proc = MagicMock()
        mock_proc.pid = 12345

        mock_ctypes = MagicMock()
        kernel32 = mock_ctypes.windll.kernel32
        kernel32.CreateJobObjectW.return_value = 42  # Fake handle
        kernel32.OpenProcess.return_value = 99  # Fake process handle
        kernel32.SetInformationJobObject.return_value = 1
        kernel32.AssignProcessToJobObject.return_value = 1

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            limiter.apply_post_start(mock_proc, limits)

            kernel32.CreateJobObjectW.assert_called_once()
            kernel32.OpenProcess.assert_called_once()
            kernel32.AssignProcessToJobObject.assert_called_once()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_apply_post_start_uses_pid_not_handle(self) -> None:
        """Uses OpenProcess with public proc.pid, not private _handle."""
        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter

        limiter = WindowsLimiter()
        limits = ResourceLimits(max_memory_bytes=256 * 1024 * 1024)
        mock_proc = MagicMock()
        mock_proc.pid = 54321

        mock_ctypes = MagicMock()
        kernel32 = mock_ctypes.windll.kernel32
        kernel32.CreateJobObjectW.return_value = 42
        kernel32.OpenProcess.return_value = 99
        kernel32.SetInformationJobObject.return_value = 1
        kernel32.AssignProcessToJobObject.return_value = 1
        kernel32.CloseHandle.return_value = 1

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            limiter.apply_post_start(mock_proc, limits)

            # Verify OpenProcess was called with the PID
            call_args = kernel32.OpenProcess.call_args
            assert 54321 in call_args[0] or 54321 in call_args[1].values()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_apply_post_start_closes_handle(self) -> None:
        """CloseHandle is called after assignment."""
        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter

        limiter = WindowsLimiter()
        limits = ResourceLimits(max_memory_bytes=128 * 1024 * 1024)
        mock_proc = MagicMock()
        mock_proc.pid = 99999

        mock_ctypes = MagicMock()
        kernel32 = mock_ctypes.windll.kernel32
        kernel32.CreateJobObjectW.return_value = 42
        kernel32.OpenProcess.return_value = 88
        kernel32.SetInformationJobObject.return_value = 1
        kernel32.AssignProcessToJobObject.return_value = 1
        kernel32.CloseHandle.return_value = 1

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            limiter.apply_post_start(mock_proc, limits)

            kernel32.CloseHandle.assert_called()

    def test_get_platform_limiter_win32(self) -> None:
        """get_platform_limiter returns WindowsLimiter on win32."""
        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter

        with patch("specweaver.sandbox.execution.platform_limiter.sys") as mock_sys:
            mock_sys.platform = "win32"
            limiter = get_platform_limiter()
        assert isinstance(limiter, WindowsLimiter)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_windows_limiter_create_job_fails(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter
        limiter = WindowsLimiter()
        limits = ResourceLimits(max_memory_bytes=1024)
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32.CreateJobObjectW.return_value = 0  # Fail

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            with caplog.at_level(logging.WARNING):
                limiter.apply_post_start(MagicMock(), limits)

        assert "CreateJobObjectW failed" in caplog.text

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_windows_limiter_set_info_fails(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter
        limiter = WindowsLimiter()
        limits = ResourceLimits(max_memory_bytes=1024)
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32.CreateJobObjectW.return_value = 42
        mock_ctypes.windll.kernel32.SetInformationJobObject.return_value = 0  # Fail

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            with caplog.at_level(logging.WARNING):
                limiter.apply_post_start(MagicMock(), limits)

        assert "SetInformationJobObject failed" in caplog.text
        mock_ctypes.windll.kernel32.CloseHandle.assert_called_with(42)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_windows_limiter_open_process_fails(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from specweaver.sandbox.execution.platform_limiter import WindowsLimiter
        limiter = WindowsLimiter()
        limits = ResourceLimits(max_memory_bytes=1024)
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32.CreateJobObjectW.return_value = 42
        mock_ctypes.windll.kernel32.SetInformationJobObject.return_value = 1
        mock_ctypes.windll.kernel32.OpenProcess.return_value = 0  # Fail

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            with caplog.at_level(logging.WARNING):
                limiter.apply_post_start(MagicMock(), limits)

        assert "OpenProcess failed" in caplog.text
        mock_ctypes.windll.kernel32.CloseHandle.assert_called_with(42)


