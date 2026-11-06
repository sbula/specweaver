# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which language and build tool a project is, decided once from its root, or a refusal.

Pure: the caller lists the root and hands over a reader. Only the root's own files count.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from specweaver.commons.languages import language_of

if TYPE_CHECKING:
    from collections.abc import Callable

#: The languages SpecWeaver generates code for.
GENERATED_LANGUAGES = ("python", "java", "kotlin", "typescript", "rust")

#: The build tools `[implement] build_tool` may name.
BUILD_TOOLS = ("uv", "maven", "gradle", "cargo", "npm")

_PYTHON_BUILDS = ("pyproject.toml", "uv.lock", "requirements*.txt")
_GRADLE_BUILDS = ("build.gradle", "build.gradle.kts")
_JVM_BUILDS = ("pom.xml", *_GRADLE_BUILDS)
_SETTING = "set [implement] {} in specweaver.toml"
#: A JVM build is one candidate; Java or Kotlin is decided after.
_JVM = "java or kotlin"
#: The languages each build tool builds.
_BUILDS = {
    "uv": ("python",),
    "maven": ("java", "kotlin"),
    "gradle": ("java", "kotlin"),
    "cargo": ("rust",),
    "npm": ("typescript",),
}


@dataclass(frozen=True)
class ProjectProfile:
    language: str
    #: `""` when the root has no build file of the language.
    build_tool: str


class ProjectUndecidedError(Exception):
    """The root does not name one language or build tool; the message names the setting."""


def decide_profile(
    root_files: frozenset[str],
    read: Callable[[str], str | None],
    *,
    kotlin_sources: bool,
    language: str | None = None,
    build_tool: str | None = None,
) -> ProjectProfile:
    """The profile of a project whose root holds `root_files`.

    `read` returns a root file's text, or None when it cannot be read. `kotlin_sources` says the
    project keeps Kotlin under `src/main/kotlin`. `language` and `build_tool` are the
    `[implement]` pins: a set pin wins over the root, and pins that disagree are refused.
    """
    if language is not None and build_tool is not None and not _builds(build_tool, language):
        raise ProjectUndecidedError(
            f'[implement] language = "{language}" and build_tool = "{build_tool}" do not agree; '
            "change one of them in specweaver.toml"
        )
    if language is None:
        language = _language(root_files, read, kotlin_sources=kotlin_sources)
    elif language not in GENERATED_LANGUAGES:
        raise ProjectUndecidedError(_cannot_generate(f"{language} ([implement] language)"))
    if build_tool is None:
        return ProjectProfile(language, _build_tool(language, root_files))
    if not _builds(build_tool, language):
        raise ProjectUndecidedError(
            f'[implement] build_tool = "{build_tool}" does not build {language}; '
            f"{_SETTING.format('language')}, or change build_tool"
        )
    return ProjectProfile(language, build_tool)


def _builds(build_tool: str, language: str) -> bool:
    return language in _BUILDS.get(build_tool, ())


def _cannot_generate(subject: str) -> str:
    generated = f"{', '.join(GENERATED_LANGUAGES[:-1])} and {GENERATED_LANGUAGES[-1]}"
    return f"{subject} cannot be generated; SpecWeaver generates {generated}"


def _language(
    root_files: frozenset[str], read: Callable[[str], str | None], *, kotlin_sources: bool
) -> str:
    found = _build_file_languages(root_files)
    kind = "build files"
    if not found:
        found = _code_languages(root_files)
        kind = "code files"
    if not found:
        raise ProjectUndecidedError(
            f"the project root has no build file and no code file; {_SETTING.format('language')}"
        )
    if len(found) > 1:
        raise ProjectUndecidedError(
            f"the project root has {kind} for {_listed(found)}; {_SETTING.format('language')}"
        )
    [(language, names)] = found.items()
    if language == _JVM:
        jvm = sorted(name for name in root_files if name in _JVM_BUILDS)
        return "kotlin" if kotlin_sources or _names_kotlin(jvm, read) else "java"
    if language not in GENERATED_LANGUAGES:
        raise ProjectUndecidedError(_cannot_generate(_listed({language: names})))
    return language


def _build_file_languages(root_files: frozenset[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    code = {language_of(name) for name in root_files}
    for name in sorted(root_files):
        language = _build_file_language(name, root_files, code)
        if language:
            found.setdefault(language, []).append(name)
    return found


def _build_file_language(
    name: str, root_files: frozenset[str], code: set[str | None]
) -> str | None:
    if any(fnmatchcase(name, pattern) for pattern in _PYTHON_BUILDS):
        return "python"
    if name in _JVM_BUILDS:
        return _JVM
    match name:
        case "package.json":
            typed = "tsconfig.json" in root_files or "typescript" in code
            return "typescript" if typed else "javascript"
        case "Cargo.toml":
            return "rust"
        case "go.mod":
            return "go"
        case "CMakeLists.txt":
            return "cpp" if "cpp" in code else "c"
    return None


def _code_languages(root_files: frozenset[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name in sorted(root_files):
        language = language_of(name)
        if language:
            found.setdefault(language, []).append(name)
    return found


def _names_kotlin(builds: list[str], read: Callable[[str], str | None]) -> bool:
    return any("kotlin" in (read(build) or "").lower() for build in builds)


def _listed(found: dict[str, list[str]]) -> str:
    parts = [
        f"{language} ({', '.join(names[:3] + ['...'] * (len(names) > 3))})"
        for language, names in sorted(found.items())
    ]
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _build_tool(language: str, root_files: frozenset[str]) -> str:
    if language == "python":
        return "uv" if {"pyproject.toml", "uv.lock"} & root_files else ""
    if language == "rust":
        return "cargo" if "Cargo.toml" in root_files else ""
    if language == "typescript":
        return "npm" if "package.json" in root_files else ""
    gradle = sorted(set(_GRADLE_BUILDS) & root_files)
    if "pom.xml" in root_files and gradle:
        raise ProjectUndecidedError(
            f"the project root has pom.xml and {gradle[0]}; "
            f"{_SETTING.format('build_tool')} (maven or gradle)"
        )
    if "pom.xml" in root_files:
        return "maven"
    return "gradle" if gradle else ""
