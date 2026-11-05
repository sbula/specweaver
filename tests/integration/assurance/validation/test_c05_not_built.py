# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C05 never says "all imports follow the rules" about a Kotlin or Rust file it did not judge.

Proves: TECH-087 FR-5
Proves: TECH-082 FR-16

Before TECH-087 the Kotlin and Rust runners returned zero violations and C05 passed; TECH-087 made
C05 say SKIP instead. Since TECH-082 both languages are judged by the shared boundary check. FR-5's
promise still holds where nothing is judged: a file no `context.yaml` covers is SKIP, never PASS.

| Bucket | Case |
|---|---|
| Happy | a Kotlin or Rust import the folder's rule forbids fails C05 |
| Boundary | the same file with no manifest above it is SKIP, naming why |
| Degradation | — (the real atom and hydrator run; no tool is needed) |
| Hostile | — (fixed project files) |
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

pytestmark = pytest.mark.integration

#: language: (files, the file to check); `app/domain` forbids `app/infra` where a manifest exists.
PROJECTS = {
    "kotlin": (
        {
            "src/main/kotlin/app/infra/Db.kt": "package app.infra\nclass Db\n",
            "src/main/kotlin/app/domain/Svc.kt": "package app.domain\nimport app.infra.Db\nclass Svc\n",
        },
        "src/main/kotlin/app/domain/Svc.kt",
        "src/main/kotlin/app",
    ),
    "rust": (
        {
            "Cargo.toml": "[package]\nname = 'app'\n",
            "src/main.rs": "mod domain;\nmod infra;\n",
            "src/infra/mod.rs": "pub struct Db;\n",
            "src/domain/mod.rs": "use crate::infra::Db;\n",
        },
        "src/domain/mod.rs",
        "src",
    ),
}


def _c05(root: Path, language: str, manifest: bool) -> object:
    files, target, base = PROJECTS[language]
    if manifest:
        files = {
            **files,
            f"{base}/domain/context.yaml": f"name: domain\narchetype: pure-logic\nforbids: [{base}/infra]\n",
        }
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    code = root / target
    rule = ImportDirectionRule()
    rule.context = {
        "qa_architecture_result": _hydrate_architecture(
            qa_atom(cwd=root, language=language), code, root, None
        )
    }
    return rule.check(code.read_text(encoding="utf-8"), spec_path=code)


@pytest.mark.parametrize("language", sorted(PROJECTS))
def test_a_forbidden_import_fails(tmp_path: Path, language: str) -> None:
    assert _c05(tmp_path, language, manifest=True).status == Status.FAIL


@pytest.mark.parametrize("language", sorted(PROJECTS))
def test_a_file_no_manifest_covers_is_skip_never_pass(tmp_path: Path, language: str) -> None:
    result = _c05(tmp_path, language, manifest=False)

    assert result.status == Status.SKIP
    assert "no context.yaml covers this file" in result.message
    assert result.findings == []
