# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Shared scaffolding for the container-executor tests.

These lived inside `test_container_executor.py` until the prepare-phase tests grew their own module
and both files needed them. They are deliberately plain functions rather than fixtures: the mounts
have to be built once and then prepared *twice* to exercise the cache stamp, which a
function-scoped fixture cannot express.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.execution.models import ContainerMounts, SubprocessResult

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock


def ok_result(stdout: str = "", exit_code: int = 0) -> SubprocessResult:
    return SubprocessResult(exit_code=exit_code, stdout=stdout, stderr="", duration_seconds=0.01)


def mounts(tmp_path: Path) -> ContainerMounts:
    source_root = tmp_path / "project"
    source_root.mkdir()
    return ContainerMounts(
        source_root=source_root,
        scratch_root=source_root / ".specweaver" / ".sandbox" / "scratch",
        cache_root=source_root / ".specweaver" / ".sandbox" / "cache",
    )


def find_call(mock_execute: MagicMock, *needles: str) -> list | None:
    """Return the argv of the first recorded call containing all needles, or None."""
    for call in mock_execute.call_args_list:
        argv = call.args[0] if call.args else call.kwargs.get("cmd")
        if argv and all(any(needle in str(part) for part in argv) for needle in needles):
            return argv
    return None
