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
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

CONSTITUTION_FILENAME = "CONSTITUTION.md"
DEFAULT_MAX_CONSTITUTION_SIZE = 5120  # 5 KB


@dataclass(frozen=True)
class ConstitutionInfo:
    """Result of loading a constitution.

    Attributes:
        content: Raw markdown content (BOM-stripped).
        path: Absolute path to the file.
        size: File size in bytes.
        is_override: True if this is not the root-level constitution
            (i.e. found in a subdirectory, overriding the root).
    """

    content: str
    path: Path
    size: int
    is_override: bool


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _walk_up_dirs(
    project_path: Path,
    spec_path: Path | None,
) -> list[Path]:
    """Build ordered list of directories to search for constitution.

    Starts at spec_path's parent, walks up to project_path (inclusive).
    Returns [project_path] if spec_path is None.
    """
    project_resolved = project_path.resolve()

    if spec_path is None:
        return [project_resolved]

    directories: list[Path] = []
    current = spec_path.resolve().parent

    while True:
        directories.append(current)
        if current == project_resolved:
            break
        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding project_path
            break
        # Don't walk above project_path
        if not str(current).startswith(str(project_resolved)):
            break
        current = parent

    # Ensure project_path is always in the list
    if project_resolved not in directories:
        directories.append(project_resolved)

    return directories


def _load_constitution(
    path: Path,
    *,
    is_override: bool,
    max_size: int = DEFAULT_MAX_CONSTITUTION_SIZE,
) -> ConstitutionInfo:
    """Load a constitution file with BOM stripping and size warning."""
    raw = path.read_text(encoding="utf-8-sig")  # auto-strips BOM

    # Strip BOM if present
    if raw.startswith("\ufeff"):
        raw = raw[1:]

    size = path.stat().st_size

    if size > max_size:
        logger.warning(
            "Constitution %s size (%d bytes) exceeds recommended limit "
            "(%d bytes). Consider trimming.",
            path,
            size,
            max_size,
        )

    return ConstitutionInfo(
        content=raw,
        path=path,
        size=size,
        is_override=is_override,
    )


# ---------------------------------------------------------------------------
# Starter template (~1.5 KB with TODO placeholders)
# ---------------------------------------------------------------------------

_STARTER_TEMPLATE = """\
# {project_name} — Constitution

> **Status**: ACTIVE
> **Owner**: TODO
> **Rule**: This file is READ-ONLY for agents. Only the owner may modify it.
> **Last Updated**: TODO

---

## 1. Identity

**Project**: {project_name}
**One-Line Purpose**: TODO: What this project does, in one sentence.
**Domain**: TODO: Industry/domain
**Target Users**: TODO: Who uses this

## 2. Tech Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | TODO | TODO | TODO |
| Framework | TODO | TODO | TODO |
| Database | TODO | TODO | TODO |
| Testing | TODO | TODO | TODO |

**Rule**: Agents MUST NOT introduce technologies not listed here without HITL approval.

## 3. Architecture Principles (Non-Negotiable)

1. TODO: First principle
2. TODO: Second principle

## 4. Coding Standards

- TODO: Naming conventions
- TODO: Error handling patterns
- TODO: Documentation requirements

**Rule**: These standards apply to ALL code, whether written by a human or an agent.

## 5. Security Invariants

- TODO: Input validation rules
- TODO: Secret management rules

## 6. Prohibited Actions

### Filesystem
- Never modify this Constitution without HITL instruction
- Never write secrets to tracked files

### Git
- Never `git push --force` to main/master

### Project-Specific
- TODO: Add project-specific prohibitions

## 7. Key Documents Index

| Document | Purpose | Path |
|----------|---------|------|
| Constitution | This file — non-negotiable rules | `CONSTITUTION.md` |
| TODO | TODO | TODO |

## 8. Agent Instructions

**Before starting ANY work, every agent MUST:**
1. Read this Constitution in full
2. Read the relevant Component Spec(s)
3. Verify that the planned work does not violate any section above

**If an agent encounters a conflict between a spec and this Constitution, the Constitution wins.**
"""
