# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_typescript
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.parsers.base import BaseTreeSitterParser
from specweaver.workspace.parsers.interfaces import CodeStructureError

logger = logging.getLogger(__name__)


class TypeScriptCodeStructure(BaseTreeSitterParser):
    def __init__(self) -> None:
        self._language = Language(tree_sitter_typescript.language_typescript())
        self._parser = Parser(self._language)

    @property
    def language(self) -> Language:
        return self._language

    @property
    def parser(self) -> Parser:
        return self._parser

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration body: (statement_block) @block)
        (method_definition body: (statement_block) @block)
        (arrow_function body: (statement_block) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return """
        (import_statement) @imp
        (import_require_clause) @imp
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration name: (identifier) @name)
        (method_definition name: (property_identifier) @name)
        (class_declaration name: (type_identifier) @name)
        (variable_declarator name: (identifier) @name value: (arrow_function))
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (comment) @comment
        """

    def _is_symbol_public(self, parent: typing.Any) -> bool:
        while parent:
            if parent.type == "export_statement":
                return True
            parent = parent.parent
        return False

    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        if (
            visibility
            and "public" in visibility
            and name_node
            and not self._is_symbol_public(name_node.parent)
        ):
            return False

        if decorator_filter:
            decs = framework_markers.get(sym_name, {}).get("decorators", [])
            if not any(decorator_filter in d for d in decs):
                return False

        return True

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                    if node_name_str == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type in (
                            "function_declaration",
                            "method_definition",
                            "class_declaration",
                            "variable_declarator",
                        ):
                            wrapper = parent
                            if (
                                wrapper.type == "variable_declarator"
                                and wrapper.parent
                                and wrapper.parent.type == "lexical_declaration"
                            ):
                                wrapper = wrapper.parent
                            if wrapper.parent and wrapper.parent.type == "export_statement":
                                wrapper = wrapper.parent
                            return wrapper
        return None

    def _search_declarator(self, child: typing.Any) -> typing.Any | None:
        for sub2 in child.children:
            if sub2.type == "arrow_function":
                for sub3 in sub2.children:
                    if sub3.type == "statement_block":
                        return sub3
        return None

    def _extract_arrow_block(self, child: typing.Any) -> typing.Any | None:
        if child.type == "variable_declarator":
            res = self._search_declarator(child)
            if res:
                return res
        elif child.type == "arrow_function":
            for sub3 in child.children:
                if sub3.type == "statement_block":
                    return sub3
        for sub in child.children:
            res = self._extract_arrow_block(sub)
            if res:
                return res
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        if node.type == "export_statement":
            for child in node.children:
                res = self._find_target_block(child)
                if res:
                    return res
        for child in node.children:
            if child.type == "statement_block" or child.type == "class_body":
                return child
            elif child.type == "lexical_declaration" or child.type == "variable_declarator":
                res = self._extract_arrow_block(child)
                if res:
                    return res
        return None

    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")
        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        return code_bytes[:start_byte] + indented_code + code_bytes[end_byte:]

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
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

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        query = Query(self.language, self.SCM_IMPORT_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        imports = set()
        for _, match_dict in matches:
            if "imp" in match_dict:
                for node in match_dict["imp"]:
                    import_text = typing.cast("bytes", node.text).decode("utf-8").strip()
                    if " from " in import_text:
                        module_part = import_text.split(" from ")[-1].strip()
                    else:
                        module_part = (
                            import_text.replace("import ", "")
                            .replace("require(", "")
                            .replace(")", "")
                            .strip()
                        )

                    if module_part.endswith(";"):
                        module_part = module_part[:-1].strip()
                    if module_part.startswith(("'", '"')) and module_part.endswith(("'", '"')):
                        module_part = module_part[1:-1]

                    imports.add(module_part)

        return sorted(list(imports))

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        bases = []
        for child in target_node.children:
            if child.type == "class_heritage":
                for clause in child.children:
                    if clause.type in ("extends_clause", "implements_clause"):
                        for t in clause.children:
                            if t.type in ("identifier", "type_identifier"):
                                bases.append(self._extract_marker_text(t))
                            elif t.type == "type_list":
                                for sub in t.children:
                                    if sub.type in ("identifier", "type_identifier"):
                                        bases.append(self._extract_marker_text(sub))
        return bases

    def _add_dec(self, child: typing.Any, decorators: list[str]) -> None:
        dec_text = self._extract_marker_text(child)
        if dec_text.startswith("@"):
            dec_text = dec_text[1:]
        if dec_text not in decorators:
            decorators.append(dec_text)

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        decorators: list[str] = []
        parent = target_node.parent
        if parent and parent.type == "export_statement":
            target_node = parent

        for child in target_node.children:
            if child.type == "decorator":
                self._add_dec(child, decorators)

        if target_node.type == "method_definition":
            prev = target_node.prev_named_sibling
            temp: list[typing.Any] = []
            while prev and prev.type == "decorator":
                temp.insert(0, prev)
                prev = prev.prev_named_sibling
            for dec_node in temp:
                self._add_dec(dec_node, decorators)

        return decorators

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        if not code.strip():
            return {}
        tree = self.parser.parse(code.encode("utf-8"))
        query_str = "(class_declaration name: (type_identifier) @name) @cls\n(method_definition name: (property_identifier) @name) @fn\n(function_declaration name: (identifier) @name) @fn"
        cursor = QueryCursor(Query(self.language, query_str))

        markers: dict[str, dict[str, list[str]]] = {}
        for _, match_dict in cursor.matches(tree.root_node):
            if "name" not in match_dict:
                continue
            symbol = self._extract_marker_text(match_dict["name"][0])
            is_class = "cls" in match_dict
            target = match_dict["cls"][0] if is_class else match_dict["fn"][0]

            if symbol not in markers:
                markers[symbol] = {"decorators": self._extract_decorators(target)}
                if is_class:
                    markers[symbol]["extends"] = self._extract_bases(target)
        return markers

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        code_bytes = code.encode("utf-8")
        if not target_parent:
            indented_code = self._auto_indent(new_code, 0).encode("utf-8")
            if not code.endswith("\n"):
                return (code_bytes + b"\n\n" + indented_code).decode("utf-8")
            return (code_bytes + b"\n" + indented_code).decode("utf-8")

        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, target_parent)
        if not node:
            raise CodeStructureError(f"Parent symbol '{target_parent}' not found.")

        target_block = self._find_target_block(node)

        if not target_block:
            raise CodeStructureError(f"Body block for parent symbol '{target_parent}' not found.")

        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")

        insert_point = target_block.end_byte - 1
        mutated = (
            code_bytes[:insert_point]
            + (b" " * (margin + 4))
            + indented_code
            + b"\n"
            + (b" " * margin)
            + code_bytes[insert_point:]
        )
        return mutated.decode("utf-8")

    def get_binary_ignore_patterns(self) -> list[str]:
        return []

    def get_default_directory_ignores(self) -> list[str]:
        return ["node_modules/", "dist/", "build/", "out/"]
