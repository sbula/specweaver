# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The QA steps run the tools of the run's language, not whatever the manifests suggest.

Proves: D-INTL-08 FR-2

The run root sets `RunContext.language`; `lint_fix` and `run_tests` build their QA runner from it.
The runners are real; nothing is run.

| Bucket | Case |
|---|---|
| Happy | a run named `rust` gets the Rust runner in a folder that looks like Python |
| Boundary | a run with no language gets the detected one |
| Degradation | not applicable — the runner is only chosen, not run |
| Hostile | not applicable — the language is validated where it is read |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.run_context import IsolationPolicy, RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.rust.runner import RustRunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _context(root: Path, language: str | None) -> RunContext:
    (root / "pyproject.toml").write_text("[project]\nname='p'\n", encoding="utf-8")
    return RunContext(
        project_path=root,
        spec_path=root / "s_spec.md",
        isolation=IsolationPolicy(language=language),
    )


@pytest.mark.parametrize("handler", [LintFixHandler(), ValidateTestsHandler()])
def test_the_named_language_picks_the_runner(tmp_path: Path, handler: object) -> None:
    atom = handler._get_atom(_context(tmp_path, "rust"))  # type: ignore[attr-defined]

    assert isinstance(atom._runner, RustRunner)


def test_without_a_language_the_manifests_decide(tmp_path: Path) -> None:
    context = _context(tmp_path, None)
    (tmp_path / "pyproject.toml").unlink()
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")

    assert isinstance(LintFixHandler()._get_atom(context)._runner, JavaRunner)
