# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A configured boundary tool the host does not have makes C05 WARN, never PASS.

Proves: TECH-082 FR-20

The real atom, hydrator and extras run with a PATH that holds none of the tools. A TypeScript
project configures dependency-cruiser and a Go project configures go-arch-lint; the shared rule
finds nothing, so only the missing tool decides between PASS and WARN `[agreed 2026-11-05]`.

| Bucket | Case |
|---|---|
| Happy | — (the tools are not installed here; their output is read in `test_boundary_extras.py`) |
| Boundary | the shared verdict is clean, and C05 still WARNs, naming the tool |
| Degradation | dependency-cruiser and go-arch-lint not on the PATH → "not installed" |
| Hostile | — (fixed project files) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.orchestration.validation_hydrator import _hydrate_architecture
from specweaver.assurance.validation.rules.code.c05_import_direction import ImportDirectionRule
from specweaver.commons.project_profile import GENERATED_LANGUAGES
from specweaver.sandbox.language.core.runner_factory import architecture_atom, qa_atom

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

#: language: (tool, files, the file to check)
PROJECTS = {
    "typescript": (
        "dependency-cruiser",
        {
            ".dependency-cruiser.cjs": "module.exports = {};\n",
            "app/svc.ts": "import x from 'lodash';\n",
        },
        "app/svc.ts",
    ),
    "go": (
        "go-arch-lint",
        {
            ".go-arch-lint.yml": "version: 3\n",
            "go.mod": "module example.com/app\n",
            "app/svc.go": 'package app\nimport "fmt"\n',
        },
        "app/svc.go",
    ),
}


@pytest.mark.parametrize("language", sorted(PROJECTS))
def test_a_configured_tool_missing_from_the_path_is_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    tool, files, target = PROJECTS[language]
    project = tmp_path / "project"
    files = {**files, "app/context.yaml": "name: app\narchetype: pure-logic\n"}
    for relative, text in files.items():
        (project / relative).parent.mkdir(parents=True, exist_ok=True)
        (project / relative).write_text(text, encoding="utf-8")
    empty = tmp_path / "bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    code = project / target
    rule = ImportDirectionRule()
    rule.context = {
        "qa_architecture_result": _hydrate_architecture(
            # Go has no QA runner, only the boundary check every language shares (TECH-079 FR-14).
            qa_atom(cwd=project, language=language)
            if language in GENERATED_LANGUAGES
            else architecture_atom(project),
            code,
            project,
            None,
        )
    }

    result = rule.check(code.read_text(encoding="utf-8"), spec_path=code)

    assert result.status == Status.WARN, result.message
    assert f"{tool} is configured but did not run: {tool} is configured but not installed" in (
        result.message
    )
