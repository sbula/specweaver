# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Factory providing pure dependency injection map for polyglot structural AST parsers.

This centralizes the physical instantiation of CodeStructureInterfaces so orchestrators
(like the Flow engine) can inject them without violating architectural boundaries.
"""

from specweaver.workspace.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.parsers.cpp.codestructure import CppCodeStructure
from specweaver.workspace.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.parsers.interfaces import CodeStructureInterface
from specweaver.workspace.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.parsers.markdown.codestructure import MarkdownCodeStructure
from specweaver.workspace.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.parsers.typescript.codestructure import TypeScriptCodeStructure


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
    }

