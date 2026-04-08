# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.llm.mention_scanner.models — ResolvedMention."""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.llm.mention_scanner.models import ResolvedMention


class TestClassify:
    """ResolvedMention.classify() determines kind from path."""

    @pytest.mark.parametrize(
        ("path_str", "expected"),
        [
            ("specs/auth_service_spec.md", "spec"),
            ("README.md", "spec"),
            ("docs/design.md", "spec"),
            ("src/models/user.py", "code"),
            ("src/specweaver/llm/adapter.py", "code"),
            ("tests/unit/test_scanner.py", "test"),
            ("tests/integration/test_flow.py", "test"),
            ("config.yaml", "config"),
            ("settings.yml", "config"),
            ("package.json", "config"),
            ("pyproject.toml", "config"),
            ("image.png", "other"),
            ("data.csv", "other"),
        ],
    )
    def test_classify(self, path_str: str, expected: str) -> None:
        assert ResolvedMention.classify(Path(path_str)) == expected


class TestResolvedMention:
    """ResolvedMention dataclass behavior."""

    def test_frozen(self) -> None:
        m = ResolvedMention(
            original="foo.py",
            resolved_path=Path("/abs/foo.py"),
            kind="code",
        )
        with pytest.raises(AttributeError):
            m.original = "bar.py"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ResolvedMention("x.py", Path("/a/x.py"), "code")
        b = ResolvedMention("x.py", Path("/a/x.py"), "code")
        assert a == b

    def test_hash(self) -> None:
        a = ResolvedMention("x.py", Path("/a/x.py"), "code")
        b = ResolvedMention("x.py", Path("/a/x.py"), "code")
        assert hash(a) == hash(b)
        assert len({a, b}) == 1
