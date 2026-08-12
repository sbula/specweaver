# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Editing a parsed file: replacing, injecting and deleting symbols.

`TECH-035`, split from `BaseTreeSitterParser` alongside `_reading.py`. The two share nothing —
zero cross-references, each depending only on the per-language contract — so this is a move, not a
rewrite.

A mixin rather than a collaborator, so no parser's public API changes.
"""

from __future__ import annotations

import logging
import typing

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

logger = logging.getLogger(__name__)


class SymbolEditingMixin:
    """Replacing a symbol or its body, injecting into a block, and deleting."""

    # Declared for the type checker only — see the note in `_reading.py`.
    if typing.TYPE_CHECKING:

        @property
        def parser(self) -> typing.Any: ...

        def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None: ...
        def _find_target_block(self, node: typing.Any) -> typing.Any | None: ...
        def _format_replacement(
            self, code_bytes: bytes, node: typing.Any, new_code: str
        ) -> bytes: ...
        def _format_body_injection(
            self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
        ) -> bytes: ...

    def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace '{symbol_name}' in empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)

        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        mutated = self._format_replacement(code_bytes, node, new_code)
        return mutated.decode("utf-8")

    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace body of '{symbol_name}' in empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        target_block = self._find_target_block(node)
        if not target_block:
            raise CodeStructureError(f"Body block for symbol '{symbol_name}' not found.")

        margin = typing.cast("int", node.start_point[1])
        mutated = self._format_body_injection(code_bytes, target_block, new_code, margin)
        return mutated.decode("utf-8")

    def delete_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            return code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)

        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        mutated = code_bytes[:start_byte] + code_bytes[end_byte:]
        return mutated.decode("utf-8")

    def _auto_indent(self, new_code: str, margin: int) -> str:
        if not new_code:
            return new_code
        lines = new_code.split("\n")
        padded = []
        for i, line in enumerate(lines):
            if i == 0:
                padded.append(line)
            else:
                if line.strip() == "":
                    padded.append(line)
                else:
                    padded.append((" " * margin) + line)
        return "\n".join(padded)
