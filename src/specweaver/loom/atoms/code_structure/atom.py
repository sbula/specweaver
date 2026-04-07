# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""CodeStructureAtom — provides read access to the AST parsing Engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.loom.atoms.base import Atom, AtomResult, AtomStatus
from specweaver.loom.commons.language.interfaces import CodeStructureError, CodeStructureInterface

if TYPE_CHECKING:
    from specweaver.loom.commons.filesystem.executor import FileExecutor
from specweaver.loom.commons.language.java.codestructure import JavaCodeStructure
from specweaver.loom.commons.language.kotlin.codestructure import KotlinCodeStructure
from specweaver.loom.commons.language.python.codestructure import PythonCodeStructure
from specweaver.loom.commons.language.rust.codestructure import RustCodeStructure
from specweaver.loom.commons.language.typescript.codestructure import TypeScriptCodeStructure

logger = logging.getLogger(__name__)


class CodeStructureAtom(Atom):
    """Atom for retrieving AST structural bounds from project source code."""

    def __init__(self, file_executor: FileExecutor) -> None:
        """Initialize with a pre-configured FileExecutor for security limits."""
        self._executor = file_executor

    def _get_parser(self, path: str) -> CodeStructureInterface | None:
        """Map a file extension to its respective TreeSitter AST parser."""
        ext = Path(path).suffix.lower()
        if ext in (".py",):
            return PythonCodeStructure()
        if ext in (".ts", ".tsx", ".js", ".jsx"):
            return TypeScriptCodeStructure()
        if ext in (".java",):
            return JavaCodeStructure()
        if ext in (".kt", ".kts"):
            return KotlinCodeStructure()
        if ext in (".rs",):
            return RustCodeStructure()
        return None

    def _handle_structure(self, parser: CodeStructureInterface, code: str, path: str) -> AtomResult:
        try:
            skeleton = parser.extract_skeleton(code)
            return AtomResult(status=AtomStatus.SUCCESS, message=f"Extracted skeleton for {path}", exports={"structure": skeleton})
        except CodeStructureError as err:
            return AtomResult(status=AtomStatus.FAILED, message=str(err))

    def _handle_list(self, parser: CodeStructureInterface, code: str, context: dict[str, Any], path: str) -> AtomResult:
        try:
            visibility = context.get("visibility")
            symbols = parser.list_symbols(code, visibility=visibility)
            return AtomResult(status=AtomStatus.SUCCESS, message=f"Listed symbols for {path}", exports={"symbols": symbols})
        except CodeStructureError as err:
            return AtomResult(status=AtomStatus.FAILED, message=str(err))

    def _handle_symbol(self, parser: CodeStructureInterface, code: str, context: dict[str, Any], intent: str) -> AtomResult:
        symbol_name = context.get("symbol_name")
        if not symbol_name:
            return AtomResult(status=AtomStatus.FAILED, message="Missing 'symbol_name' for symbol extraction.")

        try:
            if intent == "read_symbol":
                symbol_code = parser.extract_symbol(code, symbol_name)
                return AtomResult(status=AtomStatus.SUCCESS, message=f"Extracted symbol '{symbol_name}'", exports={"symbol": symbol_code})
            else:
                body_code = parser.extract_symbol_body(code, symbol_name)
                return AtomResult(status=AtomStatus.SUCCESS, message=f"Extracted body of '{symbol_name}'", exports={"body": body_code})
        except CodeStructureError as err:
            return AtomResult(status=AtomStatus.FAILED, message=str(err))

    def run(self, context: dict[str, Any]) -> AtomResult:
        """Execute the code structure request.

        Args:
            context: Dictionary containing:
                - intent: "read_file_structure", "read_symbol", "read_symbol_body", or "list_symbols"
                - path: Relative path to the target file.
                - symbol_name: (Optional) Limit payload to this symbol.
                - visibility: (Optional) Filter for list_symbols.
        """
        intent = context.get("intent")
        path = context.get("path")

        if not intent or not path:
            return AtomResult(status=AtomStatus.FAILED, message="Missing required fields: 'intent' or 'path'.")

        valid_intents = {"read_file_structure", "read_symbol", "read_symbol_body", "list_symbols"}
        if intent not in valid_intents:
            return AtomResult(status=AtomStatus.FAILED, message=f"Unsupported code structure intent: {intent}")

        parser = self._get_parser(path)
        if not parser:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"AST Structure Extraction not supported for '{Path(path).suffix}' files. Please use read_file instead."
            )

        read_res = self._executor.read(path)
        if read_res.status == "error":
            return AtomResult(status=AtomStatus.FAILED, message=read_res.error)

        code = str(read_res.data)

        if intent == "read_file_structure":
            return self._handle_structure(parser, code, path)
        if intent == "list_symbols":
            return self._handle_list(parser, code, context, path)
        return self._handle_symbol(parser, code, context, intent)
