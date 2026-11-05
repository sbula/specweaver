# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Java wildcard import is listed as one name, `app.core.*`, not as its pieces.

Proves: TECH-082 FR-16

Before, `import app.core.*;` came back as `app.core`, `.` and `*`: two names that are not imports,
which the boundary check would count as imports it could not map.
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure


def test_a_wildcard_import_is_one_name() -> None:
    code = "package a;\nimport app.core.*;\nimport static app.util.X.*;\nimport app.web.View;\n"

    assert JavaCodeStructure().extract_imports(code) == [
        "app.core.*",
        "app.util.X.*",
        "app.web.View",
    ]


def test_a_static_import_keeps_its_member() -> None:
    code = "package a;\nimport static app.util.X.y;\n"

    assert JavaCodeStructure().extract_imports(code) == ["app.util.X.y"]
