# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Rust debugger runs the binary or example its entrypoint names.

Proves: TECH-078 FR-8

| Bucket | Case |
|---|---|
| Happy | `src/bin/cli.rs` runs `--bin cli`; `examples/demo.rs` runs `--example demo` |
| Boundary | `src/main.rs` and an empty entrypoint run the default binary; `src/bin/cli/main.rs` is `cli` |
| Degradation | not applicable — cargo's own failure is covered in `test_rust_runner.py` |
| Hostile | `../x.rs` and a Windows path pass no name cargo would read as another target |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.rust.runner import RustRunner

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("entrypoint", "command"),
    [
        ("src/bin/cli.rs", ["cargo", "run", "--bin", "cli"]),
        ("src/bin/cli/main.rs", ["cargo", "run", "--bin", "cli"]),
        ("examples/demo.rs", ["cargo", "run", "--example", "demo"]),
        ("src\\bin\\cli.rs", ["cargo", "run", "--bin", "cli"]),
        ("src/main.rs", ["cargo", "run"]),
        ("", ["cargo", "run"]),
        ("../x.rs", ["cargo", "run"]),
        ("src/bin/../../evil.rs", ["cargo", "run"]),
        ("src/bin/../main.rs", ["cargo", "run"]),
    ],
)
def test_the_debugger_runs_the_named_entrypoint(
    tmp_path: Path, entrypoint: str, command: list[str]
) -> None:
    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.return_value = SubprocessResult(
        exit_code=0, stdout="hi\n", stderr="", timed_out=False, duration_seconds=0.1
    )

    RustRunner(cwd=tmp_path, executor=executor).run_debugger(target="src/", entrypoint=entrypoint)

    assert list(executor.execute.call_args[0][0]) == command
