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
from typing import TYPE_CHECKING, Any

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


def _build_tech_stack_rows(languages: list[str]) -> str:
    """Build markdown table rows for the Tech Stack section."""
    if not languages:
        return "| Language | TODO | TODO | TODO |"

    lang_info = {
        "python": ("Python", "3.11+", "Primary language"),
        "javascript": ("JavaScript", "ES2022+", "Frontend / Node.js"),
        "typescript": ("TypeScript", "5.x+", "Type-safe JavaScript"),
    }

    rows: list[str] = []
    for lang in languages:
        info = lang_info.get(lang.lower(), (lang.capitalize(), "TODO", "TODO"))
        rows.append(f"| Language | {info[0]} | {info[1]} | {info[2]} |")

    return "\n".join(rows)


def _build_standards_section(standards: list[dict[str, Any]]) -> str:
    """Build markdown bullet list from confirmed standards."""
    import json

    if not standards:
        return (
            "- TODO: Naming conventions\n"
            "- TODO: Error handling patterns\n"
            "- TODO: Documentation requirements"
        )

    lines: list[str] = []
    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = {}
    for s in standards:
        cat = s.get("category", "unknown")
        by_category.setdefault(cat, []).append(s)

    category_labels = {
        "naming": "Naming Conventions",
        "error_handling": "Error Handling",
        "type_hints": "Type Annotations",
        "docstrings": "Documentation Style",
        "import_patterns": "Import Organization",
        "test_patterns": "Testing Conventions",
        "async_patterns": "Async Patterns",
        "jsdoc": "JSDoc Documentation",
        "tsdoc": "TSDoc Documentation",
    }

    for category, items in sorted(by_category.items()):
        label = category_labels.get(category, category.replace("_", " ").title())
        lines.append(f"### {label}")
        lines.append("")
        for item in items:
            data = json.loads(item["data"]) if isinstance(item["data"], str) else item["data"]
            scope = item.get("scope", ".")
            lang = item.get("language", "unknown")
            conf = item.get("confidence", 0.0)
            prefix = f"[{scope}/{lang}]" if scope != "." else f"[{lang}]"
            lines.append(f"**{prefix}** (confidence: {conf:.0%})")
            for k, v in data.items():
                lines.append(f"- {k.replace('_', ' ').title()}: `{v}`")
            lines.append("")

    return "\n".join(lines).rstrip()


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


# ---------------------------------------------------------------------------
# Standards-enriched template (sections 1, 2, 4 pre-filled)
# ---------------------------------------------------------------------------

_STANDARDS_TEMPLATE = """\
# {project_name} — Constitution

> **Status**: ACTIVE
> **Owner**: TODO
> **Rule**: This file is READ-ONLY for agents. Only the owner may modify it.
> **Last Updated**: TODO
> **Generated from**: Auto-discovered coding standards (review and customize!)

---

## 1. Identity

**Project**: {project_name}
**Languages**: {languages}
**One-Line Purpose**: TODO: What this project does, in one sentence.
**Domain**: TODO: Industry/domain
**Target Users**: TODO: Who uses this

## 2. Tech Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
{tech_stack_rows}
| Framework | TODO | TODO | TODO |
| Database | TODO | TODO | TODO |
| Testing | TODO | TODO | TODO |

**Rule**: Agents MUST NOT introduce technologies not listed here without HITL approval.

## 3. Architecture Principles (Non-Negotiable)

1. TODO: First principle
2. TODO: Second principle

## 4. Coding Standards (Auto-Discovered)

{coding_standards}

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
