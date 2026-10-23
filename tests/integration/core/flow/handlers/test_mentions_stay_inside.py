# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file the model mentions reaches the prompt only when it lies inside the project.

Proves: TECH-075 FR-6, TECH-075 NFR-4

The real mention scanner → `_resolve_mentions` → the project boundary → the USER turns appended to
the review conversation. Real files and links; no mocks.

| Bucket | Case |
|---|---|
| Happy | an inside file the assistant names is appended with its text |
| Boundary | a link inside that points inside is appended once, as its target |
| Degradation | a named file that does not exist adds nothing |
| Hostile | an escaping link, `../` and an absolute outside path never put the outside text in the prompt |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.handlers.review import _inject_resolved_mentions
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.infrastructure.llm.models import Message, Role

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _prompt_after(project: Path, assistant_says: str) -> str:
    messages = [Message(role=Role.ASSISTANT, content=assistant_says)]
    context = RunContext(project_path=project, spec_path=project / "a_spec.md")
    _inject_resolved_mentions(messages, context)
    return "\n".join(m.content for m in messages[1:])


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "inside.py").write_text("INSIDE_TEXT = 1\n", encoding="utf-8")
    (root / "src" / "alias.py").symlink_to(root / "src" / "inside.py")
    (tmp_path / "secret.py").write_text("SECRET_TEXT = 1\n", encoding="utf-8")
    (root / "src" / "escape.py").symlink_to(tmp_path / "secret.py")
    return root


def test_an_inside_file_is_appended(project: Path) -> None:
    prompt = _prompt_after(project, "Please look at `src/inside.py`.")

    assert "INSIDE_TEXT" in prompt


def test_a_link_inside_is_appended_once(project: Path) -> None:
    prompt = _prompt_after(project, "See `src/alias.py` and `src/inside.py`.")

    assert prompt.count("INSIDE_TEXT") == 1


def test_a_missing_file_adds_nothing(project: Path) -> None:
    assert _prompt_after(project, "See `src/missing.py`.") == ""


@pytest.mark.parametrize("named", ["src/escape.py", "../secret.py", "{outside}"])
def test_an_outside_file_never_reaches_the_prompt(project: Path, named: str) -> None:
    named = named.format(outside=project.parent / "secret.py")

    prompt = _prompt_after(project, f"See `{named}` and `src/inside.py`.")

    assert "SECRET_TEXT" not in prompt
    assert "INSIDE_TEXT" in prompt
