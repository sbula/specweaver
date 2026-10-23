# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Factory providing pure dependency injection map for polyglot structural AST parsers.

This centralizes the physical instantiation of CodeStructureInterfaces so orchestrators
(like the Flow engine) can inject them without violating architectural boundaries.
"""

import logging

from specweaver.commons.languages import LANGUAGE_SUFFIXES
from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure
from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

logger = logging.getLogger(__name__)


def get_default_parsers() -> dict[tuple[str, ...], CodeStructureInterface]:
    """Return the registry mapping of file extensions to their AST parsing implementations."""
    logger.debug("get_default_parsers called: initializing parser registry")
    by_language = {
        "c": CCodeStructure(),
        "cpp": CppCodeStructure(),
        "python": PythonCodeStructure(),
        "java": JavaCodeStructure(),
        "typescript": TypeScriptCodeStructure(),
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
    return parsers
