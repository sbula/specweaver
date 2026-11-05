# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One project, written in each of the 9 languages, gets the same boundary verdict in each.

Proves: TECH-082 FR-16, FR-17, NFR-5

The tree: `domain` forbids `infra`; `domain/cli` consumes `infra` and declares it in `widens`;
`domain/core` imports `infra` without leave and imports one library. So `domain/core`'s file has one
violation and one import not mapped, and `domain/cli`'s file has none. Each language's tree sits
under its own base (`src/main/java`, Rust's `src`), and its manifests name paths from the project
root `[agreed 2026-11-05]`. Only the base and the import syntax differ; the real parser, the real
resolver and the real rule do the rest.

| Bucket | Case |
|---|---|
| Happy | the widened `domain/cli` file passes in every language |
| Boundary | the same violation and the same unmapped count in all 9 |
| Degradation | a library import is counted, never judged |
| Hostile | — (the trees are fixed) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.language.core.boundary_check import check_boundaries

if TYPE_CHECKING:
    from pathlib import Path

#: language: (base, {path under base: text}, core file, cli file)
TREES: dict[str, tuple[str, dict[str, str], str, str]] = {
    "python": (
        "",
        {
            "infra/__init__.py": "",
            "infra/db.py": "",
            "domain/core/svc.py": "import requests\nfrom infra import db\n",
            "domain/cli/main.py": "from infra import db\n",
        },
        "domain/core/svc.py",
        "domain/cli/main.py",
    ),
    "java": (
        "src/main/java/",
        {
            "infra/Db.java": "package infra;\npublic class Db {}\n",
            "domain/core/Svc.java": "package domain.core;\nimport infra.Db;\nimport java.util.List;\nclass Svc {}\n",
            "domain/cli/Main.java": "package domain.cli;\nimport infra.Db;\nclass Main {}\n",
        },
        "domain/core/Svc.java",
        "domain/cli/Main.java",
    ),
    "kotlin": (
        "src/main/kotlin/",
        {
            "infra/Db.kt": "package infra\nclass Db\n",
            "domain/core/Svc.kt": "package domain.core\nimport infra.Db\nimport kotlin.math.max\nclass Svc\n",
            "domain/cli/Main.kt": "package domain.cli\nimport infra.Db\nclass Main\n",
        },
        "domain/core/Svc.kt",
        "domain/cli/Main.kt",
    ),
    "typescript": (
        "",
        {
            "infra/db.ts": "export const db = 1;\n",
            "domain/core/svc.ts": "import { db } from '../../infra/db';\nimport _ from 'lodash';\n",
            "domain/cli/main.ts": "import { db } from '../../infra/db';\n",
        },
        "domain/core/svc.ts",
        "domain/cli/main.ts",
    ),
    "javascript": (
        "",
        {
            "infra/db.js": "module.exports = {};\n",
            "domain/core/svc.js": "const db = require('../../infra/db');\nconst _ = require('lodash');\n",
            "domain/cli/main.js": "const db = require('../../infra/db');\n",
        },
        "domain/core/svc.js",
        "domain/cli/main.js",
    ),
    "rust": (
        "src/",
        {
            "main.rs": "mod domain;\nmod infra;\n",
            "infra/mod.rs": "pub mod db;\n",
            "infra/db.rs": "pub struct Db;\n",
            "domain/mod.rs": "pub mod core;\npub mod cli;\n",
            "domain/core/mod.rs": "use crate::infra::db;\nuse std::io;\n",
            "domain/cli/mod.rs": "use crate::infra::db;\n",
        },
        "domain/core/mod.rs",
        "domain/cli/mod.rs",
    ),
    "go": (
        "",
        {
            "infra/db.go": "package infra\n",
            "domain/core/svc.go": 'package core\nimport (\n  "fmt"\n  "example.com/app/infra"\n)\n',
            "domain/cli/main.go": 'package cli\nimport "example.com/app/infra"\n',
        },
        "domain/core/svc.go",
        "domain/cli/main.go",
    ),
    "c": (
        "",
        {
            "infra/db.h": "int db(void);\n",
            "domain/core/svc.c": '#include "../../infra/db.h"\n#include <stdio.h>\n',
            "domain/cli/main.c": '#include "../../infra/db.h"\n',
        },
        "domain/core/svc.c",
        "domain/cli/main.c",
    ),
    "cpp": (
        "",
        {
            "infra/db.hpp": "int db();\n",
            "domain/core/svc.cpp": '#include "../../infra/db.hpp"\n#include <vector>\n',
            "domain/cli/main.cpp": '#include "../../infra/db.hpp"\n',
        },
        "domain/core/svc.cpp",
        "domain/cli/main.cpp",
    ),
}

#: Files outside the base that a language's resolver reads.
ROOT_FILES = {
    "rust": {"Cargo.toml": "[package]\nname = 'app'\n"},
    "go": {"go.mod": "module example.com/app\n"},
}


def _project(root: Path, language: str) -> tuple[str, str]:
    base, files, core, cli = TREES[language]
    manifests = {
        "domain/context.yaml": f"name: domain\narchetype: pure-logic\nforbids: [{base}infra]\n",
        "domain/cli/context.yaml": (
            f"name: domain-cli\narchetype: adapter\nconsumes: [{base}infra]\n"
            f"widens:\n  {base}infra: runs the database\n"
        ),
    }
    everything = {f"{base}{p}": t for p, t in {**files, **manifests}.items()}
    for relative, text in {**everything, **ROOT_FILES.get(language, {})}.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return f"{base}{core}", f"{base}{cli}"


@pytest.mark.integration
@pytest.mark.parametrize("language", sorted(TREES))
def test_the_same_tree_gets_the_same_verdict(tmp_path: Path, language: str) -> None:
    core, cli = _project(tmp_path, language)

    judged = check_boundaries(tmp_path, core)
    widened = check_boundaries(tmp_path, cli)

    assert (judged.violation_count, judged.unmapped, judged.note) == (1, 1, ""), judged
    assert (widened.violation_count, widened.unmapped, widened.note) == (0, 0, ""), widened


def test_every_language_is_in_the_fixture() -> None:
    from specweaver.commons.languages import LANGUAGE_SUFFIXES

    assert set(TREES) == set(LANGUAGE_SUFFIXES)
