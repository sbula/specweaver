# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Artifact identity on disk: minting a uuid, reading one back, and putting the tag at the top.

Proves: B-SENS-01 FR-2

Cited under `specweaver-dev` §3.2c, from `INT-US-15-SF01-MIG`. Mutant: `wrap_artifact_tag` returning
`None` for Python, so nothing is ever injected — 15 fail across three tiers, the widest blast radius
in this migration.

That breadth is the honest measure of FR-2's "every generated file": the tag is applied at four write
sites (drafting, generation, decomposition artifacts, lint-fix) and read back at more, so removing it
is visible almost everywhere. A capability whose mutant kills one test is narrow; this one is load-
bearing.

`TECH-016` §2 unified this: seven handler sites hand-rolled the event tail and four hand-rolled the
identity half.

The never-raises contract is the load-bearing part and had **no test at all** before this file —
`log_decomposition_lineage` carried it in a docstring, written after a real CB-1 failure
(2026-07-26), and nothing proved it. `lint_fix.py` did not even carry the `None` guard, which is
`TECH-036`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.commons.lineage import extract_artifact_uuid
from specweaver.core.flow.handlers.artifact_lineage import (
    derive_artifact_uuid,
    ensure_file_tagged,
    log_artifact_lineage,
    tag_content,
)

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


# --- log_artifact_lineage ---------------------------------------------------


def _context(db: Any, run_id: str | None = "run-7") -> Any:
    return SimpleNamespace(db=db, run=SimpleNamespace(run_id=run_id))


def _database(repo: Any) -> Any:
    """A stand-in for `Database`, whose `async_session_scope` is an async context manager."""

    @asynccontextmanager
    async def scope() -> Any:
        yield object()

    del repo
    return SimpleNamespace(async_session_scope=scope)


async def test_no_database_configured_is_a_silent_no_op() -> None:
    """`RunContext.db` defaults to None. This is the guard `lint_fix.py` was missing (TECH-036)."""
    with patch("specweaver.core.flow.store.FlowRepository") as repo_class:
        await log_artifact_lineage(_context(None), _UUID, "drafted_spec")

    repo_class.assert_not_called()


async def test_the_event_is_recorded_against_the_run() -> None:
    repo = AsyncMock()
    with patch("specweaver.core.flow.store.FlowRepository", return_value=repo):
        await log_artifact_lineage(
            _context(_database(repo)),
            _UUID,
            "generated_code",
            parent_id="parent-1",
            model_id="gemini-3-flash-preview",
        )

    repo.log_artifact_event.assert_awaited_once_with(
        artifact_id=_UUID,
        parent_id="parent-1",
        run_id="run-7",
        event_type="generated_code",
        model_id="gemini-3-flash-preview",
    )


async def test_a_run_with_no_id_still_records_an_event() -> None:
    """Every hand-rolled copy used `or "pipeline_run"`; unifying must not drop it."""
    repo = AsyncMock()
    with patch("specweaver.core.flow.store.FlowRepository", return_value=repo):
        await log_artifact_lineage(_context(_database(repo), run_id=None), _UUID, "lint_fixed")

    assert repo.log_artifact_event.await_args.kwargs["run_id"] == "pipeline_run"


async def test_the_defaults_match_what_the_call_sites_passed() -> None:
    repo = AsyncMock()
    with patch("specweaver.core.flow.store.FlowRepository", return_value=repo):
        await log_artifact_lineage(_context(_database(repo)), _UUID, "generated_decomposition")

    kwargs = repo.log_artifact_event.await_args.kwargs
    assert kwargs["parent_id"] is None
    assert kwargs["model_id"] == "unknown"


async def test_a_repository_failure_never_reaches_the_caller() -> None:
    """The whole contract. The artifact is already on disk and paid for with an LLM call.

    Letting this propagate hands it to `execute`'s `except Exception`, which returns ERROR with no
    output — discarding work that succeeded. Documented on `log_decomposition_lineage` since
    2026-07-26 and proven by nothing until now.
    """
    repo = AsyncMock()
    repo.log_artifact_event.side_effect = RuntimeError("no such table: artifact_events")

    with patch("specweaver.core.flow.store.FlowRepository", return_value=repo):
        await log_artifact_lineage(_context(_database(repo)), _UUID, "drafted_spec")


async def test_a_session_failure_never_reaches_the_caller() -> None:
    """The failure can also be in opening the session, not only in the write."""

    class _Exploding:
        def async_session_scope(self) -> Any:
            msg = "database is locked"
            raise OSError(msg)

    await log_artifact_lineage(_context(_Exploding()), _UUID, "drafted_spec")


async def test_a_database_that_is_not_a_database_never_reaches_the_caller() -> None:
    """Precisely `TECH-036`'s shape: whatever `context.db` holds, this must not fail the step."""
    await log_artifact_lineage(_context(object()), _UUID, "lint_fixed")


@pytest.mark.parametrize(
    "event_type",
    [
        "drafted_spec",
        "drafted_feature_spec",
        "generated_code",
        "generated_tests",
        "generated_plan",
        "generated_decomposition",
        "lint_fixed",
    ],
)
async def test_every_migrated_event_type_still_reaches_the_repository(event_type: str) -> None:
    """The seven call sites this replaces, named so a dropped migration is visible."""
    repo = AsyncMock()
    with patch("specweaver.core.flow.store.FlowRepository", return_value=repo):
        await log_artifact_lineage(_context(_database(repo)), _UUID, event_type)

    assert repo.log_artifact_event.await_args.kwargs["event_type"] == event_type
