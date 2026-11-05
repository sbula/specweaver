# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C05 judges a code file by the shared boundary check, through the real QA atom and hydrator.

Proves: TECH-082 FR-16, FR-17, FR-19, FR-20
Proves: TECH-087 FR-5

The seam: the hydrator asks the QA atom's `run_architecture` intent, which runs the shared check,
and C05 reads the serialised result. Kotlin was "not implemented" before (TECH-087 FR-5 made C05
say SKIP instead of PASS); it is judged now. A file no `context.yaml` covers is still never PASS
`[agreed 2026-11-05]`.

| Bucket | Case |
|---|---|
| Happy | a clean file passes and says how many imports were not mapped |
| Boundary | a Kotlin file is judged like a Python one |
| Degradation | a file no manifest covers is SKIP, naming why; tach configured but missing is WARN |
| Hostile | a forbidden import fails and the finding names the `widens` fix |
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

DOMAIN = "name: domain\narchetype: pure-logic\nforbids: [infra]\n"


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _c05(root: Path, relative: str, language: str = "python"):
    code = root / relative
    rule = ImportDirectionRule()
    atom = qa_atom(cwd=root, language=language)
    rule.context = {"qa_architecture_result": _hydrate_architecture(atom, code, root, None)}
    return rule.check(code.read_text(encoding="utf-8"), spec_path=code)


def test_a_forbidden_import_fails_and_names_the_fix(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {
            "domain/context.yaml": DOMAIN,
            "infra/__init__.py": "",
            "domain/core/svc.py": "from infra import db\n",
        },
    )

    result = _c05(tmp_path, "domain/core/svc.py")

    assert result.status == Status.FAIL
    assert any("widens" in f.message and "domain/core/svc.py" in f.message for f in result.findings)


def test_a_clean_file_passes_and_counts_what_it_did_not_map(tmp_path: Path) -> None:
    _write(
        tmp_path,
        {"domain/context.yaml": DOMAIN, "domain/core/svc.py": "import os\nimport json\n"},
    )

    result = _c05(tmp_path, "domain/core/svc.py")

    assert result.status == Status.PASS
    assert "2 imports not mapped to a project folder" in result.message


def test_a_kotlin_file_is_judged(tmp_path: Path) -> None:
    base = "src/main/kotlin/"
    _write(
        tmp_path,
        {
            f"{base}domain/context.yaml": f"name: domain\narchetype: pure-logic\nforbids: [{base}infra]\n",
            f"{base}infra/Db.kt": "package infra\nclass Db\n",
            f"{base}domain/core/Svc.kt": "package domain.core\nimport infra.Db\nclass Svc\n",
        },
    )

    result = _c05(tmp_path, f"{base}domain/core/Svc.kt", language="kotlin")

    assert result.status == Status.FAIL


def test_a_file_no_manifest_covers_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, {"tools/run.py": "import os\n"})

    result = _c05(tmp_path, "tools/run.py")

    assert result.status == Status.SKIP
    assert "no context.yaml covers this file" in result.message


def test_a_configured_tool_that_did_not_run_is_warn_never_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean verdict with a configured tool missing reads as WARN `[agreed 2026-11-05]`."""
    from specweaver.sandbox.language.core import boundary_extras

    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: None)
    _write(
        tmp_path,
        {
            "tach.toml": "exact = true\n",
            "domain/context.yaml": DOMAIN,
            "domain/core/svc.py": "import os\n",
        },
    )

    result = _c05(tmp_path, "domain/core/svc.py")

    assert result.status == Status.WARN
    assert "tach is configured but did not run" in result.message
