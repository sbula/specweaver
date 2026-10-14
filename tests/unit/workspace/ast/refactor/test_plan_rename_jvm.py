# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Java or Kotlin rename planned across both languages: every proven use, or nothing.

Proves: D-SENS-06 FR-7
Proves: D-SENS-06 FR-8

| Bucket | Case |
|---|---|
| Happy | a Kotlin class used from Java; a Java method and its override family; a Kotlin function |
| Boundary | the same package without import; an alias import; a qualified type; a field of the name |
| Degradation | a public class named like its file; an outside base; an unknown `*` import; a broken file |
| Hostile | a keyword new name; a sibling taken; the name as a string; a local receiver; a nested type |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.refactor.rename import RenamePlan, RenameRefusal, Spot, plan_rename

_KOTLIN = KotlinCodeStructure()
_JAVA = JavaCodeStructure()

_GREETER = {
    "src/app/util/Greeter.kt": "package app.util\n\nopen class Greeter {\n    open fun greet(n: String) = n\n}\n",
    "src/app/Main.kt": "package app\n\nimport app.util.Greeter\n\nfun main() {\n    val g = Greeter()\n}\n",
    "src/app/Use.java": (
        "package app;\n\nimport app.util.Greeter;\n\n"
        "class Use {\n    Greeter make() { return new Greeter(); }\n}\n"
    ),
}

_BASE = {
    "src/app/util/Base.java": (
        "package app.util;\n\n"
        "public class Base {\n"
        "    public void greet() {}\n"
        "    void twice() { greet(); this.greet(); }\n"
        "}\n"
    ),
    "src/app/Sub.java": (
        "package app;\n\nimport app.util.Base;\n\n"
        "class Sub extends Base {\n"
        "    private int greet = 0;\n"
        "    @Override public void greet() { super.greet(); }\n"
        "}\n"
    ),
    "src/app/K.kt": "package app\n\nimport app.util.Base\n\nclass K : Base() {\n    fun z() { greet() }\n}\n",
}


def _plan(files: dict[str, str], path: str, symbol: str, new: str) -> RenamePlan:
    parser = _JAVA if path.endswith(".java") else _KOTLIN
    result = plan_rename(files, path, symbol, new, parser)
    assert isinstance(result, RenamePlan), result
    return result


def _refusal(files: dict[str, str], path: str, symbol: str, new: str) -> RenameRefusal:
    parser = _JAVA if path.endswith(".java") else _KOTLIN
    result = plan_rename(files, path, symbol, new, parser)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Happy -----------------------------------------------------------------------------------


def test_a_kotlin_class_is_renamed_in_kotlin_and_java() -> None:
    plan = _plan(_GREETER, "src/app/util/Greeter.kt", "Greeter", "Welcomer")

    assert "open class Welcomer {" in plan.changes["src/app/util/Greeter.kt"]
    assert plan.changes["src/app/Main.kt"].count("Welcomer") == 2
    assert plan.changes["src/app/Use.java"] == (
        "package app;\n\nimport app.util.Welcomer;\n\n"
        "class Use {\n    Welcomer make() { return new Welcomer(); }\n}\n"
    )


def test_a_java_method_and_its_family_across_both_languages() -> None:
    plan = _plan(_BASE, "src/app/util/Base.java", "Base.greet", "welcome")

    assert "void twice() { welcome(); this.welcome(); }" in plan.changes["src/app/util/Base.java"]
    sub = plan.changes["src/app/Sub.java"]
    assert "public void welcome() { super.welcome(); }" in sub
    assert "private int greet = 0;" in sub
    assert "fun z() { welcome() }" in plan.changes["src/app/K.kt"]


def test_a_kotlin_top_level_function_from_kotlin_and_java() -> None:
    files = {
        "src/app/util/Tools.kt": "package app.util\n\nfun shout(s: String) = s\n",
        "src/app/util/Near.kt": 'package app.util\n\nval y = shout("y")\n',
        "src/app/Main.kt": 'package app\n\nimport app.util.shout\n\nval x = shout("x")\n',
        "src/app/Use.java": 'package app;\n\nclass Use { String f() { return app.util.ToolsKt.shout("z"); } }\n',
        "src/other/Far.kt": 'package other\n\nfun shout(s: String) = s\nval z = shout("z")\n',
    }
    plan = _plan(files, "src/app/util/Tools.kt", "shout", "yell")

    assert sorted(plan.changes) == [
        "src/app/Main.kt",
        "src/app/Use.java",
        "src/app/util/Near.kt",
        "src/app/util/Tools.kt",
    ]
    assert "app.util.ToolsKt.yell(" in plan.changes["src/app/Use.java"]


# --- Boundary --------------------------------------------------------------------------------


def test_the_same_package_needs_no_import() -> None:
    files = {**_GREETER, "src/app/util/Near.kt": "package app.util\n\nval g = Greeter()\n"}
    plan = _plan(files, "src/app/util/Greeter.kt", "Greeter", "Welcomer")
    assert "Welcomer()" in plan.changes["src/app/util/Near.kt"]


def test_an_alias_import_changes_only_the_imported_name() -> None:
    files = {
        **_GREETER,
        "src/app/Main.kt": "package app\n\nimport app.util.Greeter as G\n\nval g = G()\n",
    }
    plan = _plan(files, "src/app/util/Greeter.kt", "Greeter", "Welcomer")
    assert (
        plan.changes["src/app/Main.kt"]
        == "package app\n\nimport app.util.Welcomer as G\n\nval g = G()\n"
    )


def test_a_qualified_type_is_renamed() -> None:
    files = {**_GREETER, "src/app/Q.java": "package app;\n\nclass Q { app.util.Greeter g; }\n"}
    plan = _plan(files, "src/app/util/Greeter.kt", "Greeter", "Welcomer")
    assert "app.util.Welcomer g;" in plan.changes["src/app/Q.java"]


def test_a_class_of_the_same_name_in_another_package_is_left_alone() -> None:
    files = {
        **_GREETER,
        "src/other/Greeter.kt": "package other\n\nclass Greeter\nval g = Greeter()\n",
    }
    plan = _plan(files, "src/app/util/Greeter.kt", "Greeter", "Welcomer")
    assert "src/other/Greeter.kt" not in plan.changes


# --- Degradation -----------------------------------------------------------------------------


def test_a_public_java_class_named_like_its_file_points_to_move_module() -> None:
    assert "move_module" in _refusal(_BASE, "src/app/util/Base.java", "Base", "Root").reason


def test_a_package_private_java_class_renames() -> None:
    files = {
        "src/app/Util.java": "package app;\n\nclass Helper {}\nclass Util { Helper h = new Helper(); }\n"
    }
    plan = _plan(files, "src/app/Util.java", "Helper", "Aid")
    assert plan.changes["src/app/Util.java"].count("Aid") == 3


def test_a_family_with_an_outside_base_refuses() -> None:
    files = {
        "src/app/R.java": "package app;\n\nclass R implements Runnable { public void run() {} }\n"
    }
    assert "outside the project" in _refusal(files, "src/app/R.java", "R.run", "go").reason


def test_an_unknown_star_import_is_unsure() -> None:
    files = {
        **_GREETER,
        "src/x/X.java": "package x;\n\nimport java.util.*;\n\nclass X { Greeter g; }\n",
    }
    assert _refusal(files, "src/app/util/Greeter.kt", "Greeter", "Welcomer").spots == [
        Spot("src/x/X.java", 5)
    ]


def test_a_call_in_an_anonymous_class_is_unsure() -> None:
    files = {
        **_BASE,
        "src/app/A.java": "package app;\n\nimport app.util.Base;\n\nclass A extends Base {\n"
        "    Runnable r = new Runnable() { public void run() { greet(); } };\n}\n",
    }
    assert (
        Spot("src/app/A.java", 6)
        in _refusal(files, "src/app/util/Base.java", "Base.greet", "welcome").spots
    )


def test_a_broken_file_holding_the_name_is_unsure() -> None:
    files = {**_GREETER, "src/app/Bad.kt": "package app\n\nfun f( { Greeter() }\n"}
    assert _refusal(files, "src/app/util/Greeter.kt", "Greeter", "Welcomer").spots == [
        Spot("src/app/Bad.kt", 3)
    ]


# --- Hostile ---------------------------------------------------------------------------------


@pytest.mark.parametrize("new", ["fun", "class", "val", "1a", ""])
def test_a_keyword_new_name_refuses(new: str) -> None:
    assert _refusal(_GREETER, "src/app/util/Greeter.kt", "Greeter", new).reason


def test_a_taken_sibling_refuses() -> None:
    files = {"src/app/A.kt": "package app\n\nclass A {\n    fun go() {}\n    fun run() {}\n}\n"}
    assert _refusal(files, "src/app/A.kt", "A.go", "run").spots == [Spot("src/app/A.kt", 5)]


def test_the_name_as_a_string_is_unsure() -> None:
    files = {**_BASE, "src/app/Z.java": 'package app;\n\nclass Z { String s = "greet"; }\n'}
    assert _refusal(files, "src/app/util/Base.java", "Base.greet", "welcome").spots == [
        Spot("src/app/Z.java", 3)
    ]


def test_a_local_receiver_is_unsure() -> None:
    files = {
        **_BASE,
        "src/app/Z.java": "package app;\n\nimport app.util.Base;\n\nclass Z { void f(Base b) { b.greet(); } }\n",
    }
    assert _refusal(files, "src/app/util/Base.java", "Base.greet", "welcome").spots == [
        Spot("src/app/Z.java", 5)
    ]


def test_a_nested_type_refuses() -> None:
    files = {"src/app/A.java": "package app;\n\nclass A { static class Inner {} }\n"}
    assert "nested" in _refusal(files, "src/app/A.java", "A.Inner", "Other").reason


def test_an_overload_refuses() -> None:
    files = {"src/app/A.java": "package app;\n\nclass A { void go() {} void go(int x) {} }\n"}
    assert "more than once" in _refusal(files, "src/app/A.java", "A.go", "run").reason
