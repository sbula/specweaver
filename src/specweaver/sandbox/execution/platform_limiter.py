# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Cross-platform resource limiting strategies for subprocess execution.

Provides a ``PlatformLimiter`` ABC with concrete implementations:
- ``UnixLimiter``: Uses ``resource.setrlimit()`` via ``preexec_fn`` (Linux/macOS).
- ``WindowsLimiter``: Uses Win32 Job Objects via ``ctypes`` (Windows 11).
- ``NoOpLimiter``: Safe fallback for unsupported platforms.

Use ``get_platform_limiter()`` to auto-detect the current OS and obtain
the appropriate limiter instance.
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Callable

    from specweaver.sandbox.execution.executor import ResourceLimits

logger = logging.getLogger(__name__)


class PlatformLimiter(ABC):
    """Abstract strategy for OS-specific resource limiting."""

    @abstractmethod
    def make_preexec_fn(self, limits: ResourceLimits) -> Callable[[], None] | None:
        """Return a ``preexec_fn`` for ``subprocess.Popen``, or ``None``.

        On Unix/macOS, this returns a callable that sets ``RLIMIT_AS`` and
        ``RLIMIT_NPROC`` before the child process exec. On Windows, returns
        ``None`` (limits are applied post-start via Job Objects).
        """

    @abstractmethod
    def apply_post_start(self, proc: subprocess.Popen[str], limits: ResourceLimits) -> None:
        """Apply resource limits after process creation.

        On Windows, this creates a Win32 Job Object and assigns the process
        to it. On Unix/macOS, this is a no-op (limits applied via preexec_fn).
        """


class NoOpLimiter(PlatformLimiter):
    """Fallback limiter for unsupported platforms.

    Logs a warning but does not block execution. Resource limits are
    not enforced — this is the safe degradation path.
    """

    def make_preexec_fn(self, limits: ResourceLimits) -> None:
        """No preexec_fn on unsupported platforms."""
        return None

    def apply_post_start(self, proc: subprocess.Popen[str], limits: ResourceLimits) -> None:
        """No-op — logs warning about unsupported platform."""
        if limits.max_memory_bytes or limits.max_processes or limits.max_file_size_bytes:
            logger.warning(
                "Resource limits requested but no-op limiter active "
                "(unsupported platform: %s). Limits will NOT be enforced.",
                sys.platform,
            )


def get_platform_limiter() -> PlatformLimiter:
    """Auto-detect OS and return the appropriate resource limiter.

    Returns:
        ``UnixLimiter`` on Linux/macOS, ``WindowsLimiter`` on Windows 11,
        ``NoOpLimiter`` on all other platforms.
    """
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        return UnixLimiter()
    if sys.platform == "win32":
        return WindowsLimiter()
    return NoOpLimiter()


# ---------------------------------------------------------------------------
# UnixLimiter — resource.setrlimit (Linux / macOS)
# ---------------------------------------------------------------------------


class UnixLimiter(PlatformLimiter):
    """Uses ``resource.setrlimit()`` via ``preexec_fn``.

    Works identically on Linux (kernel 7.1+) and macOS Tahoe (26+).
    Resource limits are applied *before* the child process calls exec,
    using the ``preexec_fn`` parameter of ``subprocess.Popen``.
    """

    def make_preexec_fn(self, limits: ResourceLimits) -> Callable[[], None] | None:
        """Return a callable that sets RLIMIT_AS, RLIMIT_NPROC, and RLIMIT_FSIZE.

        Returns ``None`` if no limits are specified (all ``None``).
        """
        if not limits.max_memory_bytes and not limits.max_processes and not limits.max_file_size_bytes:
            return None

        # Capture limits in closure — will be called in the child process
        mem = limits.max_memory_bytes
        nproc = limits.max_processes
        fsize = limits.max_file_size_bytes

        def _apply_limits() -> None:
            import resource

            if mem is not None:
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            if nproc is not None:
                resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
            if fsize is not None:
                resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))

        return _apply_limits

    def apply_post_start(self, proc: subprocess.Popen[str], limits: ResourceLimits) -> None:
        """No-op on Unix — limits are applied pre-exec."""


# ---------------------------------------------------------------------------
# WindowsLimiter — Win32 Job Objects via ctypes (Windows 11)
# ---------------------------------------------------------------------------


class WindowsLimiter(PlatformLimiter):
    """Uses Win32 Job Objects via ``ctypes.windll.kernel32``.

    Per HITL decision H-2: uses ``OpenProcess()`` with public ``proc.pid``
    (not the private ``proc._handle`` attribute) for forward compatibility.

    Job Objects are the Windows 11 mechanism for per-process resource
    enforcement. The limiter creates a job, sets memory limits via
    ``JOBOBJECT_EXTENDED_LIMIT_INFORMATION``, assigns the process, then
    closes the process handle.
    """

    def make_preexec_fn(self, limits: ResourceLimits) -> None:
        """No preexec_fn on Windows — limits applied post-start."""
        return None

    def apply_post_start(self, proc: subprocess.Popen[str], limits: ResourceLimits) -> None:
        """Create a Job Object, set memory limits, assign process.

        Steps:
        1. ``CreateJobObjectW(None, None)``
        2. ``SetInformationJobObject`` with memory limit
        3. ``OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)``
        4. ``AssignProcessToJobObject(job_handle, proc_handle)``
        5. ``CloseHandle(proc_handle)``
        """
        if not limits.max_memory_bytes:
            return

        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        # 1. Create a Job Object
        job_handle = kernel32.CreateJobObjectW(None, None)
        if not job_handle:
            logger.warning("WindowsLimiter: CreateJobObjectW failed")
            return

        # 2. Set memory limit via JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        #    LimitFlags: JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        job_object_limit_process_memory = 0x00000100
        jobobjectextendedlimitinformation = 9

        # The JOBOBJECT_EXTENDED_LIMIT_INFORMATION structure is complex.
        # We use a raw byte buffer: BasicLimitInformation (48 bytes on x64),
        # then IoInfo (48 bytes), then ProcessMemoryLimit, etc.
        # For simplicity, we use ctypes.Structure.
        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):  # noqa: N801
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class IO_COUNTERS(ctypes.Structure):  # noqa: N801
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):  # noqa: N801
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        ext_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        ext_info.BasicLimitInformation.LimitFlags = job_object_limit_process_memory
        ext_info.ProcessMemoryLimit = limits.max_memory_bytes

        result = kernel32.SetInformationJobObject(
            job_handle,
            jobobjectextendedlimitinformation,
            ctypes.byref(ext_info),
            ctypes.sizeof(ext_info),
        )
        if not result:
            logger.warning("WindowsLimiter: SetInformationJobObject failed")
            kernel32.CloseHandle(job_handle)
            return

        # 3. Open process handle using public .pid (H-2 decision)
        process_all_access = 0x001FFFFF
        proc_handle = kernel32.OpenProcess(process_all_access, False, proc.pid)
        if not proc_handle:
            logger.warning("WindowsLimiter: OpenProcess failed for PID %d", proc.pid)
            kernel32.CloseHandle(job_handle)
            return

        # 4. Assign process to job
        kernel32.AssignProcessToJobObject(job_handle, proc_handle)

        # 5. Close the process handle (job handle stays alive)
        kernel32.CloseHandle(proc_handle)
