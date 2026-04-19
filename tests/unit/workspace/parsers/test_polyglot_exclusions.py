# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from specweaver.workspace.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.parsers.typescript.codestructure import TypeScriptCodeStructure


def test_python_polyglot_bounds():
    parser = PythonCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.pyc", "*.pyo", "*.pyd"}
    assert set(parser.get_default_directory_ignores()) == {"__pycache__/", ".pytest_cache/", ".tox/", ".venv/"}

def test_java_polyglot_bounds():
    parser = JavaCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.class", "*.jar", "*.ear", "*.war"}
    assert set(parser.get_default_directory_ignores()) == {"target/", "build/"}

def test_kotlin_polyglot_bounds():
    parser = KotlinCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.class", "*.jar"}
    assert set(parser.get_default_directory_ignores()) == {"target/", "build/", ".gradle/"}

def test_rust_polyglot_bounds():
    parser = RustCodeStructure()
    assert set(parser.get_binary_ignore_patterns()) == {"*.rlib", "*.so", "*.dll", "*.pdb"}
    assert set(parser.get_default_directory_ignores()) == {"target/"}

def test_typescript_polyglot_bounds():
    parser = TypeScriptCodeStructure()
    assert parser.get_binary_ignore_patterns() == []
    assert set(parser.get_default_directory_ignores()) == {"node_modules/", "dist/", "build/", "out/"}
