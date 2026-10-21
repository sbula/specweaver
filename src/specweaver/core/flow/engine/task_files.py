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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.commons.spec_names import module_stem

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE = re.compile(r"[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*")
_HEADER = re.compile(r"^>\s*\*\*Package\*\*:\s*(.*?)\s*$", re.IGNORECASE)
_SOURCE_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)", re.MULTILINE)
_GRADLE_GROUP = re.compile(r"""^\s*group\s*=?\s*["']([\w.]+)["']""", re.MULTILINE)


@dataclass(frozen=True)
class TaskFiles:
    """Repo-relative, forward slashes. `extra`: files the code step also changes (Rust's module
    declaration)."""

    code: str
    tests: str
    extra: tuple[str, ...] = ()

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
        return TaskFiles(f"src/{stem}.ts", f"tests/{stem}.test.ts")
    if chosen == "rust":
        module = stem.replace("-", "_")
        return TaskFiles(f"src/{module}.rs", f"tests/{module}.rs", (_rust_root(project_root),))
    return TaskFiles(f"src/{stem}.py", f"tests/test_{stem}.py")


def _jvm(project_root: Path, spec_path: Path, stem: str, language: str) -> TaskFiles:
    name = "".join(part[:1].upper() + part[1:] for part in re.split(r"[_-]+", stem) if part)
    package = (
        _spec_package(spec_path) or _source_package(project_root, language) or _group(project_root)
    )
    folder = f"{package.replace('.', '/')}/" if package else ""
    ext = "java" if language == "java" else "kt"
    return TaskFiles(
        f"src/main/{language}/{folder}{name}.{ext}", f"src/test/{language}/{folder}{name}Test.{ext}"
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


def _rust_root(project_root: Path) -> str:
    """The file that declares the crate's modules: `src/lib.rs`, else `src/main.rs`."""
    if (
        not (project_root / "src" / "lib.rs").is_file()
        and (project_root / "src" / "main.rs").is_file()
    ):
        return "src/main.rs"
    return "src/lib.rs"
