# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the generator tells the model in each language — content, not code.

The text lives in `workflows/languages/<lang>.md`; a project's `.specweaver/languages/<lang>.md`
replaces it. A file has a `name:` front-matter line and one level-1 heading per section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SHIPPED_DIR = Path(__file__).parent.parent / "languages"
_LANGUAGES = frozenset({"python", "java", "kotlin", "typescript", "rust"})
_SECTIONS = {
    "Code": "code",
    "Tests": "tests",
    "Code role": "code_role",
    "Tests role": "tests_role",
    "Coder role": "coder_role",
}
_NAME = re.compile(r"\A---\s*\nname:\s*(\S.*?)\s*\n---\s*\n", re.DOTALL)


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
    own = project_dir / ".specweaver" / "languages" / f"{language}.md" if project_dir else None
    path = own if own is not None and own.is_file() else _SHIPPED_DIR / f"{language}.md"
    return _parse(path)


def _parse(path: Path) -> LanguageGuide:
    text = path.read_text(encoding="utf-8")
    named = _NAME.match(text)
    if named is None:
        msg = f"{path}: the file starts with no `name:` front matter"
        raise ValueError(msg)
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text[named.end() :].splitlines():
        heading = line[2:].strip() if line.startswith("# ") else None
        if heading in _SECTIONS:
            current = sections.setdefault(_SECTIONS[heading], [])
        elif current is not None:
            current.append(line)
    missing = [title for title, key in _SECTIONS.items() if key not in sections]
    if missing:
        msg = f"{path}: missing section(s) {', '.join(missing)}"
        raise ValueError(msg)
    return LanguageGuide(
        name=named.group(1), **{key: "\n".join(lines).strip() for key, lines in sections.items()}
    )
