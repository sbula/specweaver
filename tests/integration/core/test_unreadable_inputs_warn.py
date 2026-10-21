# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An unreadable input that changes what the user gets is a warning, never silence.

Proves: D-FLOW-04 FR-8

Real files on disk; each case breaks one input and reads the result and the log.

| Bucket | Case |
|---|---|
| Happy | not applicable — a readable input is each function's own tests |
| Boundary | not applicable — the same fallback as before; only its trace is new |
| Degradation | a broken `context.yaml`, a corrupt review record, an unreadable test file or spec, no boundary |
| Hostile | not applicable — the inputs are the project's own files |
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_BROKEN_YAML = "archetype: [unclosed\n"


def _warned(caplog: pytest.LogCaptureFixture, *words: str) -> bool:
    return any(
        record.levelno == logging.WARNING and all(w in record.getMessage() for w in words)
        for record in caplog.records
    )


def test_a_broken_context_yaml_drops_its_dal_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.core.config.dal_resolver import DALResolver

    (tmp_path / "context.yaml").write_text(_BROKEN_YAML, encoding="utf-8")

    assert DALResolver(tmp_path).resolve(tmp_path / "x.py") is None
    assert _warned(caplog, "context.yaml", "DAL")


@pytest.mark.parametrize(
    ("call", "what"), [("resolve", "archetype"), ("resolve_plugins", "plugins")]
)
def test_a_broken_context_yaml_drops_its_archetype_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, call: str, what: str
) -> None:
    from specweaver.core.config.archetype_resolver import ArchetypeResolver

    (tmp_path / "context.yaml").write_text(_BROKEN_YAML, encoding="utf-8")

    assert not getattr(ArchetypeResolver(tmp_path), call)(tmp_path / "x.py")
    assert _warned(caplog, "context.yaml", what)


def test_a_run_reads_generic_from_a_broken_context_yaml_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.core.flow.handlers.run_context import RunContext

    (tmp_path / "context.yaml").write_text(_BROKEN_YAML, encoding="utf-8")
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "a_spec.md")

    assert context._read_archetype() == "generic"
    assert _warned(caplog, "archetype", "generic")


def test_a_corrupt_review_record_counts_no_spec_as_reviewed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.core.flow.handlers.reviewed_spec import _read

    record = tmp_path / "reviewed.json"
    record.write_text("{not json", encoding="utf-8")

    assert _read(record) == {}
    assert _warned(caplog, "reviewed.json", "reviewed")


def test_an_unreadable_test_file_is_left_out_of_acceptance(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.core.flow.handlers.acceptance import _requirements_of

    assert _requirements_of(tmp_path / "gone_test.py") == {}
    assert _warned(caplog, "gone_test.py", "left out")


def test_an_unreadable_spec_shows_no_coverage(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.core.flow.handlers.qa_targets import requirement_coverage_of
    from specweaver.core.flow.handlers.run_context import RunContext

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "gone_spec.md")

    assert requirement_coverage_of(context) == {}
    assert _warned(caplog, "coverage")


def test_a_reviewer_without_a_boundary_gets_no_tools_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from specweaver.core.flow.handlers.review import _build_tool_dispatcher

    context = SimpleNamespace(graph=None, project_path=None)
    adapter = SimpleNamespace(generate_with_tools=object())

    assert _build_tool_dispatcher(context, "reviewer", adapter) is None
    assert _warned(caplog, "no file tools")
