# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Any
from unittest.mock import MagicMock

from specweaver.core.loom.atoms.base import AtomStatus
from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom


def test_atom_routing_reads() -> None:
    executor = MagicMock()
    atom = CodeStructureAtom(executor)

    # Mock the parser extraction directly for isolation
    parser = MagicMock()
    parser.extract_symbol.return_value = "symbol code"
    parser.extract_symbol_body.return_value = "body code"

    # read_symbol
    res = atom._handle_read_symbol(parser, "ignored", "my_func", "read_symbol", "test.py")
    assert res.status == AtomStatus.SUCCESS
    assert res.exports["symbol"] == "symbol code"

    # read_symbol_body
    res = atom._handle_read_symbol(parser, "ignored", "my_func", "read_symbol_body", "test.py")
    assert res.status == AtomStatus.SUCCESS
    assert res.exports["body"] == "body code"

    # invalidate read
    res = atom._handle_read_symbol(parser, "ignored", "my_func", "unknown", "test.py")
    assert res.status == AtomStatus.FAILED


def test_atom_routing_writes_bypass_executor() -> None:
    executor = MagicMock()
    atom = CodeStructureAtom(executor)

    parser = MagicMock()
    parser.replace_symbol.return_value = "replaced"
    parser.replace_symbol_body.return_value = "replaced body"
    parser.delete_symbol.return_value = "deleted"
    parser.add_symbol.return_value = "added"

    path = "/fake/abs/path.py"
    context: dict[str, Any] = {"new_code": "code", "target_parent": "Parent"}

    # replace_symbol
    res = atom._handle_write_symbol(parser, "code", context, "replace_symbol", path, "my_func")
    assert res.status == AtomStatus.SUCCESS
    executor.write.assert_called_with(path, "replaced")

    # replace_symbol_body
    res = atom._handle_write_symbol(parser, "code", context, "replace_symbol_body", path, "my_func")
    assert res.status == AtomStatus.SUCCESS
    executor.write.assert_called_with(path, "replaced body")

    # delete_symbol
    res = atom._handle_write_symbol(parser, "code", context, "delete_symbol", path, "my_func")
    assert res.status == AtomStatus.SUCCESS
    executor.write.assert_called_with(path, "deleted")

    # add_symbol
    res = atom._handle_write_symbol(parser, "code", context, "add_symbol", path, None)
    assert res.status == AtomStatus.SUCCESS
    executor.write.assert_called_with(path, "added")

    # missing symbol_name error for replace/delete
    res = atom._handle_write_symbol(parser, "code", context, "replace_symbol", path, None)
    assert res.status == AtomStatus.FAILED
    assert "Missing" in res.message
