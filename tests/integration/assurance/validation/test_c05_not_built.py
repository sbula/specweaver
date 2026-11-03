# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C05 says SKIPPED, not "all imports follow layering rules", where no architecture check exists.

Proves: TECH-087 FR-5

Path P-2 of the design: the real QA atom runs the real Kotlin or Rust runner, the flow hydrator
serialises its result, and C05 reads it. Those runners return a `note` and no verdict; before
TECH-087 C05 read only the zero violation count and passed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.orchestration.validation_hydrator import _hydrate_architecture
from specweaver.assurance.validation.rules.code.c05_import_direction import ImportDirectionRule
from specweaver.sandbox.language.core.runner_factory import qa_atom

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.parametrize(
    ("language", "code_file", "says"),
    [
        ("kotlin", "src/main/kotlin/App.kt", "Kotlin architecture checks are not implemented"),
        ("rust", "src/main.rs", "Rust architecture checks are not implemented"),
    ],
)
def test_c05_skips_a_language_with_no_architecture_check(
    tmp_path: Path, language: str, code_file: str, says: str
) -> None:
    code = tmp_path / code_file
    code.parent.mkdir(parents=True)
    code.write_text("fun main() {}\n" if language == "kotlin" else "fn main() {}\n")
    atom = qa_atom(cwd=tmp_path, language=language)

    rule = ImportDirectionRule()
    rule.context = {"qa_architecture_result": _hydrate_architecture(atom, code, tmp_path, None)}
    result = rule.check(code.read_text(), spec_path=code)

    assert result.status == Status.SKIP
    assert says in result.message
    assert result.findings == []
