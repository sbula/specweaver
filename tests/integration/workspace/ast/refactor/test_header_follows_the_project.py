# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A `.h` file is C++ in a project with C++ sources and C otherwise, in every tool that asks.

Proves: TECH-079 FR-13

Real project folders; the boundary check and rename each through their own entry.

| Bucket | Case |
|---|---|
| Happy | in a C++ project the boundary check and rename read `lib.h` as C++; in a C project both read it as C |
| Boundary | `LIB.H` follows the same rule; a project of headers only is C |
| Degradation | a `.h` with no project files given is C |
| Hostile | a `.hpp` is C++ whatever the project holds; a `.c` stays C in a C++ project |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.languages import has_cpp_sources, language_of

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("names", "header", "language"),
    [
        (["main.cpp", "lib.h"], "lib.h", "cpp"),
        (["main.c", "lib.h"], "lib.h", "c"),
        (["main.cc", "LIB.H"], "LIB.H", "cpp"),
        (["a.h", "b.h"], "a.h", "c"),
        (["main.c"], "x.hpp", "cpp"),
        (["main.cpp"], "util.c", "c"),
    ],
)
def test_the_table_answers_by_the_project(names: list[str], header: str, language: str) -> None:
    assert language_of(header, cpp_sources=has_cpp_sources(names)) == language


def test_a_header_alone_is_c() -> None:
    assert language_of("lib.h") == "c"


def _project(root: Path, names: list[str]) -> None:
    (root / "context.yaml").write_text("name: app\nlevel: module\n", encoding="utf-8")
    for name in names:
        (root / name).write_text("#include <stdio.h>\n", encoding="utf-8")


@pytest.mark.parametrize(("main", "language"), [("main.cpp", "cpp"), ("main.c", "c")])
def test_the_boundary_check_and_rename_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, main: str, language: str
) -> None:
    from specweaver.sandbox.language.core import boundary_check
    from specweaver.workspace.ast.refactor.c_family import CppResolver, CResolver
    from specweaver.workspace.ast.refactor.rename import resolver_for

    _project(tmp_path, [main, "lib.h"])
    asked: list[str] = []
    real = boundary_check.targets_for
    monkeypatch.setattr(
        boundary_check, "targets_for", lambda files, lang: asked.append(lang) or real(files, lang)
    )

    boundary_check.check_boundaries(tmp_path, "lib.h")
    files = {name: (tmp_path / name).read_text("utf-8") for name in (main, "lib.h")}

    assert asked == [language]
    assert resolver_for("lib.h", files) is {"cpp": CppResolver, "c": CResolver}[language]


@pytest.mark.parametrize(
    ("cpp_sources", "kind"), [(True, "CppCodeStructure"), (False, "CCodeStructure")]
)
def test_the_parser_lookup_follows_the_project(cpp_sources: bool, kind: str) -> None:
    from specweaver.workspace.ast.parsers.factory import parser_for

    assert type(parser_for("lib.h", cpp_sources=cpp_sources)).__name__ == kind
