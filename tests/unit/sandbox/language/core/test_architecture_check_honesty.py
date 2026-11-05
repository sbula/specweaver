# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No architecture check may answer a question it never asked.

Proves: TECH-064 FR-2, TECH-064 FR-3

Three delivered paths returned `ArchitectureRunResult(violation_count=0, violations=[])` from a body
whose docstring said *"Deferred"*: the caller got the same object as from a clean check, and
`qa_runner/core/atom.py` turned it into `SUCCESS — "No architectural violations."`

Since TECH-082 one shared boundary check serves every language and no language runner answers the
question any more. So the guard asks the shared check: wherever it judges nothing, it says why in
`note`, and the atom passes that note on instead of a clean verdict.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.commons.qa import ArchitectureRunResult
from specweaver.sandbox.language.core.boundary_check import check_boundaries
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom


@pytest.mark.parametrize(
    ("files", "target"),
    [
        ({"tools/run.py": "import os\n"}, "tools/run.py"),
        (
            {"domain/context.yaml": "name: d\narchetype: x\n", "domain/notes.txt": "x"},
            "domain/notes.txt",
        ),
    ],
    ids=["no-manifest", "not-code"],
)
def test_a_check_that_judges_nothing_says_so(
    tmp_path: Path, files: dict[str, str], target: str
) -> None:
    for relative, text in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")

    result = check_boundaries(tmp_path, target)

    assert result.violation_count == 0
    assert result.note, "a zero with no note reads as a clean verdict"


class TestTheAtomSurfacesTheDecline:
    """The note has to reach the caller, or setting it changes nothing anyone sees.

    Proves: TECH-064 FR-3
    """

    def _run(self, note: str) -> object:
        def architecture(root: Path, target: str) -> ArchitectureRunResult:
            return ArchitectureRunResult(violation_count=0, violations=[], note=note)

        atom = QARunnerAtom(Path("."), runner=object(), architecture=architecture)  # type: ignore[arg-type]
        return atom._intent_run_architecture({"target": "src/a.py"})

    def test_a_declined_check_does_not_claim_a_clean_verdict(self) -> None:
        result = self._run("no context.yaml covers this file")

        assert "No architectural violations" not in result.message
        assert "did not run" in result.message

    def test_a_real_clean_verdict_still_reads_as_one(self) -> None:
        """The honest empty result must survive, or the fix just inverts the defect."""
        result = self._run("")

        assert result.message == "No architectural violations."

    def test_the_note_is_exported_for_a_machine_reader(self) -> None:
        """A pipeline step reads exports, not prose."""
        result = self._run("no context.yaml covers this file")

        assert result.exports["note"].startswith("no context.yaml")
