# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What each language's parser lists as an import is what `import_target` can map.

Proves: TECH-082 FR-16, FR-17

The two halves are only ever used in sequence: the parser lists the imports, `import_target` maps
each one. A unit test of `import_target` writes its own import strings, so it cannot see a parser
that lists a name in another shape (as Java's wildcard once came back in three pieces). Here every
string comes from the real parser of a real file.

| Bucket | Case |
|---|---|
| Happy | each language's project imports reach their files |
| Boundary | a package import names its folder; a wildcard; a re-export |
| Degradation | a library import maps to None, so the check counts it as not mapped |
| Hostile | — (the sources are fixed project files) |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.refactor.imports import import_target

#: language: (files, importer, {import as the parser lists it: target})
CASES: dict[str, tuple[dict[str, str], str, dict[str, str | None]]] = {
    "python": (
        {
            "app/__init__.py": "",
            "app/core/__init__.py": "",
            "app/core/service.py": "",
            "app/web/view.py": "import os\nfrom app.core.service import run\nfrom ..core import x\n",
        },
        "app/web/view.py",
        {"os": None, "app.core.service": "app/core/service.py", "..core": "app/core"},
    ),
    "java": (
        {
            "src/main/java/app/core/Service.java": "package app.core;\npublic class Service {}\n",
            "src/main/java/app/web/View.java": (
                "package app.web;\nimport app.core.*;\nimport java.util.List;\nclass View {}\n"
            ),
        },
        "src/main/java/app/web/View.java",
        {"app.core.*": "src/main/java/app/core", "java.util.List": None},
    ),
    "kotlin": (
        {
            "src/main/kotlin/app/core/Repo.kt": "package app.core\nclass Repo\n",
            "src/main/kotlin/app/web/View.kt": (
                "package app.web\nimport app.core.Repo\nimport kotlin.math.max\nclass View\n"
            ),
        },
        "src/main/kotlin/app/web/View.kt",
        {"app.core.Repo": "src/main/kotlin/app/core/Repo.kt", "kotlin.math.max": None},
    ),
    "typescript": (
        {
            "src/core/index.ts": "export const a = 1;\n",
            "src/web/v.ts": "import { a } from '../core';\nimport React from 'react';\n",
        },
        "src/web/v.ts",
        {"../core": "src/core", "react": None},
    ),
    "javascript": (
        {
            "src/core/a.js": "module.exports = {};\n",
            "src/web/v.cjs": "const a = require('../core/a');\nconst fs = require('fs');\n",
        },
        "src/web/v.cjs",
        {"../core/a": "src/core/a.js", "fs": None},
    ),
    "rust": (
        {
            "Cargo.toml": "[package]\nname = 'app'\n",
            "src/main.rs": "mod core;\nmod web;\n",
            "src/core/mod.rs": "pub mod service;\n",
            "src/core/service.rs": "pub struct Thing;\n",
            "src/web.rs": "use crate::core::service::Thing;\nuse std::io;\n",
        },
        "src/web.rs",
        {"crate::core::service::Thing": "src/core/service.rs", "std::io": None},
    ),
    "go": (
        {
            "go.mod": "module example.com/app\n",
            "core/c.go": "package core\n",
            "web/w.go": 'package web\nimport (\n  "fmt"\n  "example.com/app/core"\n)\n',
        },
        "web/w.go",
        {"example.com/app/core": "core", "fmt": None},
    ),
    "c": (
        {
            "src/core/a.h": "int a(void);\n",
            "src/web/w.c": '#include "../core/a.h"\n#include <stdio.h>\n',
        },
        "src/web/w.c",
        {'#include "../core/a.h"': "src/core/a.h", "#include <stdio.h>": None},
    ),
    "cpp": (
        {
            "src/core/b.hpp": "int b();\n",
            "src/web/w.cpp": '#include "../core/b.hpp"\n#include <vector>\n',
        },
        "src/web/w.cpp",
        {'#include "../core/b.hpp"': "src/core/b.hpp", "#include <vector>": None},
    ),
}


@pytest.mark.parametrize("language", sorted(CASES))
def test_the_parsers_imports_map_to_project_files(language: str) -> None:
    files, importer, expected = CASES[language]
    suffix = "." + importer.rsplit(".", 1)[1]
    parser = next(p for exts, p in get_default_parsers().items() if suffix in exts)

    listed = parser.extract_imports(files[importer])

    assert sorted(listed) == sorted(expected)
    assert {w: import_target(files, importer, w) for w in listed} == expected
