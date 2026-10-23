# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which language a file ending is, and how each language names and places its tests.

The one copy: prompts, parsers, rename, the archetype rules and the task's files all read it.
"""

from __future__ import annotations

from pathlib import PurePath

#: Every ending of each programming language.
LANGUAGE_SUFFIXES: dict[str, tuple[str, ...]] = {
    "python": (".py", ".pyi"),
    "java": (".java",),
    "kotlin": (".kt", ".kts"),
    "typescript": (".ts", ".tsx"),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "rust": (".rs",),
    "go": (".go",),
    "c": (".c", ".h"),
    "cpp": (".cpp", ".hpp", ".cc", ".cxx"),
}

_LANGUAGE_OF = {suffix: name for name, suffixes in LANGUAGE_SUFFIXES.items() for suffix in suffixes}

#: Where each language keeps its tests, relative to the project.
_TESTS_ROOT = {
    "python": "tests",
    "java": "src/test/java",
    "kotlin": "src/test/kotlin",
    "typescript": "tests",
    "rust": "tests",
}


def language_of(path: str | PurePath) -> str | None:
    """The language `path`'s ending names, or None."""
    return _LANGUAGE_OF.get(PurePath(path).suffix.lower())


def root_of_tests(language: str) -> str | None:
    """The folder a language's tests live under, or None for a language without a convention."""
    return _TESTS_ROOT.get(language)


def name_tests_for(code_name: str, language: str) -> str | None:
    """The test file a code file `code_name` has in `language`, or None without a convention."""
    code = PurePath(code_name)
    names = {
        "python": f"test_{code.stem}.py",
        "java": f"{code.stem}Test.java",
        "kotlin": f"{code.stem}Test.kt",
        "typescript": f"{code.stem}.test.ts",
        "rust": f"{code.stem}.rs",
    }
    return names.get(language)
