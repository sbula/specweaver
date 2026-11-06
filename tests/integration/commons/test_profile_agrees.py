# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The profile decision agrees with the one language table.

Proves: TECH-079 FR-3, TECH-079 FR-5

Real code files in `tmp_path`. Its second half compared the decision with the two old detectors;
they are gone (SF-02), and so is that half.

| Bucket | Case |
|---|---|
| Happy | a generatable language's ending is named |
| Boundary | every ending the table holds: a generatable language is named, any other refused by name |
| Degradation | — (pure decision over fixed folders) |
| Hostile | — (fixed folders; the hostile roots are in the unit tests) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.languages import LANGUAGE_SUFFIXES
from specweaver.commons.project_profile import (
    GENERATED_LANGUAGES,
    ProjectUndecidedError,
    decide_profile,
)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.commons.project_profile import ProjectProfile

pytestmark = pytest.mark.integration

_ENDINGS = [(lang, e) for lang, suffixes in LANGUAGE_SUFFIXES.items() for e in suffixes]


def _decide(root: Path) -> ProjectProfile:
    names = frozenset(p.name for p in root.iterdir() if p.is_file())
    return decide_profile(
        names,
        lambda name: (root / name).read_text(encoding="utf-8"),
        kotlin_sources=(root / "src/main/kotlin").is_dir(),
    )


@pytest.mark.parametrize(("language", "ending"), _ENDINGS)
def test_every_table_ending_is_decided_by_the_table(
    tmp_path: Path, language: str, ending: str
) -> None:
    code = "main" + ending
    (tmp_path / code).write_text("", encoding="utf-8")

    if language in GENERATED_LANGUAGES:
        assert _decide(tmp_path).language == language
    else:
        with pytest.raises(ProjectUndecidedError, match=rf"^{language} \({code}\) cannot"):
            _decide(tmp_path)
