# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""AST Skeleton extraction logic for condensing token contexts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.workspace.parsers.interfaces import CodeStructureInterface

logger = logging.getLogger(__name__)


def extract_ast_skeleton(path: Path, content: str) -> str:
    """Resolve a workspace AST parser to construct compressed bounds."""
    ext = path.suffix.lower()

    # Use explicit Any or CodeStructureInterface for generic parser typing
    try:
        parser: CodeStructureInterface | None = None

        if ext == ".py":
            from specweaver.workspace.parsers.python.codestructure import PythonCodeStructure
            parser = PythonCodeStructure()
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            from specweaver.workspace.parsers.typescript.codestructure import (
                TypeScriptCodeStructure,
            )
            parser = TypeScriptCodeStructure()
        elif ext == ".java":
            from specweaver.workspace.parsers.java.codestructure import JavaCodeStructure
            parser = JavaCodeStructure()
        elif ext in (".kt", ".kts"):
            from specweaver.workspace.parsers.kotlin.codestructure import KotlinCodeStructure
            parser = KotlinCodeStructure()
        elif ext == ".rs":
            from specweaver.workspace.parsers.rust.codestructure import RustCodeStructure
            parser = RustCodeStructure()

        if parser:
            return parser.extract_skeleton(content)
    except Exception as exc:
        logger.debug("Failed to AST extract skeleton for %s, falling back to exact text: %s", path, exc)

    return content
