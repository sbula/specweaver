# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A protected name is protected in any letter case.

Proves: TECH-072 FR-9

On a disk that ignores case (macOS, Windows), `.ENV/x` is `.env/x`. The file executor's protected
names and the merge's own rule (`README.md`, `docs/`, the root `doc_updates.md`) both compare
without case.

| Bucket | Case |
|---|---|
| Happy | an ordinary file is still written; the task's own file is still kept by the merge |
| Boundary | `doc_updates.md` in any case is still kept |
| Degradation | not applicable — a pure comparison |
| Hostile | `.ENV/x`, `Context.YAML`, `.Git/config`, `ReadMe.md`, `DOCS/guide.md` refused |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.doc_policy import DocPolicy
from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.security import write_verdict

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("path", [".ENV/x", "Context.YAML", ".Git/config", ".SpecWeaver/s.py"])
def test_a_protected_name_in_another_case_is_refused(tmp_path: Path, path: str) -> None:
    result = FileExecutor(tmp_path).write(path, "x")

    assert result.status == "error"
    assert not (tmp_path / path).exists()


def test_an_ordinary_file_is_still_written(tmp_path: Path) -> None:
    assert FileExecutor(tmp_path).write("src/envelope.py", "x").status == "success"


@pytest.mark.parametrize("path", ["ReadMe.md", "README.MD", "DOCS/guide.md", "Docs/x.md"])
def test_the_merge_rule_ignores_case(path: str) -> None:
    assert write_verdict(DocPolicy(), path, None, ["**"]) != "keep"


@pytest.mark.parametrize("path", ["Doc_Updates.md", "DOC_UPDATES.MD"])
def test_doc_updates_is_kept_in_any_case(path: str) -> None:
    assert write_verdict(DocPolicy(), path, None, []) == "keep"
