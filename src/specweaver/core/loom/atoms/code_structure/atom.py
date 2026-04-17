# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CodeStructureAtom — provides read access to the AST parsing Engine."""

from __future__ import annotations

import logging
import typing
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.core.loom.atoms.base import Atom, AtomResult, AtomStatus
from specweaver.core.loom.commons.language.interfaces import (
    CodeStructureError,
    CodeStructureInterface,
)

if TYPE_CHECKING:
    from specweaver.core.loom.commons.filesystem.executor import FileExecutor
from specweaver.core.loom.commons.language.java.codestructure import JavaCodeStructure
from specweaver.core.loom.commons.language.kotlin.codestructure import KotlinCodeStructure
from specweaver.core.loom.commons.language.markdown.codestructure import MarkdownCodeStructure
from specweaver.core.loom.commons.language.python.codestructure import PythonCodeStructure
from specweaver.core.loom.commons.language.rust.codestructure import RustCodeStructure
from specweaver.core.loom.commons.language.typescript.codestructure import TypeScriptCodeStructure

logger = logging.getLogger(__name__)


class CodeStructureAtom(Atom):
    """Atom for retrieving AST structural bounds from project source code."""

    def __init__(self, file_executor: FileExecutor | None = None, cwd: Path | None = None, evaluator_schemas: dict[str, Any] | None = None) -> None:
        """Initialize with a FileExecutor or construct one if cwd is provided."""
        if file_executor:
            self._executor = file_executor
        elif cwd:
            from specweaver.core.loom.commons.filesystem.executor import FileExecutor

            self._executor = FileExecutor(cwd=cwd)
        else:
            raise ValueError("CodeStructureAtom requires either file_executor or cwd")
        self._evaluator_schemas = evaluator_schemas or {}

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
        if ext in (".md",):
            return MarkdownCodeStructure()
        return None

    def _handle_structure(self, parser: CodeStructureInterface, code: str, path: str) -> AtomResult:
        try:
            skeleton = parser.extract_skeleton(code)
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Extracted skeleton for {path}",
                exports={"structure": skeleton},
            )
        except CodeStructureError as err:
            return AtomResult(status=AtomStatus.FAILED, message=str(err))

    def _handle_list(
        self, parser: CodeStructureInterface, code: str, context: dict[str, Any], path: str
    ) -> AtomResult:
        try:
            visibility = context.get("visibility")
            symbols = parser.list_symbols(code, visibility=visibility)
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Listed symbols for {path}",
                exports={"symbols": symbols},
            )
        except CodeStructureError as err:
            return AtomResult(status=AtomStatus.FAILED, message=str(err))

    def _handle_symbol(
        self,
        parser: CodeStructureInterface,
        code: str,
        context: dict[str, typing.Any],
        intent: str,
        path: str,
    ) -> AtomResult:
        symbol_name = context.get("symbol_name")

        try:
            if intent in ("read_symbol", "read_symbol_body", "read_unrolled_symbol"):
                if not symbol_name:
                    return AtomResult(
                        status=AtomStatus.FAILED,
                        message="Missing 'symbol_name' for symbol extraction.",
                    )
                return self._handle_read_symbol(parser, code, symbol_name, intent, path)
            else:
                return self._handle_write_symbol(parser, code, context, intent, path, symbol_name)
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
            return AtomResult(
                status=AtomStatus.FAILED, message="Missing required fields: 'intent' or 'path'."
            )

        valid_intents = {
            "read_file_structure",
            "read_symbol",
            "read_symbol_body",
            "read_unrolled_symbol",
            "list_symbols",
            "replace_symbol",
            "replace_symbol_body",
            "add_symbol",
            "delete_symbol",
            "extract_framework_markers",
        }
        if intent not in valid_intents:
            return AtomResult(
                status=AtomStatus.FAILED, message=f"Unsupported code structure intent: {intent}"
            )

        parser = self._get_parser(path)
        if not parser:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"AST Structure Extraction not supported for '{Path(path).suffix}' files. Please use read_file instead.",
            )

        read_res = self._executor.read(path)
        if read_res.status == "error":
            return AtomResult(status=AtomStatus.FAILED, message=read_res.error)

        code = str(read_res.data)

        if intent == "read_file_structure":
            return self._handle_structure(parser, code, path)
        if intent == "extract_framework_markers":
            return self._handle_framework_markers(parser, code, path)
        if intent == "list_symbols":
            return self._handle_list(parser, code, context, path)
        return self._handle_symbol(parser, code, context, intent, path)

    def _handle_framework_markers(
        self, parser: CodeStructureInterface, code: str, path: str
    ) -> AtomResult:
        try:
            markers = parser.extract_framework_markers(code)
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Extracted markers for {path}",
                exports={"markers": markers},
            )
        except CodeStructureError as err:
            return AtomResult(status=AtomStatus.FAILED, message=str(err))

    def _handle_read_symbol(
        self, parser: CodeStructureInterface, code: str, symbol_name: str, intent: str, path: str
    ) -> AtomResult:
        if intent == "read_symbol":
            symbol_code = parser.extract_symbol(code, symbol_name)
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Extracted symbol '{symbol_name}'",
                exports={"symbol": symbol_code},
            )
        elif intent == "read_symbol_body":
            body_code = parser.extract_symbol_body(code, symbol_name)
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Extracted body of '{symbol_name}'",
                exports={"body": body_code},
            )
        elif intent == "read_unrolled_symbol":
            symbol_code = parser.extract_symbol(code, symbol_name)
            all_markers = parser.extract_framework_markers(code)
            symbol_markers = all_markers.get(symbol_name, {})

            from specweaver.core.loom.commons.language.evaluator import SchemaEvaluator
            evaluator = SchemaEvaluator(self._evaluator_schemas)

            ext = Path(path).suffix.lower()
            lang_map = {
                ".py": "python",
                ".java": "java",
                ".kt": "kotlin",
                ".kts": "kotlin",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".rs": "rust"
            }
            language = lang_map.get(ext, "")

            try:
                explanation = evaluator.evaluate_markers(language, symbol_markers)
            except Exception as e:
                return AtomResult(status=AtomStatus.FAILED, message=f"Evaluator error: {e!s}")

            if explanation:
                symbol_code = f"{explanation}\n{symbol_code}"

            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Extracted and evaluated unrolled symbol '{symbol_name}'",
                exports={"symbol": symbol_code},
            )
        return AtomResult(status=AtomStatus.FAILED, message="Invalid read intent")

    def _handle_write_symbol(
        self,
        parser: CodeStructureInterface,
        code: str,
        context: dict[str, typing.Any],
        intent: str,
        path: str,
        symbol_name: str | None,
    ) -> AtomResult:
        if intent in ("replace_symbol", "replace_symbol_body", "delete_symbol") and not symbol_name:
            return AtomResult(
                status=AtomStatus.FAILED, message=f"Missing 'symbol_name' for {intent}."
            )

        if intent == "replace_symbol":
            new_code = context.get("new_code", "")
            mutated = parser.replace_symbol(code, symbol_name, new_code)  # type: ignore
            self._executor.write(path, mutated)
            return AtomResult(status=AtomStatus.SUCCESS, message=f"Replaced symbol '{symbol_name}'")
        elif intent == "replace_symbol_body":
            new_code = context.get("new_code", "")
            mutated = parser.replace_symbol_body(code, symbol_name, new_code)  # type: ignore
            self._executor.write(path, mutated)
            return AtomResult(
                status=AtomStatus.SUCCESS, message=f"Replaced body of symbol '{symbol_name}'"
            )
        elif intent == "delete_symbol":
            mutated = parser.delete_symbol(code, symbol_name)  # type: ignore
            self._executor.write(path, mutated)
            return AtomResult(status=AtomStatus.SUCCESS, message=f"Deleted symbol '{symbol_name}'")
        elif intent == "add_symbol":
            new_code = context.get("new_code", "")
            target_parent = context.get("target_parent")
            mutated = parser.add_symbol(code, target_parent, new_code)
            self._executor.write(path, mutated)
            return AtomResult(
                status=AtomStatus.SUCCESS, message=f"Added new symbol inside '{target_parent}'"
            )
        return AtomResult(status=AtomStatus.FAILED, message="Invalid write intent")
