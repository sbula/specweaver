# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python-specific standards analyzer using tree-sitter.

Extracts coding conventions from Python source files in a single pass per file, then aggregates
results with recency weighting. The results match what the standard library `ast` gave: only
plain parameters count for type hints, a docstring is a plain string first in the body, and the
test framework is the import nearest the top of the file.

Categories: naming, error_handling, type_hints, docstrings,
            import_patterns, test_patterns.
"""

from __future__ import annotations

import codecs
import logging
from collections import Counter, deque
from typing import TYPE_CHECKING

from specweaver.assurance.standards._documentation import documentation_result
from specweaver.assurance.standards.tree_sitter_base import (
    TreeSitterStyleAnalyzer,
    classify_name,
    vote_result,
)
from specweaver.commons.languages import LANGUAGE_SUFFIXES
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    import tree_sitter

    from specweaver.assurance.standards.analyzer import CategoryResult
    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "naming",
    "error_handling",
    "type_hints",
    "docstrings",
    "import_patterns",
    "test_patterns",
]

#: Test frameworks recognised from an import, longest-prefix irrelevant — both are top-level names.
_TEST_FRAMEWORKS = ("pytest", "unittest")
#: Parameters `ast` lists in `args.args`; a splat or a bare `*` ends them.
_PLAIN = ("identifier", "typed_parameter", "default_parameter", "typed_default_parameter")
_ANNOTATED = ("typed_parameter", "typed_default_parameter")
_SPLATS = ("list_splat_pattern", "dictionary_splat_pattern", "keyword_separator")
#: Children of an `except` clause that are not the exception it names.
_EXCEPT_PARTS = ("except", "*", ":", "block", "comment")

Parsed = list[tuple["Path", float, "tree_sitter.Tree"]]


def _text(node: tree_sitter.Node | None) -> str:
    return node.text.decode("utf-8", errors="replace") if node is not None and node.text else ""


def _nodes(tree: tree_sitter.Tree) -> Iterator[tree_sitter.Node]:
    """Every node, breadth first, as `ast.walk` visits."""
    queue = deque([tree.root_node])
    while queue:
        node = queue.popleft()
        yield node
        queue.extend(node.children)


def _functions(parsed: Parsed) -> Iterator[tuple[float, tree_sitter.Node]]:
    for _path, w, tree in parsed:
        for node in _nodes(tree):
            if node.type == "function_definition":
                yield w, node


def _plain_parameters(function: tree_sitter.Node) -> list[tree_sitter.Node]:
    """The parameters `ast` calls `args.args`: after any `/`, before any `*`."""
    plain: list[tree_sitter.Node] = []
    params = function.child_by_field_name("parameters")
    for child in params.children if params is not None else ():
        if child.type == "positional_separator":
            plain = []
        elif child.type in _SPLATS or (child.children and child.children[0].type in _SPLATS):
            break
        elif child.type in _PLAIN:
            plain.append(child)
    return plain


def _unescaped(content: tree_sitter.Node) -> str:
    """The text of a string's content with each escape sequence decoded, as Python reads it."""
    raw = content.text or b""
    out, pos = [], 0
    for escape in content.named_children:
        if escape.type == "escape_sequence":
            begin, end = (
                escape.start_byte - content.start_byte,
                escape.end_byte - content.start_byte,
            )
            out.append(raw[pos:begin].decode("utf-8", errors="replace"))
            out.append(
                codecs.decode(raw[begin:end].decode("ascii", errors="replace"), "unicode_escape")
            )
            pos = end
    out.append(raw[pos:].decode("utf-8", errors="replace"))
    return "".join(out)


def _leading_string(function: tree_sitter.Node) -> tree_sitter.Node | None:
    """The string that is the body's first statement, if it is one."""
    body = function.child_by_field_name("body")
    first = next((c for c in body.named_children if c.type != "comment"), None) if body else None
    if first is None or first.type != "expression_statement" or first.named_child_count != 1:
        return None
    value = first.named_children[0]
    return value if value.type in ("string", "concatenated_string") else None


def _plain_text(value: tree_sitter.Node) -> str | None:
    """The text of a plain string, or None for an f-, t- or bytes string (no docstring to `ast`)."""
    parts = list(value.named_children) if value.type == "concatenated_string" else [value]
    content = ""
    for part in parts:
        prefix = _text(part.children[0]).lower() if part.children else ""
        if any(flag in prefix for flag in "fbt"):
            return None
        content += "".join(
            _unescaped(piece) for piece in part.named_children if piece.type == "string_content"
        )
    return content


def _has_docstring(function: tree_sitter.Node) -> bool:
    """A plain string, first in the body, holding more than whitespace."""
    value = _leading_string(function)
    text = _plain_text(value) if value is not None else None
    return bool(text and text.strip())


def _module_of(statement: tree_sitter.Node) -> str:
    """The module a `from` import names, without its leading dots."""
    module = statement.child_by_field_name("module_name")
    if module is not None and module.type == "relative_import":
        module = next((c for c in module.named_children if c.type == "dotted_name"), None)
    return _text(module)


def _framework_of(node: tree_sitter.Node) -> str | None:
    """The test framework an import statement names, if it names one."""
    if node.type == "import_statement":
        names = [c.child_by_field_name("name") or c for c in node.named_children]
        return next((n for n in map(_text, names) if n in _TEST_FRAMEWORKS), None)
    if node.type == "import_from_statement":
        module = _module_of(node)
        return next((f for f in _TEST_FRAMEWORKS if module.startswith(f)), None)
    return None


class PythonStandardsAnalyzer(TreeSitterStyleAnalyzer):
    """Extract coding standards from Python source files via tree-sitter."""

    def language_name(self) -> str:
        return "python"

    def file_extensions(self) -> set[str]:
        return set(LANGUAGE_SUFFIXES["python"])

    def supported_categories(self) -> list[str]:
        return list(_CATEGORIES)

    def get_code_structure(self) -> CodeStructureInterface:
        return PythonCodeStructure()

    def get_extractors(self) -> list[Callable[..., CategoryResult]]:
        return [
            self._extract_naming,
            self._extract_error_handling,
            self._extract_type_hints,
            self._extract_docstrings,
            self._extract_imports,
            self._extract_test_patterns,
        ]

    def _readable(self, tree: tree_sitter.Tree) -> bool:
        """A file Python cannot parse is skipped, as before."""
        return not tree.root_node.has_error

    # ------------------------------------------------------------------
    # Category extractors
    # ------------------------------------------------------------------

    def _extract_naming(self, parsed_files: Parsed) -> CategoryResult:
        func_styles: Counter[str] = Counter()
        class_styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            for node in _nodes(tree):
                name = _text(node.child_by_field_name("name"))
                if node.type == "function_definition":
                    if not name.startswith("_"):
                        func_styles[classify_name(name)] += round(w)
                        sample_size += 1
                elif node.type == "class_definition":
                    class_styles[classify_name(name)] += round(w)
                    sample_size += 1

        return vote_result(
            "naming", sample_size, function_style=func_styles, class_style=class_styles
        )

    def _extract_error_handling(self, parsed_files: Parsed) -> CategoryResult:
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            for node in _nodes(tree):
                if node.type == "except_clause":
                    bare = all(c.type in _EXCEPT_PARTS for c in node.children)
                    styles["bare" if bare else "specific"] += round(w)
                    sample_size += 1

        return vote_result("error_handling", sample_size, exception_style=styles)

    def _extract_type_hints(self, parsed_files: Parsed) -> CategoryResult:
        typed: Counter[str] = Counter()
        sample_size = 0

        for w, function in _functions(parsed_files):
            has_annotations = function.child_by_field_name("return_type") is not None or any(
                p.type in _ANNOTATED for p in _plain_parameters(function)
            )
            typed["yes" if has_annotations else "no"] += round(w)
            sample_size += 1

        return vote_result("type_hints", sample_size, usage=typed)

    def _extract_docstrings(self, parsed_files: Parsed) -> CategoryResult:
        functions = [function for _w, function in _functions(parsed_files)]
        documented = sum(1 for function in functions if _has_docstring(function))
        return documentation_result("docstrings", documented, len(functions))

    def _extract_imports(self, parsed_files: Parsed) -> CategoryResult:
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            for node in _nodes(tree):
                if node.type in ("import_statement", "future_import_statement"):
                    styles["absolute"] += round(w)
                    sample_size += 1
                elif node.type == "import_from_statement":
                    module = node.child_by_field_name("module_name")
                    relative = module is not None and module.type == "relative_import"
                    styles["relative" if relative else "absolute"] += round(w)
                    sample_size += 1

        return vote_result("import_patterns", sample_size, style=styles)

    def _extract_test_patterns(self, parsed_files: Parsed) -> CategoryResult:
        frameworks: Counter[str] = Counter()
        sample_size = 0

        for path, w, tree in parsed_files:
            if not path.name.startswith("test_") and not path.name.endswith("_test.py"):
                continue

            framework = next(filter(None, map(_framework_of, _nodes(tree))), None)
            if framework:
                frameworks[framework] += round(w)
                sample_size += 1

        return vote_result("test_patterns", sample_size, framework=frameworks)
