# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import time
from pathlib import Path

import pytest

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom
from specweaver.core.loom.commons.filesystem.executor import EngineFileExecutor


@pytest.mark.asyncio
async def test_integration_flow_skeletonize_di(tmp_path: Path) -> None:
    """Story 4: Complete Pipeline Context Condensation integration bounds."""
    # Scaffold generic project
    test_file = tmp_path / "test.py"
    test_file.write_text("def my_func():\n    print('hello')\n")

    # 1. Pipeline Runner instantiates Context (Invoking DI Hotfix)
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "test.md")
    assert ctx.parsers is not None, "Hotfix failed to inject default parsers dictionaries."

    # 2. Handlers instantiate isolated Atoms passing DI map
    executor = EngineFileExecutor(tmp_path)
    atom = CodeStructureAtom(executor, parsers=ctx.parsers)

    # 3. PromptBuilder triggers skeletonize condensation bounds natively
    t0 = time.time()
    result = atom.run({"intent": "skeletonize", "path": "test.py"})
    t1 = time.time()

    # 4. Asserts E2E Structural Extraction
    assert result.status.value == "SUCCESS"
    assert "def my_func():" in result.exports["structure"]
    assert "print('hello')" not in result.exports["structure"]

    # 5. Assert NFR-1 Latency Bound (< 1.0s) mathematically on live native tree-sitter C execution
    assert (t1 - t0) < 1.0, f"NFR-1 Violation: Context Condensation took {t1 - t0}s!"
