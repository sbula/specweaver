# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The guide for adding a language says how a QA method reports a check that did not run.

Proves: TECH-087 FR-19

The guide once told the next language to "map `run_complexity` to a static no-op violation array":
a bare zero, which every reader takes as clean. The user asked that this be documented where a new
language is added (2026-10-30).
"""

from __future__ import annotations

from pathlib import Path

_GUIDE = Path(__file__).resolve().parents[2] / "docs" / "dev_guides" / "language_support_guide.md"


def _text() -> str:
    assert _GUIDE.is_file(), _GUIDE
    return " ".join(_GUIDE.read_text(encoding="utf-8").split())


def test_the_guide_gives_the_rule_for_each_qa_method() -> None:
    text = _text()
    for needle in (
        "never a bare zero",
        "`failed_lint`",
        "`failed_complexity`",
        "`note`",
        "C05 skips",
        "timed out",
    ):
        assert needle in text, needle


def test_the_no_op_advice_is_gone() -> None:
    assert "no-op violation array" not in _text()
