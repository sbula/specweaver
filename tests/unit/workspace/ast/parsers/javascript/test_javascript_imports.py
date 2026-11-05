# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The JavaScript parser lists the modules a `.js`, `.jsx`, `.mjs` or `.cjs` file imports.

Proves: TECH-082 FR-18

| Bucket | Case |
|---|---|
| Happy | ES imports, `export ... from`, `require("x")` |
| Boundary | a dynamic `import("x")`; a side-effect import; JSX; an empty file |
| Degradation | a file with a syntax error still lists the imports that parse |
| Hostile | `require(name)` and a template-literal `require` name no module, so they are not listed |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.parsers.javascript.codestructure import JavaScriptCodeStructure


@pytest.fixture
def parser() -> JavaScriptCodeStructure:
    return JavaScriptCodeStructure()


def test_es_imports_and_re_exports(parser: JavaScriptCodeStructure) -> None:
    code = (
        "import x from './a';\n"
        'import { y } from "../b";\n'
        "import * as z from 'lodash';\n"
        "export { w } from './c';\n"
        "export * from './d';\n"
    )

    assert parser.extract_imports(code) == ["../b", "./a", "./c", "./d", "lodash"]


def test_require_in_a_commonjs_file(parser: JavaScriptCodeStructure) -> None:
    code = "const fs = require('fs');\nconst { e } = require(\"./e\");\nmodule.exports = {};\n"

    assert parser.extract_imports(code) == ["./e", "fs"]


def test_dynamic_and_side_effect_imports(parser: JavaScriptCodeStructure) -> None:
    code = "import './style.css';\nasync function f() { return import('./lazy'); }\n"

    assert parser.extract_imports(code) == ["./lazy", "./style.css"]


def test_jsx_file(parser: JavaScriptCodeStructure) -> None:
    code = "import Button from './Button';\nexport const App = () => <Button label='hi' />;\n"

    assert parser.extract_imports(code) == ["./Button"]


def test_empty_file(parser: JavaScriptCodeStructure) -> None:
    assert parser.extract_imports("") == []


def test_a_syntax_error_keeps_the_imports_that_parse(parser: JavaScriptCodeStructure) -> None:
    code = "import a from './a';\nfunction broken( {\n"

    assert "./a" in parser.extract_imports(code)


def test_a_require_that_names_no_module_is_not_listed(parser: JavaScriptCodeStructure) -> None:
    code = "const n = './x';\nrequire(n);\nrequire(`./${n}`);\nrequire('./real');\n"

    assert parser.extract_imports(code) == ["./real"]


@pytest.mark.parametrize("suffix", [".js", ".jsx", ".mjs", ".cjs"])
def test_the_factory_gives_every_javascript_ending_this_parser(suffix: str) -> None:
    parsers = {ext: p for exts, p in get_default_parsers().items() for ext in exts}

    assert isinstance(parsers[suffix], JavaScriptCodeStructure)


def test_add_symbol_puts_a_method_inside_its_class(parser: JavaScriptCodeStructure) -> None:
    code = "export class Circle {\n    area() { return 1 }\n}\n"

    added = parser.add_symbol(code, "Circle", "size() { return 2 }")

    assert parser.list_symbols(added) == ["Circle", "Circle.area", "Circle.size"]


def test_node_modules_is_ignored_by_default(parser: JavaScriptCodeStructure) -> None:
    assert "node_modules/" in parser.get_default_directory_ignores()
