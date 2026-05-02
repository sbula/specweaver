# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_rust
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.ast.parsers.base import BaseTreeSitterParser
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

logger = logging.getLogger(__name__)


class RustCodeStructure(BaseTreeSitterParser):
    def __init__(self) -> None:
        self._language = Language(tree_sitter_rust.language())
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
        (function_item body: (block) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return """
        (use_declaration) @imp
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (struct_item name: (type_identifier) @name)
        (impl_item type: (type_identifier) @name)
        (impl_item type: (generic_type (type_identifier) @name))
        (function_item name: (identifier) @name)
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (line_comment) @comment
        (block_comment) @comment
        """

    def supported_intents(self) -> list[str]:
        return [
            "skeleton", "symbol", "symbol_body", "list", "replace",
            "replace_body", "add", "delete", "traceability", "imports"
        ]

    def supported_parameters(self) -> list[str]:
        return ["visibility"]

    def _is_symbol_public(self, parent: typing.Any) -> bool:
        if parent:
            for child in parent.children:
                if child.type == "visibility_modifier":
                    return True
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

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        if not name_node.parent or name_node.parent.type != "function_item":
            return None
        parent = name_node.parent.parent
        while parent:
            if parent.type == "impl_item":
                type_node = parent.child_by_field_name("type")
                if type_node:
                    if type_node.type == "type_identifier":
                        return typing.cast("bytes", type_node.text).decode("utf-8")
                    elif type_node.type == "generic_type":
                        for gc in type_node.children:
                            if gc.type == "type_identifier":
                                return typing.cast("bytes", gc.text).decode("utf-8")
            parent = parent.parent
        return None

    def _process_symbol_match(self, name_node: typing.Any, target_name: str, target_scope: str | None) -> typing.Any | None:
        node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
        if node_name_str != target_name:
            return None

        scope = self._get_symbol_scope(name_node)
        if scope != target_scope:
            return None

        parent = name_node.parent
        if parent and parent.type == "generic_type":
            parent = parent.parent
        if parent and parent.type in ("function_item", "struct_item", "impl_item"):
            return parent
        return None

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope = None
        target_name = symbol_name
        if "." in symbol_name:
            target_scope, target_name = symbol_name.split(".", 1)

        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        best_match = None
        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    parent = self._process_symbol_match(name_node, target_name, target_scope)
                    if parent:
                        if parent.type == "impl_item":
                            return parent
                        if not best_match:
                            best_match = parent
        return best_match

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        for child in node.children:
            if child.type == "block" or child.type == "declaration_list":
                return child
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

    def extract_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot extract '{symbol_name}' from empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        collected_blocks: list[str] = []
        target_scope = None
        target_name = symbol_name
        if "." in symbol_name:
            target_scope, target_name = symbol_name.split(".", 1)

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    parent = self._process_symbol_match(name_node, target_name, target_scope)
                    if parent:
                        collected_blocks.append(
                            typing.cast("bytes", parent.text).decode("utf-8")
                        )

        if collected_blocks:
            return "\n\n".join(collected_blocks)

        raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")

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
                    if import_text.startswith("pub use "):
                        import_text = import_text[8:].strip()
                    elif import_text.startswith("use "):
                        import_text = import_text[4:].strip()

                    if import_text.endswith(";"):
                        import_text = import_text[:-1].strip()

                    imports.add(import_text.split("{")[0].strip().rstrip(":"))

        return sorted(list(imports))

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        decorators: list[str] = []
        prev = target_node.prev_named_sibling
        temp: list[typing.Any] = []
        while prev and prev.type == "attribute_item":
            temp.insert(0, prev)
            prev = prev.prev_named_sibling

        for dec_node in temp:
            dec_text = self._extract_marker_text(dec_node)
            if dec_text.startswith("#[") and dec_text.endswith("]"):
                dec_text = dec_text[2:-1].strip()
            if dec_text not in decorators:
                decorators.append(dec_text)
        return decorators

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        if not code.strip():
            return {}

        tree = self.parser.parse(code.encode("utf-8"))
        query_str = "(struct_item name: (type_identifier) @name) @cls\n(function_item name: (identifier) @name) @fn"
        cursor = QueryCursor(Query(self.language, query_str))

        markers: dict[str, dict[str, list[str]]] = {}
        for _, match_dict in cursor.matches(tree.root_node):
            if "name" not in match_dict:
                continue
            name_node = match_dict["name"][0]
            symbol = self._extract_marker_text(name_node)
            scope = self._get_symbol_scope(name_node)
            full_name = f"{scope}.{symbol}" if scope else symbol

            is_class = "cls" in match_dict
            target = match_dict["cls"][0] if is_class else match_dict["fn"][0]

            if full_name not in markers:
                markers[full_name] = {"decorators": self._extract_decorators(target)}
                if is_class:
                    markers[full_name]["extends"] = []

        impl_query = Query(self.language, "(impl_item trait: (_) @trait type: (_) @type)")
        for _, impl_match in QueryCursor(impl_query).matches(tree.root_node):
            if "trait" in impl_match and "type" in impl_match:
                trait_name = self._extract_marker_text(impl_match["trait"][0])
                type_name = self._extract_marker_text(impl_match["type"][0])
                if type_name in markers and "extends" in markers[type_name]:
                    markers[type_name]["extends"].append(trait_name)

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

        target_block = None
        for child in node.children:
            if child.type == "block" or child.type == "declaration_list":
                target_block = child
                break

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
        return ["*.rlib", "*.so", "*.dll", "*.pdb"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["target/"]
