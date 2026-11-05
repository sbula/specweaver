# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each language names the project file or folder an import reaches, or says it reaches none.

Proves: TECH-082 FR-16, FR-17

`import_target(files, path, written)` takes an import exactly as the language's parser lists it.
A package file (`__init__.py`, `mod.rs`, `index.ts`) and a Go import name their folder. Anything
outside the project is None, which the boundary check counts as not mapped.

| Bucket | Case |
|---|---|
| Happy | each language's project import reaches the right file |
| Boundary | relative imports, packages, static and wildcard imports, nested Go modules, aliases |
| Degradation | an import of a project file that does not exist is None, never an error |
| Hostile | `..` climbing out of the project, absolute paths, a non-code file |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.refactor.imports import import_target

PYTHON = {
    "app/__init__.py": "",
    "app/core/__init__.py": "",
    "app/core/service.py": "",
    "app/web/view.py": "",
    "src/lib/x.py": "",
}

JAVA = {
    "src/main/java/app/core/Service.java": "package app.core;\npublic class Service {}\n",
    "src/main/java/app/util/X.java": "package app.util;\npublic class X { static int y() { return 1; } }\n",
    "src/main/java/app/web/View.java": "package app.web;\nclass View {}\n",
    "src/main/kotlin/app/data/Repo.kt": "package app.data\nclass Repo\n",
}

SCRIPTS = {
    "src/core/a.ts": "",
    "src/core/index.ts": "",
    "src/web/v.ts": "",
    "src/legacy/old.js": "",
    "src/lib/index.js": "",
    "src/web/c.cjs": "",
    "src/web/app.jsx": "",
}

RUST = {
    "Cargo.toml": "[package]\nname = 'app'\n",
    "src/main.rs": "mod core;\nmod web;\n",
    "src/core/mod.rs": "pub mod service;\n",
    "src/core/service.rs": "pub struct Thing;\n",
    "src/web.rs": "pub fn run() {}\n",
}

GO = {
    "go.mod": "module example.com/app\n",
    "core/c.go": "package core\n",
    "web/w.go": "package web\n",
    "tools/go.mod": "module example.com/tools\n",
    "tools/x/x.go": "package x\n",
}

C = {
    "src/core/a.h": "",
    "src/core/a.c": "",
    "include/util.h": "",
    "src/web/w.c": "",
    "src/web/w.cpp": "",
    "src/core/b.hpp": "",
}


@pytest.mark.parametrize(
    ("path", "written", "target"),
    [
        ("app/web/view.py", "app.core.service", "app/core/service.py"),
        ("app/web/view.py", "app.core", "app/core"),
        ("app/web/view.py", "..core", "app/core"),
        ("app/web/view.py", "..core.service", "app/core/service.py"),
        ("app/web/view.py", "lib.x", "src/lib/x.py"),
    ],
)
def test_python(path: str, written: str, target: str) -> None:
    assert import_target(PYTHON, path, written) == target


@pytest.mark.parametrize(
    ("path", "written", "target"),
    [
        (
            "src/main/java/app/web/View.java",
            "app.core.Service",
            "src/main/java/app/core/Service.java",
        ),
        ("src/main/java/app/web/View.java", "app.util.X.y", "src/main/java/app/util/X.java"),
        ("src/main/java/app/web/View.java", "app.core.*", "src/main/java/app/core"),
        ("src/main/java/app/web/View.java", "app.core.Missing", "src/main/java/app/core"),
        ("src/main/java/app/web/View.java", "app.data.Repo", "src/main/kotlin/app/data/Repo.kt"),
    ],
)
def test_java_and_kotlin(path: str, written: str, target: str) -> None:
    assert import_target(JAVA, path, written) == target


@pytest.mark.parametrize(
    ("path", "written", "target"),
    [
        ("src/web/v.ts", "../core/a", "src/core/a.ts"),
        ("src/web/v.ts", "../core", "src/core"),
        ("src/web/v.ts", "../legacy/old.js", "src/legacy/old.js"),
        ("src/web/c.cjs", "../lib", "src/lib"),
        ("src/web/v.ts", "./app", "src/web/app.jsx"),
    ],
)
def test_typescript_and_javascript(path: str, written: str, target: str) -> None:
    assert import_target(SCRIPTS, path, written) == target


@pytest.mark.parametrize(
    ("path", "written", "target"),
    [
        ("src/web.rs", "crate::core::service::Thing", "src/core/service.rs"),
        ("src/web.rs", "crate::core", "src/core"),
        ("src/web.rs", "super::core::service", "src/core/service.rs"),
        ("src/core/service.rs", "self::Thing as T", "src/core/service.rs"),
        ("src/web.rs", "crate::core::*", "src/core"),
    ],
)
def test_rust(path: str, written: str, target: str) -> None:
    assert import_target(RUST, path, written) == target


@pytest.mark.parametrize(
    ("written", "target"),
    [("example.com/app/core", "core"), ("example.com/tools/x", "tools/x")],
)
def test_go(written: str, target: str) -> None:
    assert import_target(GO, "web/w.go", written) == target


@pytest.mark.parametrize(
    ("path", "written", "target"),
    [
        ("src/web/w.c", '#include "../core/a.h"', "src/core/a.h"),
        ("src/web/w.c", '#include "util.h"', "include/util.h"),
        ("src/web/w.cpp", '#include "../core/b.hpp"', "src/core/b.hpp"),
    ],
)
def test_c_and_cpp(path: str, written: str, target: str) -> None:
    assert import_target(C, path, written) == target


@pytest.mark.parametrize(
    ("files", "path", "written"),
    [
        (PYTHON, "app/web/view.py", "os"),
        (JAVA, "src/main/java/app/web/View.java", "java.util.List"),
        (SCRIPTS, "src/web/v.ts", "react"),
        (RUST, "src/web.rs", "std::io"),
        (GO, "web/w.go", "fmt"),
        (C, "src/web/w.c", "#include <stdio.h>"),
    ],
)
def test_an_import_from_outside_the_project_reaches_nothing(
    files: dict[str, str], path: str, written: str
) -> None:
    assert import_target(files, path, written) is None


@pytest.mark.parametrize(
    ("files", "path", "written"),
    [
        (PYTHON, "app/web/view.py", "app.nothere"),
        (PYTHON, "app/web/view.py", ".sib"),
        (SCRIPTS, "src/web/v.ts", "./nothere"),
        (RUST, "src/web.rs", "crate::nothere"),
        (C, "src/web/w.c", '#include "nothere.h"'),
        (GO, "web/w.go", "example.com/app"),
    ],
)
def test_a_missing_project_file_reaches_nothing(
    files: dict[str, str], path: str, written: str
) -> None:
    assert import_target(files, path, written) is None


@pytest.mark.parametrize(
    ("files", "path", "written"),
    [
        (PYTHON, "app/web/view.py", "......etc"),
        (SCRIPTS, "src/web/v.ts", "../../../etc/passwd"),
        (SCRIPTS, "src/web/v.ts", "/etc/passwd"),
        (SCRIPTS, "src/web/v.ts", "./style.css"),
        (C, "src/web/w.c", '#include "/etc/passwd"'),
        (C, "src/web/w.c", '#include "../../../etc/passwd"'),
    ],
)
def test_a_path_out_of_the_project_reaches_nothing(
    files: dict[str, str], path: str, written: str
) -> None:
    assert import_target(files, path, written) is None


def test_a_file_of_no_known_language_has_no_targets() -> None:
    assert import_target({"a.txt": ""}, "a.txt", "b") is None


def test_a_package_in_main_and_in_tests_names_the_importers_side() -> None:
    files = {
        **JAVA,
        "src/test/java/app/core/ServiceTest.java": "package app.core;\nclass ServiceTest {}\n",
        "src/test/java/app/web/ViewTest.java": "package app.web;\nclass ViewTest {}\n",
    }

    assert import_target(files, "src/main/java/app/web/View.java", "app.core.*") == (
        "src/main/java/app/core"
    )
    assert import_target(files, "src/test/java/app/web/ViewTest.java", "app.core.*") == (
        "src/test/java/app/core"
    )


def test_a_rust_module_with_no_file_of_its_own_reaches_nothing() -> None:
    files = {**RUST, "src/main.rs": "mod core;\nmod web;\nmod inline { pub fn f() {} }\n"}

    assert import_target(files, "src/web.rs", "crate::inline") is None


def test_a_language_with_no_imports_to_map_has_no_targets() -> None:
    from specweaver.workspace.ast.refactor.imports import targets_for

    assert targets_for({"a.sql": ""}, "sql") is None
