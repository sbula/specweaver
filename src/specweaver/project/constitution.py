# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Constitution loader — find, validate, and generate CONSTITUTION.md.

A constitution is a read-only, human-authored markdown document that
defines non-negotiable project rules.  It is injected into every LLM
prompt via ``PromptBuilder.add_constitution()`` so that agents always
operate within the project's constraints.

Resolution order (walk-up):
    spec_path directory → walk up to project_path → nearest wins.

Size policy:
    - ``find_constitution()``: loads with WARNING if over limit (graceful)
    - ``check_constitution()``: returns errors if over limit (CI gate)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

# Re-export from sub-modules for backward compatibility
from specweaver.project._helpers import (
    CONSTITUTION_FILENAME,
    DEFAULT_MAX_CONSTITUTION_SIZE,
    ConstitutionInfo,
)
from specweaver.project._helpers import (
    build_standards_section as _build_standards_section,
)
from specweaver.project._helpers import (
    build_tech_stack_rows as _build_tech_stack_rows,
)
from specweaver.project._helpers import (
    load_constitution as _load_constitution,
)
from specweaver.project._helpers import (
    walk_up_dirs as _walk_up_dirs,
)
from specweaver.project._templates import STANDARDS_TEMPLATE as _STANDARDS_TEMPLATE
from specweaver.project._templates import STARTER_TEMPLATE as _STARTER_TEMPLATE

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "CONSTITUTION_FILENAME",
    "DEFAULT_MAX_CONSTITUTION_SIZE",
    "ConstitutionInfo",
    "check_constitution",
    "find_all_constitutions",
    "find_constitution",
    "generate_constitution",
    "generate_constitution_from_standards",
    "is_unmodified_starter",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_constitution(
    project_path: Path,
    spec_path: Path | None = None,
    *,
    max_size: int = DEFAULT_MAX_CONSTITUTION_SIZE,
) -> ConstitutionInfo | None:
    """Find and load the nearest ``CONSTITUTION.md``.

    Resolution order:
    1. Walk up from *spec_path*'s directory to *project_path*.
    2. The nearest ``CONSTITUTION.md`` wins (service overrides root).
    3. Returns ``None`` if no constitution exists anywhere.

    Size handling:
    - ``<= max_size``: loaded normally.
    - ``> max_size``: loaded with a WARNING logged (graceful at runtime).

    Args:
        project_path: Root directory of the target project.
        spec_path: Optional path to the spec being processed.  When
            provided, walk-up resolution starts from its parent directory.
        max_size: Maximum allowed size in bytes.  Default 5 KB.

    Returns:
        ``ConstitutionInfo`` or ``None`` if no constitution found.
    """
    # Build search directories: from spec_path upward to project_path
    search_dirs = _walk_up_dirs(project_path, spec_path)
    logger.debug(
        "find_constitution: searching %d directories from %s",
        len(search_dirs),
        spec_path or project_path,
    )

    for directory in search_dirs:
        candidate = directory / CONSTITUTION_FILENAME
        if candidate.is_file():
            is_override = directory != project_path
            info = _load_constitution(candidate, is_override=is_override, max_size=max_size)
            logger.info(
                "Constitution loaded: %s (%d bytes, override=%s)",
                info.path, info.size, info.is_override,
            )
            return info

    logger.debug("No constitution found in %s", project_path)
    return None


def find_all_constitutions(project_path: Path) -> list[ConstitutionInfo]:
    """Find all ``CONSTITUTION.md`` files in the project tree.

    Scans the project root and all immediate subdirectories (service-level).
    Used by ``sw constitution show`` (no ``--path`` flag) to list all
    constitutions in the project.

    Args:
        project_path: Root directory of the target project.

    Returns:
        List of ``ConstitutionInfo``, root first, then overrides sorted
        by path.
    """
    results: list[ConstitutionInfo] = []

    # Check root
    root_candidate = project_path / CONSTITUTION_FILENAME
    if root_candidate.is_file():
        info = _load_constitution(root_candidate, is_override=False)
        results.append(info)

    # Scan subdirectories (one level deep — service boundaries)
    if project_path.is_dir():
        for child in sorted(project_path.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                candidate = child / CONSTITUTION_FILENAME
                if candidate.is_file():
                    info = _load_constitution(candidate, is_override=True)
                    results.append(info)

    logger.info(
        "find_all_constitutions: found %d constitution(s) in %s",
        len(results), project_path,
    )
    return results


def check_constitution(
    path: Path,
    *,
    max_size: int = DEFAULT_MAX_CONSTITUTION_SIZE,
) -> list[str]:
    """Validate a constitution file.  Returns a list of error strings.

    Unlike ``find_constitution()`` which warns on oversize, this function
    **errors** — designed for ``sw constitution check`` as a CI gate.

    Args:
        path: Path to the constitution file.
        max_size: Maximum allowed size in bytes.

    Returns:
        Empty list if valid, otherwise list of error descriptions.
    """
    errors: list[str] = []

    if not path.exists():
        errors.append(f"Constitution not found: {path}")
        logger.debug("check_constitution: file not found: %s", path)
        return errors

    size = path.stat().st_size
    if size > max_size:
        errors.append(
            f"Constitution size ({size} bytes) exceeds limit "
            f"({max_size} bytes). Consider trimming — "
            f"project-level rules only, component details belong in specs.",
        )
        logger.debug(
            "check_constitution: %s exceeds limit (%d > %d)",
            path, size, max_size,
        )
    else:
        logger.debug(
            "check_constitution: %s OK (%d bytes, limit %d)",
            path, size, max_size,
        )

    return errors


def generate_constitution(project_path: Path, project_name: str) -> Path:
    """Generate a starter ``CONSTITUTION.md`` from the built-in template.

    Idempotent: does **not** overwrite an existing file.

    Args:
        project_path: Directory where the file will be created.
        project_name: Project name for template substitution.

    Returns:
        Path to the (existing or newly created) file.
    """
    target = project_path / CONSTITUTION_FILENAME

    if target.exists():
        logger.debug(
            "generate_constitution: %s already exists, skipping",
            target,
        )
        return target

    content = _STARTER_TEMPLATE.format(project_name=project_name)
    target.write_text(content, encoding="utf-8")
    logger.info(
        "Generated starter constitution: %s (%d bytes)",
        target, len(content.encode("utf-8")),
    )

    return target


def is_unmodified_starter(path: Path) -> bool:
    """Check whether a constitution file is the unmodified starter template.

    Returns ``True`` if the file contains 5 or more ``TODO`` markers,
    indicating it was never customized by the user.  This heuristic
    avoids overwriting user-edited constitutions during bootstrap.

    Args:
        path: Path to the constitution file.

    Returns:
        ``True`` if the file looks like the unmodified starter template.
    """
    if not path.exists():
        return False

    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return False

    # The starter template has ~13 TODO markers.  If only a few remain,
    # the user has likely started editing.  5 is a safe threshold.
    min_todo_markers = 5
    return content.count("TODO") >= min_todo_markers


def generate_constitution_from_standards(
    project_path: Path,
    project_name: str,
    standards: list[dict[str, Any]],
    languages: list[str],
    *,
    force: bool = False,
) -> Path | None:
    """Generate a ``CONSTITUTION.md`` pre-filled from confirmed standards.

    Sections 1 (Identity), 2 (Tech Stack), and 4 (Coding Standards) are
    populated from the standards data.  Sections 3, 5-8 remain as TODO
    placeholders requiring human judgment.

    Overwrite policy:
    - If no file exists → create.
    - If file exists and is the unmodified starter template → auto-replace.
    - If file exists and user-edited → skip (unless *force* is True).

    Args:
        project_path: Directory where the file will be created.
        project_name: Project name for template substitution.
        standards: List of standard dicts from DB (keys: scope, language,
            category, data, confidence, confirmed_by).
        languages: List of detected language names (e.g. ``["python", "typescript"]``).
        force: If True, overwrite even user-edited constitutions.

    Returns:
        Path to the created/updated file, or ``None`` if skipped.
    """
    target = project_path / CONSTITUTION_FILENAME

    if target.exists() and not force and not is_unmodified_starter(target):
        logger.info(
            "generate_constitution_from_standards: %s exists and is "
            "user-edited, skipping (use force=True to overwrite)",
            target,
        )
        return None

    # Build tech stack rows
    tech_rows = _build_tech_stack_rows(languages)

    # Build coding standards section
    standards_section = _build_standards_section(standards)

    # Build languages display
    languages_display = ", ".join(lang.capitalize() for lang in languages) if languages else "TODO"

    content = _STANDARDS_TEMPLATE.format(
        project_name=project_name,
        languages=languages_display,
        tech_stack_rows=tech_rows,
        coding_standards=standards_section,
    )

    target.write_text(content, encoding="utf-8")
    logger.info(
        "Generated standards-based constitution: %s (%d bytes, %d standards)",
        target, len(content.encode("utf-8")), len(standards),
    )

    return target
