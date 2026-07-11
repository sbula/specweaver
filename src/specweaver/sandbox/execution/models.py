# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Data models for subprocess execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.commons.qa import OutputEvent


@dataclass(frozen=True)
class ResourceLimits:
    """Cross-platform resource constraints for subprocess execution.

    All fields default to ``None``, meaning no limit is enforced.
    """

    max_memory_bytes: int | None = None
    """Virtual memory limit in bytes."""

    max_processes: int | None = None
    """Maximum number of child processes (fork bomb protection)."""

    max_file_size_bytes: int | None = None
    """Maximum output file size in bytes."""


@dataclass(frozen=True)
class SubprocessResult:
    """Structured result from a subprocess execution.

    Returned by :meth:`SubprocessExecutor.execute`. Contains the raw
    stdout/stderr as well as structured ``OutputEvent`` objects and
    telemetry data.
    """

    exit_code: int
    """Process exit code (0 = success, negative = signal-killed)."""

    stdout: str
    """Captured standard output as text."""

    stderr: str
    """Captured standard error as text."""

    duration_seconds: float
    """Wall-clock execution time in seconds."""

    timed_out: bool = False
    """Whether the process was killed due to timeout."""

    events: list[OutputEvent] = field(default_factory=list)
    """Structured output events (stdout/stderr lines as OutputEvent)."""
