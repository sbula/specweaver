# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Migration verification tests for language runners → SubprocessExecutor.

Verifies each runner:
1. Accepts an optional executor parameter (DI)
2. Creates a default executor when none provided
3. Has private _cwd attribute (consistency)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from pathlib import Path


class TestPythonRunnerMigration:
    """Verify PythonQARunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        """PythonQARunner(cwd, executor=mock) stores the provided executor."""
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        """PythonQARunner(cwd) auto-creates a SubprocessExecutor."""
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        runner = PythonQARunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        """PythonQARunner uses _cwd (private) attribute."""
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        runner = PythonQARunner(cwd=tmp_path)
        assert runner._cwd == tmp_path


class TestTypeScriptRunnerMigration:
    """Verify TypeScriptRunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        runner = TypeScriptRunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        runner = TypeScriptRunner(cwd=tmp_path)
        assert runner._cwd == tmp_path


class TestRustRunnerMigration:
    """Verify RustRunner accepts and uses SubprocessExecutor."""

    def test_accepts_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)
        assert runner._executor is mock_executor

    def test_creates_default_executor(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        runner = RustRunner(cwd=tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)

    def test_has_private_cwd(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        runner = RustRunner(cwd=tmp_path)
        assert runner._cwd == tmp_path
