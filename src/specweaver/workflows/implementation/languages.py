# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the generator tells the model in each language and framework — content, not code.

The text lives in `workflows/languages/<lang>.md` and `workflows/frameworks/<name>.md`; a project's
`.specweaver/languages/` or `.specweaver/frameworks/` file of the same name replaces it. A file has
front-matter lines (`name:`, and for a framework `languages:`) and one level-1 heading per section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_WORKFLOWS = Path(__file__).parent.parent
_LANGUAGES = frozenset({"python", "java", "kotlin", "typescript", "rust"})
_FRAMEWORK_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
_FRAMEWORK_SECTIONS = {"Code": "code", "Tests": "tests"}
_SECTIONS = {
    "Code": "code",
    "Tests": "tests",
    "Code role": "code_role",
    "Tests role": "tests_role",
    "Coder role": "coder_role",
}
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FIELD = re.compile(r"^(\w+):\s*(\S.*?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class LanguageGuide:
    """The display name, the code and tests instructions, and the three role lines."""

    name: str
    code: str
    tests: str
    code_role: str
    tests_role: str
    coder_role: str


def language_guide(language: str, project_dir: Path | None = None) -> LanguageGuide:
    """The guide for `language`, the project's own file first.

    Raises `ValueError` for a language outside the five, and for a file without its `name:` line or
    one of its sections, naming the file.
    """
    if language not in _LANGUAGES:
        msg = f"no generation guide for language {language!r}; known: {sorted(_LANGUAGES)}"
        raise ValueError(msg)
    path = _content(project_dir, "languages", language)
    front, sections = _parse(path, _SECTIONS)
    return LanguageGuide(name=front["name"], **sections)


@dataclass(frozen=True)
class FrameworkGuide:
    """The display name, the languages it is for, and its code idioms and test style."""

    name: str
    languages: tuple[str, ...]
    code: str
    tests: str


def framework_guide(name: str, project_dir: Path | None = None) -> FrameworkGuide | None:
    """The guide for framework `name`, the project's own file first; None when there is none.

    `name` often comes from a `context.yaml` archetype, so only a plain name is looked up.
    """
    if not _FRAMEWORK_NAME.fullmatch(name):
        return None
    path = _content(project_dir, "frameworks", name)
    if not path.is_file():
        return None
    front, sections = _parse(path, _FRAMEWORK_SECTIONS)
    languages = tuple(
        part.strip() for part in front.get("languages", "").split(",") if part.strip()
    )
    return FrameworkGuide(name=front["name"], languages=languages, **sections)


def _content(project_dir: Path | None, kind: str, name: str) -> Path:
    own = project_dir / ".specweaver" / kind / f"{name}.md" if project_dir else None
    return own if own is not None and own.is_file() else _WORKFLOWS / kind / f"{name}.md"


def _parse(path: Path, titles: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """The front-matter fields and the named sections; refused, naming the file, when either is
    incomplete."""
    text = path.read_text(encoding="utf-8")
    front = _FRONT.match(text)
    fields = dict(_FIELD.findall(front.group(1))) if front else {}
    if "name" not in fields or front is None:
        msg = f"{path}: the file starts with no `name:` front matter"
        raise ValueError(msg)
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text[front.end() :].splitlines():
        heading = line[2:].strip() if line.startswith("# ") else None
        if heading in titles:
            current = sections.setdefault(titles[heading], [])
        elif current is not None:
            current.append(line)
    missing = [title for title, key in titles.items() if key not in sections]
    if missing:
        msg = f"{path}: missing section(s) {', '.join(missing)}"
        raise ValueError(msg)
    return fields, {key: "\n".join(lines).strip() for key, lines in sections.items()}
