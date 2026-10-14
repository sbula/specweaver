# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript enums and interfaces, and Rust enums, are symbols like any class.

Proves: D-SENS-06 FR-9

| Bucket | Case |
|---|---|
| Happy | listed, read, replaced, deleted |
| Boundary | an interface's method signatures are listed under it; an exported enum |
| Degradation | a file with only an enum still parses after the enum is deleted |
| Hostile | an enum member is not a symbol |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

_TS = """export enum Color {
  Red,
  Green,
}

export interface Shape {
  area(): number;
  name: string;
}

export class Square implements Shape {
  name = "square";
  area(): number {
    return 1;
  }
}
"""

_RUST = """pub enum Color {
    Red,
    Green,
}

pub struct Square;
"""

_CASES = [
    (TypeScriptCodeStructure, _TS, "Color", "Red,"),
    (TypeScriptCodeStructure, _TS, "Shape", "area(): number;"),
    (RustCodeStructure, _RUST, "Color", "Red,"),
]


def test_typescript_lists_enums_interfaces_and_their_methods() -> None:
    symbols = TypeScriptCodeStructure().list_symbols(_TS)

    assert {"Color", "Shape", "Shape.area", "Square", "Square.area"} <= set(symbols)
    assert "Red" not in symbols
    assert "Color.Red" not in symbols


def test_rust_lists_enums() -> None:
    symbols = RustCodeStructure().list_symbols(_RUST)

    assert {"Color", "Square"} <= set(symbols)
    assert "Red" not in symbols


@pytest.mark.parametrize(("parser_cls", "code", "symbol", "inside"), _CASES)
def test_an_enum_or_interface_reads_whole(parser_cls, code: str, symbol: str, inside: str) -> None:  # type: ignore[no-untyped-def]
    text = parser_cls().extract_symbol(code, symbol)
    assert inside in text
    assert text.rstrip().endswith("}")


@pytest.mark.parametrize(("parser_cls", "code", "symbol", "inside"), _CASES)
def test_an_enum_or_interface_is_replaced_and_deleted(
    parser_cls, code: str, symbol: str, inside: str
) -> None:  # type: ignore[no-untyped-def]
    parser = parser_cls()
    replaced = parser.replace_symbol(
        code, symbol, parser.extract_symbol(code, symbol).replace(inside, "Blue,")
    )
    deleted = parser.delete_symbol(code, symbol)

    assert "Blue," in replaced
    assert inside not in deleted
    assert symbol not in parser.list_symbols(deleted)
    assert not parser.parser.parse(deleted.encode()).root_node.has_error


def test_an_interface_method_reads_as_its_signature() -> None:
    text = TypeScriptCodeStructure().extract_symbol(_TS, "Shape.area")
    assert text.strip().startswith("area(): number")
