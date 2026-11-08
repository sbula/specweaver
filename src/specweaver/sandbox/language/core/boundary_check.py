# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The boundary rule judged on one code file, the same way in every language.

The file's parser lists its imports; the language's resolver names the project file or folder each
reaches (`workspace/ast/refactor/imports.py`); the effective rule of the file's folder, built from
every `context.yaml` under the project root, says whether that is allowed. An import that reaches
nothing in the project is counted; only an inherited `forbids` entry that names it by its written
name judges it. Manifest paths start at the project root. Runs no process: it reads files and
judges.
"""

from __future__ import annotations

import logging
import os
import posixpath
from pathlib import Path
from typing import Any

import pathspec

from specweaver.assurance.graph.boundary_rule import BoundaryRule
from specweaver.commons.languages import LANGUAGE_SUFFIXES, has_cpp_sources, language_of
from specweaver.commons.qa import ArchitectureRunResult, ArchitectureViolation
from specweaver.graph.topology.topology import load_nodes
from specweaver.sandbox.language.core.boundary_extras import run_extras
from specweaver.workspace.ast.parsers.factory import get_default_parsers, parser_for
from specweaver.workspace.ast.refactor.imports import targets_for

logger = logging.getLogger(__name__)

#: The files each language's resolver reads: its own family, plus the manifests that place it.
_FAMILY: dict[str, tuple[str, ...]] = {
    "java": (*LANGUAGE_SUFFIXES["java"], *LANGUAGE_SUFFIXES["kotlin"]),
    "kotlin": (*LANGUAGE_SUFFIXES["java"], *LANGUAGE_SUFFIXES["kotlin"]),
    "typescript": (*LANGUAGE_SUFFIXES["typescript"], *LANGUAGE_SUFFIXES["javascript"]),
    "javascript": (*LANGUAGE_SUFFIXES["typescript"], *LANGUAGE_SUFFIXES["javascript"]),
    "c": (*LANGUAGE_SUFFIXES["c"], *LANGUAGE_SUFFIXES["cpp"]),
    "cpp": (*LANGUAGE_SUFFIXES["c"], *LANGUAGE_SUFFIXES["cpp"]),
}
_PLACING = {"go": ("go.mod",), "rust": ("Cargo.toml",), "typescript": ("tsconfig.json",)}


def check_boundaries(project_root: Path, target: str) -> ArchitectureRunResult:
    """Each import of `target` (relative to `project_root`) judged by its folder's effective rule."""
    return _Judge(project_root).judge(target)


def check_architecture(project_root: Path, target: str, executor: Any) -> ArchitectureRunResult:
    """The shared check on a file, or on every code file under a folder, plus each stricter tool
    the project configured for the languages it found.

    The QA atom's `run_architecture` intent runs this; `qa_atom` hands it over with the executor.
    """
    judge = _Judge(project_root)
    files = judge.code_files(target)
    verdicts = [judge.judge(f) for f in files]
    judged = [v for v in verdicts if not v.note]
    languages = sorted({lang for f in files if (lang := language_of(f))})
    extras = [run for lang in languages for run in run_extras(project_root, lang, executor)]
    violations = [
        *(v for r in judged for v in r.violations),
        *(v for e in extras for v in e.violations),
    ]
    note = "" if judged or any(e.ran for e in extras) else _nothing_judged(verdicts, target)
    unmapped = sum(r.unmapped for r in judged)
    return ArchitectureRunResult(
        len(violations), violations, note=note, unmapped=unmapped, extras=extras
    )


def _nothing_judged(verdicts: list[ArchitectureRunResult], target: str) -> str:
    if len(verdicts) == 1:
        return verdicts[0].note
    return f"no context.yaml covers any code file under {target}; no boundary rule was examined."


class _Judge:
    """The project's rules and each language's files, read once for any number of files."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root
        nodes, _ = load_nodes(project_root)
        self._rule = BoundaryRule(nodes, project_root)
        self._ignored = _ignored(project_root)
        self._families: dict[str, tuple[dict[str, str], Any]] = {}
        self._cpp: bool | None = None

    def _cpp_sources(self) -> bool:
        """Whether the project has C++ sources, so its headers are C++; walked once."""
        if self._cpp is None:
            self._cpp = has_cpp_sources(_walk(self._root, self._ignored))
        return self._cpp

    def code_files(self, target: str) -> list[str]:
        """`target` itself, or every code file under it when it is a folder."""
        if not (self._root / target).is_dir():
            return [target]
        return sorted(f for f in _walk(self._root, self._ignored, target) if language_of(f))

    def judge(self, target: str) -> ArchitectureRunResult:
        language = language_of(target, cpp_sources=self._cpp_sources())
        if language is None:
            return ArchitectureRunResult(
                0, note=f"{target} is not a code file; no boundary was examined."
            )
        folder = posixpath.dirname(target)
        owner = self._rule.owner(folder)
        if owner is None:
            return ArchitectureRunResult(
                0,
                note=f"no context.yaml covers this file ({target}); no boundary rule was examined.",
            )
        files, reach = self._family(language)
        code = files.get(target)
        if code is None:
            code = (self._root / target).read_text(encoding="utf-8")
        parser = parser_for(target, cpp_sources=self._cpp_sources())
        if parser is None:
            return ArchitectureRunResult(
                0, note=f"no parser reads {target}; no boundary was examined."
            )
        violations: list[ArchitectureViolation] = []
        unmapped = 0
        for written in parser.extract_imports(code):
            reached = reach(target, written) if reach else None
            if reached is None:
                banned = self._rule.forbids_library(folder, written)
                if banned is None:
                    unmapped += 1
                else:
                    violations.append(_library_violation(target, written, *banned))
            elif not self._rule.allows(folder, _module(reached)):
                fix = _fix(self._rule, folder, _module(reached), owner)
                violations.append(_violation(target, written, reached, owner, fix))
        return ArchitectureRunResult(len(violations), violations, unmapped=unmapped)

    def _family(self, language: str) -> tuple[dict[str, str], Any]:
        if language not in self._families:
            files = _read_family(self._root, language, self._ignored)
            self._families[language] = (files, targets_for(files, language))
        return self._families[language]


def _module(path: str) -> str:
    """A file names its module without its ending, so `src/core.py` matches the entry `src/core`."""
    return posixpath.splitext(path)[0] if language_of(path) else path


def _fix(rule: BoundaryRule, folder: str, module: str, owner: str) -> str:
    """What the owner's manifest must say: `consumes`, and `widens` too where the rule needs it."""
    manifest = posixpath.join(owner, "context.yaml") if owner else "context.yaml"
    if rule.needs_widens(folder, module):
        return f"add '{module}' to consumes and to widens: with a reason in {manifest}"
    return f"add '{module}' to consumes in {manifest}"


def _violation(
    target: str, written: str, reached: str, owner: str, fix: str
) -> ArchitectureViolation:
    return ArchitectureViolation(
        file=target,
        code="BoundaryRule",
        message=(
            f"{target}: import '{written}' reaches '{reached}', which the rule of '{owner or '.'}' "
            f"does not allow; {fix}"
        ),
    )


def _library_violation(target: str, written: str, folder: str, entry: str) -> ArchitectureViolation:
    manifest = posixpath.join(folder, "context.yaml") if folder else "context.yaml"
    return ArchitectureViolation(
        file=target,
        code="BoundaryRule",
        message=(
            f"{target}: import '{written}' reaches no project file, and the forbids entry "
            f"'{entry}' in {manifest} names it; remove the import, or remove the entry"
        ),
    )


def _read_family(project_root: Path, language: str, ignored: pathspec.PathSpec) -> dict[str, str]:
    """Every readable file the language's resolver needs, by path relative to the root."""
    suffixes = _FAMILY.get(language, LANGUAGE_SUFFIXES[language])
    names = _PLACING.get(language, ())
    files: dict[str, str] = {}
    for relative in _walk(project_root, ignored):
        if not (relative.endswith(suffixes) or posixpath.basename(relative) in names):
            continue
        try:
            files[relative] = (project_root / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("boundary check: %s is skipped, it cannot be read: %s", relative, exc)
    return files


def _walk(project_root: Path, ignored: pathspec.PathSpec, start: str = "") -> list[str]:
    """Every file under `start` not ignored, relative to the root; an ignored folder is not entered."""
    found: list[str] = []
    for folder, dirs, names in os.walk(project_root / start):
        relative = Path(folder).relative_to(project_root).as_posix()
        prefix = "" if relative == "." else f"{relative}/"
        dirs[:] = [d for d in dirs if not ignored.match_file(f"{prefix}{d}/")]
        found += [f"{prefix}{n}" for n in names if not ignored.match_file(f"{prefix}{n}")]
    return found


def _ignored(project_root: Path) -> pathspec.PathSpec:
    """`.git`, each parser's default ignored folders and the project's `.specweaverignore`."""
    lines = [".git/"]
    for parser in get_default_parsers().values():
        lines.extend(parser.get_default_directory_ignores())
    ignore_file = project_root / ".specweaverignore"
    if ignore_file.is_file():
        lines.extend(ignore_file.read_text(encoding="utf-8").splitlines())
    return pathspec.PathSpec.from_lines("gitignore", lines)
