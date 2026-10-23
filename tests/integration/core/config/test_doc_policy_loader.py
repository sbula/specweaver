# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's doc policy is read from its own `specweaver.toml` on disk.

Proves: C-EXEC-08 FR-1, NFR-1

| Bucket | Case |
|---|---|
| Happy | the `[docs]` rules of a project's file are loaded beside its `[llm]` section |
| Boundary | a project with no file, or no section, has an empty policy |
| Degradation | not applicable — a missing file is the boundary case |
| Hostile | a broken rule names the project's file and the line |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.project_settings import load_section
from specweaver.core.config.doc_policy import parse_doc_policy
from specweaver.core.config.settings_file import SettingsFileError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def test_a_project_s_rules_are_loaded(tmp_path: Path) -> None:
    (tmp_path / "specweaver.toml").write_text(
        '[llm]\nprivate_only = false\n\n[[docs.rule]]\npaths = ["docs/user_guides/**"]\naccess = "open"\n',
        encoding="utf-8",
    )

    policy = load_section(tmp_path, parse_doc_policy)

    assert [rule.access for rule in policy.rule] == ["open"]


def test_no_file_is_an_empty_policy(tmp_path: Path) -> None:
    assert load_section(tmp_path, parse_doc_policy).rule == []


def test_a_broken_rule_names_the_file_and_the_line(tmp_path: Path) -> None:
    path = tmp_path / "specweaver.toml"
    path.write_text('[[docs.rule]]\npaths = ["docs/**"]\naccess = "maybe"\n', encoding="utf-8")

    with pytest.raises(SettingsFileError) as caught:
        load_section(tmp_path, parse_doc_policy)

    assert (caught.value.source, caught.value.line) == (str(path), 3)
