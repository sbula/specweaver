# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure


def test_get_default_parsers() -> None:
    parsers = get_default_parsers()

    # Assert standard extensions are correctly mapped
    assert (".py",) in parsers
    assert isinstance(parsers[(".py",)], PythonCodeStructure)

    assert (".java",) in parsers
    assert isinstance(parsers[(".java",)], JavaCodeStructure)

    assert (".sql",) in parsers
    assert isinstance(parsers[(".sql",)], SqlCodeStructure)

    # Ensure tuples cover TS/TSX
    assert (".ts", ".tsx") in parsers
