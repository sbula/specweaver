# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Java, Kotlin, Rust, C or C++ file moved, and every reference to it rewritten.

Proves: D-SENS-06 FR-10

| Bucket | Case |
|---|---|
| Happy | a Java class to another package; a Kotlin file; a Rust module renamed; a C header |
| Boundary | a Java rename in its folder renames the public class; a C++ source with its own include |
| Degradation | same-package uses without import; a `*` import; a Rust move to another folder; `mod.rs` |
| Hostile | an include found only through an include path; a Java file outside its source root |
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.refactor.move import MovePlan, plan_move
from specweaver.workspace.ast.refactor.rename import RenameRefusal, Spot

_JAVA = {
    "src/main/java/app/util/Greeter.java": 'package app.util;\n\npublic class Greeter {\n    public String greet() { return "hi"; }\n}\n',
    "src/main/java/app/Main.java": "package app;\n\nimport app.util.Greeter;\n\nclass Main { Greeter g = new Greeter(); }\n",
}


def _plan(files, path, new, parser) -> MovePlan:  # type: ignore[no-untyped-def]
    result = plan_move(files, path, new, parser)
    assert isinstance(result, MovePlan), result
    return result


def _refusal(files, path, new, parser) -> RenameRefusal:  # type: ignore[no-untyped-def]
    result = plan_move(files, path, new, parser)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Java and Kotlin -------------------------------------------------------------------------


def test_a_java_class_to_another_package() -> None:
    plan = _plan(
        _JAVA,
        "src/main/java/app/util/Greeter.java",
        "src/main/java/app/words/Greeter.java",
        JavaCodeStructure(),
    )

    assert plan.changes["src/main/java/app/words/Greeter.java"].startswith("package app.words;\n")
    assert "import app.words.Greeter;" in plan.changes["src/main/java/app/Main.java"]


def test_a_java_rename_in_its_folder_renames_the_public_class() -> None:
    plan = _plan(
        _JAVA,
        "src/main/java/app/util/Greeter.java",
        "src/main/java/app/util/Welcomer.java",
        JavaCodeStructure(),
    )

    assert "public class Welcomer {" in plan.changes["src/main/java/app/util/Welcomer.java"]
    assert plan.changes["src/main/java/app/Main.java"] == (
        "package app;\n\nimport app.util.Welcomer;\n\nclass Main { Welcomer g = new Welcomer(); }\n"
    )


def test_a_kotlin_file_to_another_package() -> None:
    files = {
        "src/main/kotlin/app/util/Tools.kt": "package app.util\n\nfun shout(s: String) = s\n",
        "src/main/kotlin/app/Main.kt": 'package app\n\nimport app.util.shout\n\nval x = shout("x")\n',
    }
    plan = _plan(
        files,
        "src/main/kotlin/app/util/Tools.kt",
        "src/main/kotlin/app/text/Tools.kt",
        KotlinCodeStructure(),
    )
    assert plan.changes["src/main/kotlin/app/text/Tools.kt"].startswith("package app.text\n")
    assert "import app.text.shout" in plan.changes["src/main/kotlin/app/Main.kt"]


def test_same_package_uses_without_import_refuse() -> None:
    files = {
        **_JAVA,
        "src/main/java/app/util/Near.java": "package app.util;\n\nclass Near { Greeter g; }\n",
    }
    refusal = _refusal(
        files,
        "src/main/java/app/util/Greeter.java",
        "src/main/java/app/words/Greeter.java",
        JavaCodeStructure(),
    )
    assert refusal.spots == [Spot("src/main/java/app/util/Near.java", 3)]


def test_a_star_import_using_the_class_refuses() -> None:
    files = {
        **_JAVA,
        "src/main/java/app/Star.java": "package app;\n\nimport app.util.*;\n\nclass Star { Greeter g; }\n",
    }
    refusal = _refusal(
        files,
        "src/main/java/app/util/Greeter.java",
        "src/main/java/app/words/Greeter.java",
        JavaCodeStructure(),
    )
    assert Spot("src/main/java/app/Star.java", 3) in refusal.spots


def test_a_java_file_moved_outside_its_source_root_refuses() -> None:
    assert (
        "source root"
        in _refusal(
            _JAVA, "src/main/java/app/util/Greeter.java", "lib/Greeter.java", JavaCodeStructure()
        ).reason
    )


# --- Rust ------------------------------------------------------------------------------------

_CRATE = {
    "Cargo.toml": '[package]\nname = "app"\n',
    "src/lib.rs": "pub mod util;\nmod run;\n",
    "src/util.rs": "pub fn total(a: u32) -> u32 { a }\n",
    "src/run.rs": "use crate::util::total;\nfn go() -> u32 { total(1) + crate::util::total(2) + util_free() }\nfn util_free() -> u32 { 0 }\n",
}


def test_a_rust_module_renamed_in_its_folder() -> None:
    plan = _plan(_CRATE, "src/util.rs", "src/tools.rs", RustCodeStructure())

    assert plan.changes["src/lib.rs"] == "pub mod tools;\nmod run;\n"
    assert plan.changes["src/run.rs"].startswith(
        "use crate::tools::total;\nfn go() -> u32 { total(1) + crate::tools::total(2)"
    )
    assert plan.changes["src/tools.rs"] == _CRATE["src/util.rs"]


def test_a_rust_move_to_another_folder_refuses() -> None:
    assert (
        "folder" in _refusal(_CRATE, "src/util.rs", "src/deep/util.rs", RustCodeStructure()).reason
    )


def test_a_rust_mod_rs_refuses() -> None:
    files = {**_CRATE, "src/lib.rs": "mod a;\n", "src/a/mod.rs": "pub fn x() {}\n"}
    assert "mod.rs" in _refusal(files, "src/a/mod.rs", "src/a/inner.rs", RustCodeStructure()).reason


# --- C and C++ -------------------------------------------------------------------------------

_C = {
    "src/util.h": "int total(int a);\n",
    "src/util.c": '#include "util.h"\nint total(int a) { return a; }\n',
    "src/app/main.c": '#include "../util.h"\nint main(void) { return total(1); }\n',
}


def test_a_c_header_moved_and_its_includes_follow() -> None:
    plan = _plan(_C, "src/util.h", "src/inc/util.h", CCodeStructure())

    assert plan.changes["src/util.c"] == '#include "inc/util.h"\nint total(int a) { return a; }\n'
    assert plan.changes["src/app/main.c"].startswith('#include "../inc/util.h"\n')


def test_a_c_source_moved_keeps_its_own_include_working() -> None:
    plan = _plan(_C, "src/util.c", "src/impl/util.c", CCodeStructure())
    assert plan.changes["src/impl/util.c"].startswith('#include "../util.h"\n')


def test_an_include_found_only_through_an_include_path_is_unsure() -> None:
    files = {**_C, "src/app/other.c": '#include "util.h"\nint f(void) { return total(2); }\n'}
    refusal = _refusal(files, "src/util.h", "src/inc/util.h", CCodeStructure())
    assert refusal.spots == [Spot("src/app/other.c", 1)]


def test_the_moved_class_using_an_old_neighbour_refuses() -> None:
    files = {
        **_JAVA,
        "src/main/java/app/util/Helper.java": "package app.util;\n\nclass Helper {}\n",
        "src/main/java/app/util/Greeter.java": "package app.util;\n\npublic class Greeter {\n    Helper h;\n}\n",
    }
    refusal = _refusal(
        files,
        "src/main/java/app/util/Greeter.java",
        "src/main/java/app/words/Greeter.java",
        JavaCodeStructure(),
    )
    assert refusal.spots == [Spot("src/main/java/app/util/Greeter.java", 4)]
