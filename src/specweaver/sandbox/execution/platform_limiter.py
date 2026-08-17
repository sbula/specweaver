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
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
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


def _threads_owned_by(entry: Path, uid: int) -> int | None:
    """Thread count for one `/proc/<pid>` entry, or None if it is not `uid`'s or has gone.

    A process exiting between listing and reading is ordinary, not a reason to fail.
    """
    try:
        status = (entry / "status").read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None

    entry_uid: int | None = None
    threads: int | None = None
    for line in status.splitlines():
        if line.startswith("Uid:"):
            entry_uid = int(line.split()[1])
        elif line.startswith("Threads:"):
            threads = int(line.split()[1])
            break
    return threads if entry_uid == uid else None


def current_task_count() -> int | None:
    """Tasks (threads) owned by the current real UID, or ``None`` if it cannot be determined.

    This is what ``RLIMIT_NPROC`` actually counts — threads, not processes — which is why a cap set
    from a process-shaped intuition is unreachable. Read from ``/proc``; on platforms without it
    (macOS) this returns ``None`` and the caller degrades explicitly rather than guessing.

    Costs ~6 ms on a host with 230 tasks, measured. That is per subprocess launch, against bash
    steps that take orders of magnitude longer, so it is not worth caching — and a cached baseline
    would go stale in exactly the situation the limit exists for.
    """
    proc = Path("/proc")
    if not proc.is_dir():
        return None

    uid = os.getuid()
    counts = [
        threads
        for entry in proc.iterdir()
        if entry.name.isdigit()
        for threads in (_threads_owned_by(entry, uid),)
        if threads is not None
    ]
    return sum(counts) if counts else None


class UnixLimiter(PlatformLimiter):
    """Uses ``resource.setrlimit()`` via ``preexec_fn``.

    Works identically on Linux (kernel 7.1+) and macOS Tahoe (26+).
    Resource limits are applied *before* the child process calls exec,
    using the ``preexec_fn`` parameter of ``subprocess.Popen``.
    """

    def make_preexec_fn(self, limits: ResourceLimits) -> Callable[[], None] | None:
        """Return a callable that sets PR_SET_PDEATHSIG and resource limits.

        Sets PR_SET_PDEATHSIG to SIGKILL on Linux to prevent zombie processes.
        """
        # Capture limits in closure — will be called in the child process
        mem = limits.max_memory_bytes
        fsize = limits.max_file_size_bytes

        # `max_processes` is a budget for THIS sandbox, but RLIMIT_NPROC is per-real-UID and counts
        # tasks (threads). Applying the budget raw caps every task the user owns, and an ordinary
        # machine is already past it before the sandbox forks: 64 processes but 234 tasks against a
        # configured 128, measured on an idle host. Every bash step failed with
        # `fork: retry: Resource temporarily unavailable` after ~15s of retries.
        #
        # So the cap is baseline + budget, bounding what this sandbox may ADD. Counted here in the
        # parent, not in the closure: `preexec_fn` runs after fork where only async-signal-safe work
        # is sound, and walking /proc there is neither safe nor cheap.
        #
        # This is a best-effort backstop, not a real bound — the limit still applies to the whole
        # UID, and the baseline can drift between measurement and exec. A kernel-enforced
        # per-subtree bound via cgroups v2 `pids.max` should REPLACE this rather than layer on
        # top of it.
        nproc: int | None = None
        if limits.max_processes is not None:
            baseline = current_task_count()
            if baseline is None:
                logger.warning(
                    "Cannot read the current task count, so max_processes=%d is not enforced. "
                    "Memory and file-size limits still apply.",
                    limits.max_processes,
                )
            else:
                nproc = baseline + limits.max_processes

        def _apply_limits() -> None:
            import resource
            import sys

            if sys.platform.startswith("linux"):
                try:
                    import ctypes
                    import signal

                    libc = ctypes.CDLL("libc.so.6")
                    libc.prctl(1, signal.SIGKILL)
                except Exception:
                    pass

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
        job_object_limit_kill_on_job_close = 0x00002000
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
        ext_info.BasicLimitInformation.LimitFlags = (
            job_object_limit_process_memory | job_object_limit_kill_on_job_close
        )
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
