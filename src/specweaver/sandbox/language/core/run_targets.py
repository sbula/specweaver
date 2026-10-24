# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Turning a test target into the filter a build tool takes, so a run runs exactly what it names.

A target is `<path>` or `<path>::<name>`: one test, one file, one folder with its subfolders, or
the project (empty or `.`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

_EXTENSIONS = {"java": ".java", "kotlin": ".kt"}


class TargetError(ValueError):
    """A target the build tool has no filter for; running everything instead would not be it."""


@dataclass(frozen=True)
class RunTarget:
    """What a test target names: `path` in `/` form, the test `name`, and its size."""

    path: str
    name: str
    kind: Literal["test", "file", "folder", "project"]


def parse_target(target: str) -> RunTarget:
    """The size a target names. The first `::` splits off the name; a drive letter has one colon."""
    path, _, name = target.replace("\\", "/").partition("::")
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    path = path.rstrip("/")
    if path in ("", "."):
        return RunTarget("", "", "project")
    if name:
        return RunTarget(path, name, "test")
    return RunTarget(path, "", "file" if PurePosixPath(path).suffix else "folder")


def no_test_ran(target: str, detail: str = "") -> str:
    """Why a run that ran no test is a failure: the target names nothing that exists."""
    said = f" ({detail})" if detail else ""
    named = "the project" if parse_target(target).kind == "project" else target
    return f"no test ran for {named}: the target names no test{said}"


def jvm_test_args(target: RunTarget, language: str, tool: str) -> list[str]:
    """Gradle's `--tests` or Maven's `-Dtest` for the target; nothing for the project.

    A file that is not a test file keeps running every test."""
    selector = _jvm_selector(target, language, tool)
    if not selector:
        return []
    if tool == "gradle":
        return ["--tests", selector]
    # Maven fails on its own when nothing matches; the empty run is judged by the runner instead.
    return [
        f"-Dtest={selector}",
        "-Dsurefire.failIfNoSpecifiedTests=false",
        "-DfailIfNoTests=false",
    ]


def _jvm_selector(target: RunTarget, language: str, tool: str) -> str:
    """The class, method or package pattern in the tool's spelling; empty for everything."""
    if target.kind == "folder":
        package = _jvm_package(target.path, language)
        if not package:
            return ""
        return f"{'.'.join(package)}.*" if tool == "gradle" else f"{'/'.join(package)}/**/*"
    if target.kind == "project":
        return ""
    selector = jvm_test_class(target.path, language) or ""
    if selector and target.name:
        selector += f".{target.name}" if tool == "gradle" else f"#{target.name}"
    return selector


def _jvm_package(folder: str, language: str) -> tuple[str, ...]:
    """The package a folder holds; empty for the test root or anything above it."""
    parts = PurePosixPath(folder).parts
    root = ("src", "test", language)
    if parts == root[: len(parts)]:
        return ()
    for index in range(len(parts) - 2):
        if parts[index : index + 3] in (root, ("src", "main", language)):
            return parts[index + 3 :]
    raise TargetError(f"{folder} is not under src/test/{language}/, so its tests have no package")


def jvm_test_class(target: str, language: str) -> str | None:
    """The class a JVM test file declares, fully qualified when it sits under `src/test/<lang>/`;
    None for a folder, the project, or a file outside the test sources."""
    path = PurePosixPath(target.replace("\\", "/"))
    if path.suffix != _EXTENSIONS.get(language) or "main" in path.parts[:-1]:
        return None
    parts = path.parts
    for index in range(len(parts) - 2):
        if parts[index : index + 3] == ("src", "test", language):
            return ".".join((*parts[index + 3 : -1], path.stem))
    return path.stem


def cargo_test_args(target: RunTarget) -> list[str]:
    """The `cargo test` arguments for the target. A name is matched with `--exact`; a test in a
    `src/` file is `<module>::tests::<name>`, the layout generation writes."""
    if target.kind == "project":
        return []
    parts = PurePosixPath(target.path).parts
    top = next((part for part in parts if part in ("src", "tests")), None)
    if top == "tests":
        rest = parts[parts.index("tests") + 1 :]
        if not rest:
            return ["--test", "*"]
        args = ["--test", PurePosixPath(rest[0]).stem]
        return [*args, "--", target.name, "--exact"] if target.name else args
    if top == "src":
        return _cargo_source_args(parts[parts.index("src") + 1 :], target)
    raise TargetError(
        f"{target.path} is neither under src/ nor tests/, so cargo has no filter for it"
    )


def _cargo_source_args(rest: tuple[str, ...], target: RunTarget) -> list[str]:
    """`--lib` (or `--bins` for `main.rs`) and the module path a file or folder under `src/` is."""
    if rest == ("main.rs",):
        where, module = ["--bins"], []
    else:
        where, module = ["--lib"], [PurePosixPath(part).stem for part in rest]
        if module and module[-1] in ("mod", "lib"):
            module.pop()
    if target.name:
        return [*where, "--", "::".join([*module, "tests", target.name]), "--exact"]
    return [*where, f"{'::'.join(module)}::"] if module else where


_JS_REGEX_SPECIALS = re.compile(r"[\\^$.*+?()[\]{}|/]")


def npm_test_args(target: RunTarget) -> list[str]:
    """What follows `npm test --` for Jest or Vitest: the path, a folder ending in `/` so a
    sibling with a longer name stays out, and a name escaped and anchored at both ends."""
    if target.kind == "project":
        return []
    if target.kind == "folder":
        return [f"{target.path}/"]
    if target.kind == "test":
        # The full name is the `describe` names and the test's, joined by spaces.
        name = _JS_REGEX_SPECIALS.sub(r"\\\g<0>", target.name)
        return [target.path, "-t", f"(^| ){name}$"]
    return [target.path]


def cargo_run_args(entrypoint: str) -> list[str]:
    """`--bin <x>` for `src/bin/<x>.rs` or `src/bin/<x>/main.rs`, `--example <x>` for
    `examples/<x>.rs`; nothing for the default binary or a path that climbs out."""
    parts = PurePosixPath(entrypoint.replace("\\", "/")).parts
    if ".." in parts or not parts or PurePosixPath(parts[-1]).suffix != ".rs":
        return []
    if parts[:2] == ("src", "bin"):
        rest = parts[2:]
        if len(rest) == 1:
            return ["--bin", PurePosixPath(rest[0]).stem]
        return ["--bin", rest[0]] if rest[1:] == ("main.rs",) else []
    if parts[0] == "examples" and len(parts) == 2:
        return ["--example", PurePosixPath(parts[1]).stem]
    return []


_WRAPPERS = {"gradle": ("gradlew", "gradlew.bat"), "maven": ("mvnw", "mvnw.cmd")}
_ON_PATH = {"gradle": "gradle", "maven": "mvn"}


def build_launcher(project: Path, tool: str) -> str:
    """The project's own wrapper (`./gradlew`, `./mvnw`), else the tool on PATH.

    A bare `gradlew` is looked up on PATH only, never in the project, so the wrapper is named by
    its path. The wrapper wins because the machine's own install may be too old for the project.
    """
    for wrapper in _WRAPPERS[tool]:
        if (project / wrapper).is_file():
            return wrapper if wrapper.endswith((".bat", ".cmd")) else f"./{wrapper}"
    return _ON_PATH[tool]
