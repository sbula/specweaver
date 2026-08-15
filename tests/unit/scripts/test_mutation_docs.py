# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The guide's commands are the ones the CLI actually accepts.

Proves: TECH-049 FR-14

A guide naming a flag that does not exist is worse than no guide: it sends the reader to a command
that fails, at the one moment they were willing to follow instructions. This binds the two, so
renaming a flag breaks the documentation test rather than the reader's morning.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GUIDE = REPO_ROOT / "docs" / "dev_guides" / "writing_mutation_campaigns.md"
MUTATION = REPO_ROOT / "scripts" / "mutation.py"
CORPUS = REPO_ROOT / "scripts" / "_corpus.py"

#: Long options a script declares, read from its `add_argument` calls rather than by running it —
#: importing `mutation.py` builds sandboxes, which a documentation test has no business doing.
_OPTION = re.compile(r'add_argument\(\s*"(--[a-z-]+)"')


def _declared(script: Path) -> set[str]:
    return set(_OPTION.findall(script.read_text(encoding="utf-8")))


def _documented(text: str, script_name: str) -> set[str]:
    """Long options appearing on a line that invokes the named script."""
    found: set[str] = set()
    for line in text.splitlines():
        if script_name in line:
            found.update(re.findall(r"(--[a-z-]+)", line))
    return found


class TestMainFlagsAreDocumented:
    """Every flag the guide shows must exist."""

    def test_the_guide_exists(self) -> None:
        assert GUIDE.is_file(), f"the dev guide is missing: {GUIDE}"

    def test_every_mutation_flag_it_names_is_real(self) -> None:
        used = _documented(GUIDE.read_text(encoding="utf-8"), "mutation.py")
        assert used, "the guide should show at least one mutation.py invocation"
        assert used <= _declared(MUTATION), sorted(used - _declared(MUTATION))

    def test_every_corpus_flag_it_names_is_real(self) -> None:
        used = _documented(GUIDE.read_text(encoding="utf-8"), "_corpus.py")
        assert used <= _declared(CORPUS), sorted(used - _declared(CORPUS))

    def test_it_documents_the_gate_and_every_disposition(self) -> None:
        """A routine missing one disposition sends the reader to guess at it."""
        text = GUIDE.read_text(encoding="utf-8")
        assert "--gate" in text
        for disposition in ("real-gap", "equivalent", "will-fix", "stale-refreshed"):
            assert disposition in text, disposition

    @pytest.mark.parametrize("skill", ["specweaver-dev/SKILL.md", "specweaver-pre-commit/SKILL.md"])
    def test_the_skills_know_the_corpus_exists(self, skill: str) -> None:
        """Before this sub-feature, grep found zero mentions in any skill.

        The gate blocks work; a skill that never mentions it leaves the reader with a blocked
        session and no thread to pull.
        """
        for tree in (".claude", ".agents"):
            path = REPO_ROOT / tree / "skills" / skill
            text = path.read_text(encoding="utf-8")
            assert "mutation.py" in text or "_mutants.json" in text, path
