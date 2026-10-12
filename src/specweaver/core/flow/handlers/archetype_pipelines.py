# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which validation pipeline a file gets: its folder's archetype and, for code, its language.

Shared by the validate steps and `sw check`, so both judge a file by the same rules. An
archetype's languages are the `supported_languages` of its evaluator schema
(`workflows/evaluators/frameworks/<archetype>.yaml`, or the project's `.specweaver/evaluators/`);
a schema naming none judges any language.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.validation.pipeline import ValidationPipeline

logger = logging.getLogger(__name__)

SPEC_DEFAULT = "validation_spec_default"
CODE_DEFAULT = "validation_code_default"

#: The file endings of each language an archetype may name.
LANGUAGE_SUFFIXES: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "java": (".java",),
    "kotlin": (".kt", ".kts"),
    "typescript": (".ts", ".tsx"),
    "javascript": (".js", ".jsx"),
    "rust": (".rs",),
    "go": (".go",),
    "c": (".c", ".h"),
    "cpp": (".cpp", ".hpp", ".cc", ".cxx"),
}


def archetype_of(path: Path, project_path: Path | None) -> str | None:
    """The archetype the nearest `context.yaml` above `path` declares."""
    from specweaver.core.config.archetype_resolver import ArchetypeResolver

    return ArchetypeResolver(project_path).resolve(path) if project_path else None


def spec_pipeline(
    spec_path: Path, project_path: Path | None, *, feature: bool = False
) -> tuple[ValidationPipeline, str | None]:
    """The archetype's spec pipeline, else the default; and the archetype.

    A feature spec always gets the feature pipeline: an archetype bounds a component.
    """
    archetype = archetype_of(spec_path, project_path)
    if feature:
        return _load("validation_spec_feature", project_path), archetype
    pipeline = _archetype_pipeline("spec", archetype, project_path, None)
    return pipeline or _load(SPEC_DEFAULT, project_path), archetype


def code_pipeline(
    code_path: Path, project_path: Path | None
) -> tuple[ValidationPipeline, str | None]:
    """The archetype's code pipeline when it covers the file's language, else the default."""
    archetype = archetype_of(code_path, project_path)
    pipeline = _archetype_pipeline("code", archetype, project_path, code_path)
    if pipeline is None:
        return _load(CODE_DEFAULT, project_path), None
    return pipeline, archetype


def own_pipeline(
    level: str, path: Path, project_path: Path | None
) -> tuple[ValidationPipeline | None, str | None]:
    """The pipeline the file's archetype brings itself (`spec` or `code`), or None; and the archetype.

    None when there is no archetype, it ships no pipeline for `level`, or the code file is not in
    its languages — the caller then keeps its own choice.
    """
    archetype = archetype_of(path, project_path)
    code_path = path if level == "code" else None
    return _archetype_pipeline(level, archetype, project_path, code_path), archetype


def add_payload(
    pipeline: ValidationPipeline,
    path: Path,
    project_path: Path | None,
    archetype: str | None,
    *,
    parsers: Any = None,
    markers: bool = False,
) -> None:
    """Give every step the file's structure, and with `markers` its framework markers."""
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
    from specweaver.workflows.evaluators.loader import load_evaluator_schemas

    cwd = project_path or path.parent
    atom = CodeStructureAtom(
        cwd=cwd,
        evaluator_schemas=load_evaluator_schemas(project_dir=project_path),
        active_archetype=archetype or "generic",
        parsers=parsers,
    )
    relative = _inside(path, cwd)
    payload: dict[str, Any] = {}
    structure = atom.run({"intent": "read_file_structure", "path": relative})
    if structure.status.value == "SUCCESS":
        payload = structure.exports
    if markers:
        found = atom.run({"intent": "extract_framework_markers", "path": relative})
        if found.status.value == "SUCCESS" and "markers" in found.exports:
            payload["framework_markers"] = found.exports["markers"]
    for step in pipeline.steps:
        step.params["ast_payload"] = payload


def _archetype_pipeline(
    level: str, archetype: str | None, project_path: Path | None, code_path: Path | None
) -> ValidationPipeline | None:
    """`validation_<level>_<archetype>`; None without one, or when it skips the file's language."""
    if not archetype:
        return None
    name = f"validation_{level}_{archetype}"
    try:
        pipeline = _load(name, project_path)
    except FileNotFoundError:
        logger.debug("No pipeline %r; using the default", name)
        return None
    if code_path is None:
        return pipeline
    return pipeline if covers(languages_of(archetype, project_path), code_path) else None


def languages_of(archetype: str, project_path: Path | None) -> list[str]:
    """The languages the archetype's evaluator schema names; empty when it names none.

    Raises `ValueError` on a name `LANGUAGE_SUFFIXES` does not know: a misspelt language would
    otherwise make the archetype judge no file at all, silently.
    """
    from specweaver.workflows.evaluators.loader import load_evaluator_schemas

    schema = load_evaluator_schemas(project_dir=project_path).get(archetype) or {}
    languages = list((schema.get("metadata") or {}).get("supported_languages") or [])
    unknown = sorted(set(languages) - LANGUAGE_SUFFIXES.keys())
    if unknown:
        msg = f"archetype {archetype!r} names unknown languages {unknown}"
        raise ValueError(msg)
    return languages


def covers(languages: list[str], path: Path) -> bool:
    """Whether `path` is in one of `languages`; no languages covers any file."""
    suffix = path.suffix.lower()
    return not languages or any(suffix in LANGUAGE_SUFFIXES[name] for name in languages)


def _load(name: str, project_path: Path | None) -> ValidationPipeline:
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

    return load_pipeline_yaml(name, project_dir=project_path)


def _inside(path: Path, root: Path) -> str:
    """`path` relative to `root`, as the sandboxed atoms take it; unchanged when it lies outside."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
