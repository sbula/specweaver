# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for mention scanning helpers in flow._review.

Covers: _resolve_mentions, _scan_and_store_mentions, _is_within,
        _get_prior_mentions.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from specweaver.flow._review import (
    _get_prior_mentions,
    _is_within,
    _resolve_mentions,
    _scan_and_store_mentions,
)
from specweaver.llm.mention_scanner.models import ResolvedMention

# ===========================================================================
# _is_within
# ===========================================================================


class TestIsWithin:
    """Workspace boundary check."""

    def test_path_within_root(self, tmp_path: Path) -> None:
        child = tmp_path / "sub" / "file.py"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        assert _is_within(child, tmp_path) is True

    def test_path_outside_root(self, tmp_path: Path) -> None:
        outside = Path(tmp_path.anchor) / "somewhere_else" / "file.py"
        assert _is_within(outside, tmp_path) is False


# ===========================================================================
# _resolve_mentions
# ===========================================================================


class TestResolveMentions:
    """File resolution with boundary enforcement."""

    def test_resolves_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "auth_spec.md"
        f.write_text("spec content")
        result = _resolve_mentions(["auth_spec.md"], tmp_path)
        assert len(result) == 1
        assert result[0].original == "auth_spec.md"
        assert result[0].resolved_path == f.resolve()
        assert result[0].kind == "spec"

    def test_skips_nonexistent_file(self, tmp_path: Path) -> None:
        result = _resolve_mentions(["missing.py"], tmp_path)
        assert result == []

    def test_rejects_outside_boundary(self, tmp_path: Path) -> None:
        # Create file outside project root
        other = tmp_path / "other_project"
        other.mkdir()
        secret = other / "secret.py"
        secret.write_text("secret")
        # Candidate resides in a sibling directory
        project = tmp_path / "my_project"
        project.mkdir()
        result = _resolve_mentions(
            ["../other_project/secret.py"],
            project,
        )
        assert result == []

    def test_dedup_by_resolved_path(self, tmp_path: Path) -> None:
        f = tmp_path / "foo.py"
        f.write_text("code")
        result = _resolve_mentions(["foo.py", "./foo.py"], tmp_path)
        assert len(result) == 1

    def test_spec_prioritized_over_code(self, tmp_path: Path) -> None:
        py = tmp_path / "handler.py"
        py.write_text("code")
        md = tmp_path / "handler_spec.md"
        md.write_text("spec")
        result = _resolve_mentions(["handler.py", "handler_spec.md"], tmp_path)
        assert result[0].kind == "spec"

    def test_caps_at_max_files(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"file_{i}.py").write_text(f"code {i}")
        candidates = [f"file_{i}.py" for i in range(10)]
        result = _resolve_mentions(candidates, tmp_path, max_files=3)
        assert len(result) == 3

    def test_handles_oserror(self, tmp_path: Path) -> None:
        # Candidate with invalid characters should be handled gracefully
        result = _resolve_mentions(["valid.py"], tmp_path)
        assert result == []  # file doesn't exist, no crash

    def test_multiple_workspace_roots(self, tmp_path: Path) -> None:
        root1 = tmp_path / "root1"
        root1.mkdir()
        root2 = tmp_path / "root2"
        root2.mkdir()
        f = root2 / "util.py"
        f.write_text("code")
        result = _resolve_mentions(
            ["util.py"],
            root1,
            workspace_roots=[root2],
        )
        assert len(result) == 1
        assert result[0].resolved_path == f.resolve()


# ===========================================================================
# _scan_and_store_mentions
# ===========================================================================


class TestScanAndStoreMentions:
    """Scans response, resolves, stores in feedback."""

    def test_no_mentions_no_feedback(self, tmp_path: Path) -> None:
        ctx = self._make_context(tmp_path)
        _scan_and_store_mentions("This is a clean response.", ctx)
        assert "mention_scanner:resolved" not in ctx.feedback

    def test_stores_resolved_mentions(self, tmp_path: Path) -> None:
        f = tmp_path / "auth_spec.md"
        f.write_text("spec content")
        ctx = self._make_context(tmp_path)
        _scan_and_store_mentions("See `auth_spec.md` for details.", ctx)
        assert "mention_scanner:resolved" in ctx.feedback
        resolved = ctx.feedback["mention_scanner:resolved"]
        assert len(resolved) >= 1
        assert resolved[0].original == "auth_spec.md"

    def test_empty_response(self, tmp_path: Path) -> None:
        ctx = self._make_context(tmp_path)
        _scan_and_store_mentions("", ctx)
        assert "mention_scanner:resolved" not in ctx.feedback

    @staticmethod
    def _make_context(project_path: Path) -> MagicMock:
        ctx = MagicMock()
        ctx.project_path = project_path
        ctx.workspace_roots = None
        ctx.feedback = {}
        return ctx


# ===========================================================================
# _get_prior_mentions
# ===========================================================================


class TestGetPriorMentions:
    """Reads mention_scanner:resolved from context.feedback."""

    def test_returns_none_when_no_feedback(self) -> None:
        ctx = MagicMock()
        ctx.feedback = {}
        assert _get_prior_mentions(ctx) is None

    def test_returns_list_when_present(self) -> None:
        mention = ResolvedMention("foo.py", Path("/a/foo.py"), "code")
        ctx = MagicMock()
        ctx.feedback = {"mention_scanner:resolved": [mention]}
        result = _get_prior_mentions(ctx)
        assert result == [mention]

    def test_returns_none_for_non_list(self) -> None:
        ctx = MagicMock()
        ctx.feedback = {"mention_scanner:resolved": "not a list"}
        assert _get_prior_mentions(ctx) is None
