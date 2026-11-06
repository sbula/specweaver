# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which validation pipeline a file gets: its framework, else its folder's archetype.

Shared by the validate steps and `sw check`, so both judge a file by the same rules. A code file's
framework is `workspace.project.framework_for`'s answer, the one generation uses; a spec's is its
folder's `framework:` (the build file never picks a spec pipeline). An archetype's languages are
the `supported_languages` of its evaluator schema (`workflows/evaluators/frameworks/<name>.yaml`,
or the project's `.specweaver/evaluators/`); a schema naming none judges any language.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.commons.languages import LANGUAGE_SUFFIXES
from specweaver.commons.languages import language_of as _language_of

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.validation.pipeline import ValidationPipeline
    from specweaver.commons.project_profile import ProjectProfile

logger = logging.getLogger(__name__)

SPEC_DEFAULT = "validation_spec_default"
CODE_DEFAULT = "validation_code_default"


def archetype_of(path: Path, project_path: Path | None) -> str | None:
    """The archetype the nearest `context.yaml` above `path` declares."""
    from specweaver.core.config.archetype_resolver import ArchetypeResolver

    return ArchetypeResolver(project_path).resolve(path) if project_path else None


def spec_pipeline(
    spec_path: Path,
    project_path: Path | None,
    *,
    feature: bool = False,
    profile: str | None = None,
) -> tuple[ValidationPipeline, str | None]:
    """The framework's or archetype's spec pipeline, else the profile's, else the default; and
    the name it came from.

    A feature spec always gets the feature pipeline: an archetype bounds a component.
    """
    pipeline, key = own_pipeline("spec", spec_path, project_path)
    if feature:
        return _load("validation_spec_feature", project_path), key
    return pipeline or _profile_pipeline(profile, project_path), key


def _profile_pipeline(profile: str | None, project_path: Path | None) -> ValidationPipeline:
    """The profile's spec pipeline (`validation_spec_<profile>`), else the default."""
    if profile:
        from specweaver.core.config.profiles import profile_to_pipeline_name

        try:
            return _load(profile_to_pipeline_name(profile), project_path)
        except FileNotFoundError:
            logger.warning("Profile %r has no pipeline; using the default", profile)
    return _load(SPEC_DEFAULT, project_path)


def code_pipeline(
    code_path: Path, project_path: Path | None, profile: ProjectProfile | None = None
) -> tuple[ValidationPipeline, str | None]:
    """The framework's or archetype's code pipeline when it covers the file, else the default."""
    pipeline, key = own_pipeline("code", code_path, project_path, profile)
    if pipeline is None:
        return _load(CODE_DEFAULT, project_path), None
    return pipeline, key


def own_pipeline(
    level: str, path: Path, project_path: Path | None, profile: ProjectProfile | None = None
) -> tuple[ValidationPipeline | None, str | None]:
    """The pipeline the file's framework or archetype brings (`spec` or `code`), or None; and the
    name it came from.

    The framework comes first, then the archetype, so a project's own `validation_code_<role>`
    still applies. None when neither ships a pipeline for `level`, or the code file is not in its
    languages; the caller then keeps its own choice.
    """
    keys = _names(level, path, project_path, profile)
    code_path = path if level == "code" else None
    for key in keys:
        pipeline = _archetype_pipeline(level, key, project_path, code_path)
        if pipeline is not None:
            return pipeline, key
    return None, keys[0] if keys else None


def _names(
    level: str, path: Path, project_path: Path | None, profile: ProjectProfile | None
) -> list[str]:
    """The framework, then the archetype: the names whose pipelines may judge `path`."""
    if project_path is None:
        return []
    from specweaver.core.config.archetype_resolver import ArchetypeResolver
    from specweaver.workspace.project.frameworks import framework_for

    if level == "code":
        answer = framework_for(project_path, path, profile)
        framework = answer.key if answer else None
    else:
        framework = ArchetypeResolver(project_path).resolve_framework(path)
    names = (framework, archetype_of(path, project_path))
    return [name for name in dict.fromkeys(names) if name]


def language_of(path: Path) -> str:
    """The language a file's ending names; the bare ending when no language claims it."""
    return _language_of(path) or path.suffix.lower().lstrip(".") or path.name


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
    from specweaver.workspace.project.evaluator_schemas import load_evaluator_schemas

    cwd = project_path or path.parent
    atom = CodeStructureAtom(
        cwd=cwd,
        evaluator_schemas=load_evaluator_schemas(project_dir=project_path),
        active_archetype=archetype or "generic",
        parsers=parsers,
    )
    relative = relative_to_root(path, cwd)
    payload: dict[str, Any] = {}
    if relative is None:
        logger.warning("%s is outside the project %s; its structure is not read", path, cwd)
        for step in pipeline.steps:
            step.params["ast_payload"] = payload
        return
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
    from specweaver.workspace.project.evaluator_schemas import load_evaluator_schemas
    from specweaver.workspace.project.frameworks import languages_of as schema_languages

    schema = load_evaluator_schemas(project_dir=project_path).get(archetype) or {}
    return list(schema_languages(archetype, schema))


def covers(languages: list[str], path: Path) -> bool:
    """Whether `path` is in one of `languages`; no languages covers any file."""
    suffix = path.suffix.lower()
    return not languages or any(suffix in LANGUAGE_SUFFIXES[name] for name in languages)


def _load(name: str, project_path: Path | None) -> ValidationPipeline:
    from specweaver.assurance.validation.io.pipeline_loader import load_pipeline_yaml

    return load_pipeline_yaml(name, project_dir=project_path)


def relative_to_root(path: Path, root: Path) -> str | None:
    """`path` relative to `root`, as the sandboxed atoms take it; None when it lands outside."""
    from specweaver.assurance.validation.orchestration.project_paths import (
        ProjectPathError,
        project_file,
    )

    try:
        # `absolute()`, not `resolve()`: a relative path is read from the working folder, and the
        # boundary resolves links itself.
        inside = project_file(root, str(path.absolute()))
    except ProjectPathError:  # expected: outside the root; the caller warns and skips
        return None
    return inside.relative_to(root.resolve()).as_posix()
