# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A write the executor refused is a failed write.

Proves: TECH-072 FR-1

The atom used to discard the executor's answer and report "Replaced symbol" regardless, so a
protected path was refused on disk and reported as done to the agent.

| Bucket | Case |
|---|---|
| Happy | the executor accepts → SUCCESS |
| Degradation | the executor refuses → FAILED, carrying the executor's reason |
| Boundary | every write intent (replace, replace body, delete, add) behaves the same |
| Hostile | not applicable here: the path is judged by the executor, covered by the integration test |
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.filesystem.core.executor import ExecutorResult
from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface


def _atom(write_result: ExecutorResult) -> CodeStructureAtom:
    parser = MagicMock(spec=CodeStructureInterface)
    for op in ("replace_symbol", "replace_symbol_body", "delete_symbol", "add_symbol"):
        getattr(parser, op).return_value = "def hook():\n    return 2\n"
    executor = MagicMock()
    executor.read.return_value = ExecutorResult(
        status="success", data="def hook():\n    return 1\n"
    )
    executor.write.return_value = write_result
    return CodeStructureAtom(executor, parsers={(".py",): parser})


_INTENTS = [
    {"intent": "replace_symbol", "symbol_name": "hook", "new_code": "x"},
    {"intent": "replace_symbol_body", "symbol_name": "hook", "new_code": "x"},
    {"intent": "delete_symbol", "symbol_name": "hook"},
    {"intent": "add_symbol", "target_parent": None, "new_code": "x"},
]


@pytest.mark.parametrize("context", _INTENTS, ids=lambda c: c["intent"])
def test_a_refused_write_is_a_failure(context: dict) -> None:
    refused = ExecutorResult(status="error", error="Protected path: .specweaver/x.py")

    result = _atom(refused).run({**context, "path": ".specweaver/x.py"})

    assert result.status == AtomStatus.FAILED
    assert "Protected path" in result.message


@pytest.mark.parametrize("context", _INTENTS, ids=lambda c: c["intent"])
def test_an_accepted_write_is_a_success(context: dict) -> None:
    result = _atom(ExecutorResult(status="success")).run({**context, "path": "src/x.py"})

    assert result.status == AtomStatus.SUCCESS


def test_an_unknown_write_intent_fails_and_writes_nothing() -> None:
    atom = _atom(ExecutorResult(status="success"))

    result = atom._handle_write_symbol(
        MagicMock(spec=CodeStructureInterface), "code", {}, "rename_symbol", "src/x.py", "hook"
    )

    assert result.status == AtomStatus.FAILED
    assert "Invalid write intent" in result.message
    atom._executor.write.assert_not_called()
