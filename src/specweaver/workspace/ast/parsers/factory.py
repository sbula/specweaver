# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Factory providing pure dependency injection map for polyglot structural AST parsers.

This centralizes the physical instantiation of CodeStructureInterfaces so orchestrators
(like the Flow engine) can inject them without violating architectural boundaries.
"""

import logging
from collections.abc import Mapping
from functools import cache
from pathlib import PurePath
from types import MappingProxyType

from specweaver.commons.languages import LANGUAGE_SUFFIXES, language_of
from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure
from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.javascript.codestructure import JavaScriptCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

logger = logging.getLogger(__name__)


#: A file ending → its parser registry, as `get_default_parsers` returns it.
Registry = Mapping[tuple[str, ...], CodeStructureInterface]


@cache
def get_default_parsers() -> Registry:
    """The registry of file endings to their parsers, built once per process and read-only.

    Sharing the parsers across threads is safe: py-tree-sitter holds the GIL for a whole parse.
    """
    logger.debug("get_default_parsers: building the parser registry")
    by_language = {
        "c": CCodeStructure(),
        "cpp": CppCodeStructure(),
        "python": PythonCodeStructure(),
        "java": JavaCodeStructure(),
        "typescript": TypeScriptCodeStructure(),
        "javascript": JavaScriptCodeStructure(),
        "rust": RustCodeStructure(),
        "kotlin": KotlinCodeStructure(),
        "go": GoCodeStructure(),
    }
    parsers: dict[tuple[str, ...], CodeStructureInterface] = {
        LANGUAGE_SUFFIXES[name]: parser for name, parser in by_language.items()
    }
    # Not programming languages, so not in the table.
    parsers[(".md", ".mdx")] = MarkdownCodeStructure()
    parsers[(".sql",)] = SqlCodeStructure()
    return MappingProxyType(parsers)


def parser_for(
    path: str | PurePath, parsers: Registry | None = None, *, cpp_sources: bool = False
) -> CodeStructureInterface | None:
    """The parser for the file at `path` by its ending, whatever its case; None when none reads it.

    `parsers` is an injected registry; without one, the default. `cpp_sources` reads a `.h` as C++.
    """
    registry = get_default_parsers() if parsers is None else parsers
    language = language_of(path, cpp_sources=cpp_sources)
    if language is not None and LANGUAGE_SUFFIXES[language] in registry:
        return registry[LANGUAGE_SUFFIXES[language]]
    suffix = PurePath(path).suffix.lower()
    return next((parser for exts, parser in registry.items() if suffix in exts), None)
