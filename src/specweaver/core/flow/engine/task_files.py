# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The files one task writes, worked out once per language: generation writes them, the merge keeps
them, the coder's grant opens them and the QA steps test them.

| Language | Code | Tests |
|---|---|---|
| Python | `src/<stem>.py` | `tests/test_<stem>.py` |
| Java | `src/main/java/<pkg>/<Name>.java` | `src/test/java/<pkg>/<Name>Test.java` |
| Kotlin | `src/main/kotlin/<pkg>/<Name>.kt` | `src/test/kotlin/<pkg>/<Name>Test.kt` |
| TypeScript | `src/<stem>.ts` | `tests/<stem>.test.ts` |
| Rust | `src/<stem>.rs` | `tests/<stem>.rs` |

`<Name>` is the stem in PascalCase. `<pkg>` is the spec's `> **Package**:` line, else the longest
package prefix the existing sources share, else the build's group, else none.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from specweaver.commons.spec_names import module_stem

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE = re.compile(r"[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*")
_HEADER = re.compile(r"^>\s*\*\*Package\*\*:\s*(.*?)\s*$", re.IGNORECASE)
_SOURCE_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)", re.MULTILINE)
_GRADLE_GROUP = re.compile(r"""^\s*group\s*=?\s*["']([\w.]+)["']""", re.MULTILINE)

#: The file that declares a Rust task's module.
RUST_ROOT = "src/lib.rs"


@dataclass(frozen=True)
class TaskFiles:
    """Repo-relative, forward slashes. `extra`: files the code step also changes (Rust's module
    declaration). `language`: the language they were derived for, named or detected."""

    code: str
    tests: str
    extra: tuple[str, ...] = ()
    language: str = field(default="python", compare=False)

    @property
    def all(self) -> list[str]:
        return [self.code, self.tests, *self.extra]


def task_files_for(project_root: Path, spec_path: Path, language: str | None) -> TaskFiles:
    """The task's files for `language`; None detects it from the project's manifests.

    Raises `ValueError` naming the spec line when its `Package` line is not a dotted identifier.
    """
    from specweaver.sandbox.language.core._detect import detect_language

    stem = module_stem(spec_path)
    chosen = language or detect_language(project_root)
    if chosen in {"java", "kotlin"}:
        return _jvm(project_root, spec_path, stem, chosen)
    if chosen == "typescript":
        return TaskFiles(f"src/{stem}.ts", _tests(f"{stem}.ts", chosen), language=chosen)
    if chosen == "rust":
        # Always the library root: tests in `tests/` reach only a library crate, so a binary-only
        # crate gets a `lib.rs` beside its `main.rs`.
        module = stem.replace("-", "_")
        code = f"src/{module}.rs"
        return TaskFiles(code, _tests(code, chosen), (RUST_ROOT,), language=chosen)
    return TaskFiles(f"src/{stem}.py", _tests(f"{stem}.py", "python"), language="python")


def _tests(code: str, language: str, package_folder: str = "") -> str:
    """The test file of `code`, by the language's one convention (`commons.languages`)."""
    from specweaver.commons.languages import name_tests_for, root_of_tests

    return f"{root_of_tests(language)}/{package_folder}{name_tests_for(code, language)}"


def _jvm(project_root: Path, spec_path: Path, stem: str, language: str) -> TaskFiles:
    name = "".join(part[:1].upper() + part[1:] for part in re.split(r"[_-]+", stem) if part)
    package = (
        _spec_package(spec_path) or _source_package(project_root, language) or _group(project_root)
    )
    folder = f"{package.replace('.', '/')}/" if package else ""
    ext = "java" if language == "java" else "kt"
    return TaskFiles(
        f"src/main/{language}/{folder}{name}.{ext}",
        _tests(f"{name}.{ext}", language, folder),
        language=language,
    )


def _spec_package(spec_path: Path) -> str | None:
    try:
        lines = spec_path.read_text(encoding="utf-8").splitlines()
    except OSError:  # expected: an unreadable spec names no package; the next source decides
        return None
    for number, line in enumerate(lines, start=1):
        found = _HEADER.match(line)
        if found:
            package = found.group(1)
            if not _PACKAGE.fullmatch(package):
                msg = f"{spec_path.name}:{number}: Package {package!r} is not a dotted identifier"
                raise ValueError(msg)
            return package
    return None


def _source_package(project_root: Path, language: str) -> str | None:
    """The longest package prefix every main source shares, or None."""
    sources = sorted(
        (project_root / "src" / "main" / language).rglob(
            f"*.{'java' if language == 'java' else 'kt'}"
        )
    )
    packages = [
        found.group(1).split(".")
        for found in (
            _SOURCE_PACKAGE.search(path.read_text(encoding="utf-8", errors="replace"))
            for path in sources
        )
        if found
    ]
    if not packages:
        return None
    shared: list[str] = []
    for parts in zip(*packages, strict=False):
        if len(set(parts)) != 1:
            break
        shared.append(parts[0])
    return ".".join(shared) or None


def _group(project_root: Path) -> str | None:
    """The build's group: Maven's project `groupId`, else Gradle's `group`."""
    pom = project_root / "pom.xml"
    group = _maven_group(pom) if pom.is_file() else _gradle_group(project_root)
    return group if group and _PACKAGE.fullmatch(group) else None


def _maven_group(pom: Path) -> str | None:
    try:
        root = ElementTree.parse(pom).getroot()
    except ElementTree.ParseError:  # expected: a broken pom names no group
        return None
    return next((child.text for child in root if child.tag.endswith("groupId")), None)


def _gradle_group(project_root: Path) -> str | None:
    for name in ("build.gradle.kts", "build.gradle"):
        build = project_root / name
        if build.is_file():
            found = _GRADLE_GROUP.search(build.read_text(encoding="utf-8", errors="replace"))
            return found.group(1) if found else None
    return None


def task_brief(files: TaskFiles, project_root: Path) -> str | None:
    """What the model must know so the task's files build together; None for Python, whose prompt
    stays as it was."""
    if files.language in {"java", "kotlin"}:
        return _jvm_brief(files)
    if files.language == "rust":
        return _rust_brief(files, project_root)
    if files.language == "typescript":
        return _typescript_brief(files, project_root)
    return None


def _jvm_class(path: str) -> tuple[str, str]:
    """The package and simple class name a `src/<main|test>/<lang>/…` path declares."""
    parts = path.split("/")[3:]
    return ".".join(parts[:-1]), parts[-1].rsplit(".", 1)[0]


def _jvm_brief(files: TaskFiles) -> str:
    package, name = _jvm_class(files.code)
    _, test = _jvm_class(files.tests)
    where = f"package `{package}`" if package else "the default package (no package line)"
    subject = f"{package}.{name}" if package else name
    return (
        "## Task files\n"
        f"- Code: `{files.code}`, {where}, class `{name}`.\n"
        f"- Tests: `{files.tests}`, {where}, class `{test}`, testing `{subject}`."
    )


def _rust_brief(files: TaskFiles, project_root: Path) -> str:
    import tomllib

    module = files.code.rsplit("/", 1)[-1].removesuffix(".rs")
    try:
        manifest = tomllib.loads((project_root / "Cargo.toml").read_text(encoding="utf-8"))
        crate = str(manifest["package"]["name"]).replace("-", "_")
        uses = f"using `{crate}::{module}`"
    except (OSError, ValueError, KeyError, TypeError):  # expected: the brief says what is missing
        uses = "using the crate's module (Cargo.toml names no package)"
    return (
        "## Task files\n"
        f"- Code: `{files.code}`, declared as `pub mod {module};` in `{RUST_ROOT}`.\n"
        f"- Tests: `{files.tests}`, an integration test {uses}."
    )


def _typescript_brief(files: TaskFiles, project_root: Path) -> str:
    import json

    module = files.code.removesuffix(".ts")
    try:
        manifest = json.loads((project_root / "package.json").read_text(encoding="utf-8"))
        tools = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
    except (OSError, ValueError, AttributeError):  # expected: no readable manifest names no tool
        tools = {}
    tool = next(
        (name for key, name in (("vitest", "Vitest"), ("jest", "Jest")) if key in tools),
        "the project's `npm test` script",
    )
    return (
        "## Task files\n"
        f"- Code: `{files.code}`.\n"
        f"- Tests: `{files.tests}`, importing from `../{module}`, run by {tool}."
    )
