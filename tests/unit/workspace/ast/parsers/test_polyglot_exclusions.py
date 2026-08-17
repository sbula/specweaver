# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each language parser contributes its own structural and binary exclusions.

Proves: C-SENS-02 FR-1, C-SENS-02 FR-2

Cited under `specweaver-dev` §3.2c, from `INT-US-05-SF03-MIG`.

Mutants: emptying Rust's `["target/"]` directory exclusion (FR-1) and Java's
`["*.class", "*.jar", "*.ear", "*.war"]` binary exclusions (FR-2) each fail here, and nowhere else in
`tests/unit/workspace`. The per-language lists are data, so this is the only place that notices a
language quietly contributing nothing.
"""

from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure


def test_python_polyglot_bounds() -> None:
    parser = PythonCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.pyc", "*.pyo", "*.pyd"}
    assert set(parser.get_default_directory_ignores()) == {
        "__pycache__/",
        ".pytest_cache/",
        ".tox/",
        ".venv/",
    }


def test_java_polyglot_bounds() -> None:
    parser = JavaCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.class", "*.jar", "*.ear", "*.war"}
    assert set(parser.get_default_directory_ignores()) == {"target/", "build/"}


def test_kotlin_polyglot_bounds() -> None:
    parser = KotlinCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.class", "*.jar"}
    assert set(parser.get_default_directory_ignores()) == {"target/", "build/", ".gradle/"}


def test_rust_polyglot_bounds() -> None:
    parser = RustCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.rlib", "*.so", "*.dll", "*.pdb"}
    assert set(parser.get_default_directory_ignores()) == {"target/"}


def test_typescript_polyglot_bounds() -> None:
    parser = TypeScriptCodeStructure()
    assert parser.get_binary_ignore_patterns() == []
    assert set(parser.get_default_directory_ignores()) == {
        "node_modules/",
        "dist/",
        "build/",
        "out/",
    }
