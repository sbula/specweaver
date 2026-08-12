# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The lineage-tag half of an artifact write, which four handlers hand-rolled.

`TECH-016` §2. The six write sites are NOT one sequence — `draft.py` tags a file the drafter has
already written, `generation.py`/`decomposition_artifacts.py` tag content on its way to disk, and
`lint_fix.py` carries a *pre-existing* uuid through an LLM round-trip and must never mint one. So
what is shared is these two primitives plus the file-level convenience, not a single writer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.flow.handlers.artifact_identity import (
    derive_artifact_uuid,
    ensure_file_tagged,
    tag_content,
)
from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

if TYPE_CHECKING:
    from pathlib import Path

_UUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_TAGGED_YAML = f"# sw-artifact: {_UUID}\nkey: value\n"


# --- derive_artifact_uuid ---------------------------------------------------


def test_an_existing_uuid_survives_a_regeneration(tmp_path: Path) -> None:
    """The point of reading back: a regenerated artifact keeps ONE lineage identity."""
    path = tmp_path / "spec_plan.yaml"
    path.write_text(_TAGGED_YAML, encoding="utf-8")

    assert derive_artifact_uuid(path) == _UUID


def test_a_missing_file_gets_a_fresh_uuid(tmp_path: Path) -> None:
    minted = derive_artifact_uuid(tmp_path / "never_written.yaml")

    assert len(minted) == 36
    assert minted.count("-") == 4


def test_an_untagged_file_gets_a_fresh_uuid(tmp_path: Path) -> None:
    path = tmp_path / "spec_plan.yaml"
    path.write_text("key: value\n", encoding="utf-8")

    assert derive_artifact_uuid(path) != ""


def test_two_derivations_of_the_same_untagged_file_differ(tmp_path: Path) -> None:
    """Minting is not idempotent by itself — only the tag on disk makes identity stable.

    Pinned because it is the reason `ensure_file_tagged` writes rather than just returning.
    """
    path = tmp_path / "spec_plan.yaml"
    path.write_text("key: value\n", encoding="utf-8")

    assert derive_artifact_uuid(path) != derive_artifact_uuid(path)


def test_an_unreadable_file_does_not_take_the_step_down(tmp_path: Path) -> None:
    """A directory where a file was expected. Lineage must not be the thing that fails a write."""
    path = tmp_path / "a_directory.yaml"
    path.mkdir()

    assert len(derive_artifact_uuid(path)) == 36


# --- tag_content ------------------------------------------------------------


def test_the_tag_is_prepended_in_the_language_s_comment_syntax() -> None:
    assert tag_content("key: value\n", _UUID, "yaml") == _TAGGED_YAML


def test_a_language_with_no_comment_syntax_is_left_alone() -> None:
    """`wrap_artifact_tag` returns None for json, and corrupting the file is worse than no tag."""
    assert tag_content('{"a": 1}', _UUID, "json") == '{"a": 1}'


def test_content_that_already_carries_the_tag_is_not_tagged_twice() -> None:
    assert tag_content(_TAGGED_YAML, _UUID, "yaml") == _TAGGED_YAML


def test_content_carrying_a_different_uuid_is_left_alone() -> None:
    """Two tags in one file is a lineage fork. The one already on disk wins."""
    other = f"# sw-artifact: {'a' * 8}-1111-2222-3333-{'b' * 12}\nkey: value\n"

    assert tag_content(other, _UUID, "yaml") == other


# --- ensure_file_tagged -----------------------------------------------------


def test_an_untagged_file_is_tagged_in_place(tmp_path: Path) -> None:
    path = tmp_path / "spec.md"
    path.write_text("# Title\n", encoding="utf-8")

    returned = ensure_file_tagged(path, "markdown")

    assert extract_artifact_uuid(path.read_text(encoding="utf-8")) == returned
    assert path.read_text(encoding="utf-8").endswith("# Title\n")


def test_an_already_tagged_file_is_not_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "spec_plan.yaml"
    path.write_text(_TAGGED_YAML, encoding="utf-8")
    before = path.stat().st_mtime_ns

    assert ensure_file_tagged(path, "yaml") == _UUID
    assert path.read_text(encoding="utf-8") == _TAGGED_YAML
    assert path.stat().st_mtime_ns == before, "an already-tagged file must not be rewritten"


def test_a_missing_file_is_not_created(tmp_path: Path) -> None:
    """`draft.py`'s inline copy guarded on `.exists()` and its static-method twin did not.

    Unifying them has to pick one, so the choice is pinned here: mint an identity, write nothing.
    """
    path = tmp_path / "never_written.md"

    assert len(ensure_file_tagged(path, "markdown")) == 36
    assert not path.exists()


def test_a_language_with_no_comment_syntax_leaves_the_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    path.write_text('{"a": 1}', encoding="utf-8")

    ensure_file_tagged(path, "json")

    assert path.read_text(encoding="utf-8") == '{"a": 1}'
