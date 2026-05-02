# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Factory providing pure dependency injection map for polyglot structural AST parsers.

This centralizes the physical instantiation of CodeStructureInterfaces so orchestrators
(like the Flow engine) can inject them without violating architectural boundaries.
"""

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


def get_default_parsers() -> dict[tuple[str, ...], CodeStructureInterface]:
    """Return the registry mapping of file extensions to their AST parsing implementations."""
    return {
        (".c", ".h"): CCodeStructure(),
        (".cpp", ".hpp", ".cc", ".cxx"): CppCodeStructure(),
        (".py",): PythonCodeStructure(),
        (".java",): JavaCodeStructure(),
        (".ts", ".tsx"): TypeScriptCodeStructure(),
        (".rs",): RustCodeStructure(),
        (".kt", ".kts"): KotlinCodeStructure(),
        (".md", ".mdx"): MarkdownCodeStructure(),
        (".go",): GoCodeStructure(),
        (".sql",): SqlCodeStructure(),
    }

