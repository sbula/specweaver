# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A TypeScript rename planned across modules: every proven use, or nothing.

Proves: D-SENS-06 FR-7
Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a class through imports, re-exports and a namespace; a method and its override family |
| Boundary | an alias import; a default import; `index.ts`; a `.js` import path; an interface family |
| Degradation | `export *`; `tsconfig` paths; a `.js` file naming it; a missing module; an outside base |
| Hostile | an object-literal key; a rebound `this`; an unknown receiver; a keyword new name |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure
from specweaver.workspace.ast.refactor.rename import RenamePlan, RenameRefusal, Spot, plan_rename

_TS = TypeScriptCodeStructure()

_FILES = {
    "src/greeter.ts": (
        "export class Greeter {\n"
        "  greet(n: string): string { return n; }\n"
        "  twice(n: string): string { return this.greet(n) + this.greet(n); }\n"
        "}\n"
    ),
    "src/loud.ts": (
        'import { Greeter } from "./greeter";\n'
        "export class Loud extends Greeter {\n"
        "  greet(n: string): string { return super.greet(n).toUpperCase(); }\n"
        "}\n"
    ),
    "src/index.ts": 'export { Greeter } from "./greeter";\n',
    "src/app.ts": (
        'import { Greeter } from "./index";\n'
        'import * as g from "./greeter";\n'
        "const a: Greeter = new Greeter();\n"
        "const b = new g.Greeter();\n"
    ),
}


def _plan(files: dict[str, str], path: str, symbol: str, new: str) -> RenamePlan:
    result = plan_rename(files, path, symbol, new, _TS)
    assert isinstance(result, RenamePlan), result
    return result


def _refusal(files: dict[str, str], path: str, symbol: str, new: str) -> RenameRefusal:
    result = plan_rename(files, path, symbol, new, _TS)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Happy -----------------------------------------------------------------------------------


def test_a_class_through_imports_re_exports_and_a_namespace() -> None:
    plan = _plan(_FILES, "src/greeter.ts", "Greeter", "Welcomer")

    assert sorted(plan.changes) == ["src/app.ts", "src/greeter.ts", "src/index.ts", "src/loud.ts"]
    assert plan.changes["src/index.ts"] == 'export { Welcomer } from "./greeter";\n'
    assert plan.changes["src/app.ts"] == (
        'import { Welcomer } from "./index";\n'
        'import * as g from "./greeter";\n'
        "const a: Welcomer = new Welcomer();\n"
        "const b = new g.Welcomer();\n"
    )


def test_a_method_and_its_override_family() -> None:
    plan = _plan(_FILES, "src/greeter.ts", "Greeter.greet", "welcome")

    assert plan.changes["src/greeter.ts"].count("welcome") == 3
    assert (
        "  welcome(n: string): string { return super.welcome(n).toUpperCase(); }"
        in plan.changes["src/loud.ts"]
    )


def test_an_interface_and_its_implementations_are_one_family() -> None:
    files = {
        "src/shape.ts": "export interface Shape {\n  area(): number;\n}\n",
        "src/square.ts": (
            'import { Shape } from "./shape";\n'
            "export class Square implements Shape {\n  area(): number { return 1; }\n}\n"
        ),
    }
    plan = _plan(files, "src/shape.ts", "Shape.area", "size")
    assert "  size(): number { return 1; }" in plan.changes["src/square.ts"]


# --- Boundary --------------------------------------------------------------------------------


def test_an_alias_import_changes_only_the_imported_name() -> None:
    files = {
        **_FILES,
        "src/app.ts": 'import { Greeter as G } from "./greeter";\nconst a = new G();\n',
    }
    plan = _plan(files, "src/greeter.ts", "Greeter", "Welcomer")
    assert (
        plan.changes["src/app.ts"]
        == 'import { Welcomer as G } from "./greeter";\nconst a = new G();\n'
    )


def test_a_default_import_keeps_its_own_name() -> None:
    files = {
        "src/greeter.ts": "export default class Greeter {}\n",
        "src/app.ts": 'import Greeter from "./greeter";\nconst a = new Greeter();\n',
    }
    plan = _plan(files, "src/greeter.ts", "Greeter", "Welcomer")
    assert "src/app.ts" not in plan.changes


def test_index_ts_and_a_js_import_path_resolve() -> None:
    files = {
        "src/lib/index.ts": "export function total(a: number) { return a; }\n",
        "src/a.ts": 'import { total } from "./lib";\ntotal(1);\n',
        "src/b.ts": 'import { total } from "./lib/index.js";\ntotal(2);\n',
    }
    plan = _plan(files, "src/lib/index.ts", "total", "sum")
    assert sorted(plan.changes) == ["src/a.ts", "src/b.ts", "src/lib/index.ts"]


def test_a_same_named_class_elsewhere_is_left_alone() -> None:
    files = {**_FILES, "src/other.ts": "class Greeter {}\nconst x = new Greeter();\n"}
    assert "src/other.ts" not in _plan(files, "src/greeter.ts", "Greeter", "Welcomer").changes


def test_an_outside_package_import_of_the_same_name_is_left_alone() -> None:
    files = {**_FILES, "src/other.ts": 'import { Greeter } from "some-lib";\nnew Greeter();\n'}
    assert "src/other.ts" not in _plan(files, "src/greeter.ts", "Greeter", "Welcomer").changes


# --- Degradation -----------------------------------------------------------------------------


def test_export_star_is_unsure() -> None:
    files = {
        **_FILES,
        "src/all.ts": 'export * from "./greeter";\n',
        "src/c.ts": 'import { Greeter } from "./all";\n',
    }
    assert _refusal(files, "src/greeter.ts", "Greeter", "Welcomer").spots == [Spot("src/c.ts", 1)]


def test_tsconfig_paths_make_a_bare_specifier_unsure() -> None:
    files = {
        **_FILES,
        "tsconfig.json": '{"compilerOptions": {"paths": {"@app/*": ["src/*"]}}}\n',
        "src/c.ts": 'import { Greeter } from "@app/greeter";\n',
    }
    assert _refusal(files, "src/greeter.ts", "Greeter", "Welcomer").spots == [Spot("src/c.ts", 1)]


def test_a_js_file_naming_it_is_unsure() -> None:
    files = {**_FILES, "src/legacy.js": "const g = new Greeter();\n"}
    assert _refusal(files, "src/greeter.ts", "Greeter", "Welcomer").spots == [
        Spot("src/legacy.js", 1)
    ]


def test_a_missing_relative_module_is_unsure() -> None:
    files = {**_FILES, "src/c.ts": 'import { Greeter } from "./gone";\n'}
    assert _refusal(files, "src/greeter.ts", "Greeter", "Welcomer").spots == [Spot("src/c.ts", 1)]


def test_a_family_with_an_outside_base_refuses() -> None:
    files = {
        "src/c.ts": 'import { Component } from "react";\nexport class C extends Component {\n  render() {}\n}\n'
    }
    assert "outside the project" in _refusal(files, "src/c.ts", "C.render", "draw").reason


# --- Hostile ---------------------------------------------------------------------------------


def test_an_object_literal_key_is_unsure() -> None:
    files = {**_FILES, "src/c.ts": "const fake = { greet(n: string) { return n; } };\n"}
    assert _refusal(files, "src/greeter.ts", "Greeter.greet", "welcome").spots == [
        Spot("src/c.ts", 1)
    ]


def test_a_rebound_this_is_unsure() -> None:
    files = {
        **_FILES,
        "src/greeter.ts": _FILES["src/greeter.ts"].replace(
            "  twice(", '  later() { return function () { return this.greet("x"); }; }\n  twice('
        ),
    }
    assert (
        Spot("src/greeter.ts", 3)
        in _refusal(files, "src/greeter.ts", "Greeter.greet", "welcome").spots
    )


def test_an_unknown_receiver_is_unsure() -> None:
    files = {**_FILES, "src/c.ts": 'export function f(x: any) { return x.greet("y"); }\n'}
    assert _refusal(files, "src/greeter.ts", "Greeter.greet", "welcome").spots == [
        Spot("src/c.ts", 1)
    ]


@pytest.mark.parametrize("new", ["class", "function", "1x", ""])
def test_a_keyword_new_name_refuses(new: str) -> None:
    assert _refusal(_FILES, "src/greeter.ts", "Greeter", new).reason
