# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Editing a parsed file: replacing, injecting and deleting symbols.

Separate from `_reading.py` because the two share nothing: zero cross-references, each depending
only on the per-language contract.

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

    def _replacement_bytes(self, new_code: str, node: typing.Any) -> bytes:
        """The bytes to splice in, re-indented to the node's column.

        The ONE thing the ten per-language copies of `_format_replacement` varied by. C, C++ and
        Markdown override this to splice verbatim: brace blocks and Markdown sections carry their
        own layout, so re-indenting them corrupts the block rather than aligning it.
        """
        margin = typing.cast("int", node.start_point[1])
        return self._auto_indent(new_code, margin).encode("utf-8")

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        """Insert `new_code` inside a brace-delimited block, indented one level in.

        Shared by `java`, `kotlin`, `rust` and `typescript`. The `+1` and `-1` step over the
        block's own braces, so this is the **brace-block** form; a language
        whose block is not brace-delimited overrides it — `python` splices the whole suite, `go`,
        `c` and `cpp` hunt for the brace children, `sql` and `markdown` have no executable body at
        all. A default, never a prohibition.
        """
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")
        insert_start = target_block.start_byte + 1
        insert_end = target_block.end_byte - 1
        return (
            code_bytes[:insert_start]
            + b"\n"
            + (b" " * (margin + 4))
            + indented_code
            + b"\n"
            + (b" " * margin)
            + code_bytes[insert_end:]
        )

    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        """Replace the node's byte span with `new_code`.

        Shared by every language whose splice is a byte-span replacement, the per-language part
        being :meth:`_replacement_bytes`. A **default, not a prohibition**: a language whose splice
        is genuinely different still overrides this outright.
        """
        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        return (
            code_bytes[:start_byte]
            + self._replacement_bytes(new_code, node)
            + code_bytes[end_byte:]
        )

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
