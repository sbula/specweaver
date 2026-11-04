# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each `context.feedback` key is declared once, in `run_state/feedback.py`.

Proves: TECH-082 FR-12

A key written by hand elsewhere is a second place that must agree on its spelling. The arbiter takes
the side step names from the dual pipeline's side table, not literals.

| Bucket | Case |
|---|---|
| Happy | `core/flow` holds no literal feedback key outside `feedback.py`; the arbiter names no side |
| Boundary | a key held in a name (`context.feedback[step.name]`) passes |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | an f-string key, a `.get`/`.pop`/`.setdefault` literal and an `in` test are each found |
"""

from __future__ import annotations

import ast
from pathlib import Path

_FLOW = Path(__file__).resolve().parents[4] / "src" / "specweaver" / "core" / "flow"
_DECLARED = _FLOW / "run_state" / "feedback.py"
_SIDE_STEPS = {"generate_code", "generate_scenarios"}


def _is_feedback(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "feedback"


def _is_literal(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) or isinstance(
        node, ast.JoinedStr
    )


def _literal_keys(path: Path) -> list[str]:
    """Each literal used as a feedback key in `path`, as `file:line`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # expected: named, so an unreadable file cannot pass as clean
        return [f"{path}:unparsable"]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            hit = _is_feedback(node.value) and _is_literal(node.slice)
        elif isinstance(node, ast.Call):
            func = node.func
            hit = (
                isinstance(func, ast.Attribute)
                and func.attr in ("get", "pop", "setdefault")
                and _is_feedback(func.value)
                and bool(node.args)
                and _is_literal(node.args[0])
            )
        elif isinstance(node, ast.Compare):
            hit = (
                _is_literal(node.left)
                and isinstance(node.ops[0], (ast.In, ast.NotIn))
                and _is_feedback(node.comparators[0])
            )
        else:
            hit = False
        if hit:
            found.append(f"{path}:{node.lineno}")
    return found


def test_no_feedback_key_is_written_by_hand() -> None:
    files = sorted(f for f in _FLOW.rglob("*.py") if f != _DECLARED)

    assert files
    assert [hit for f in files for hit in _literal_keys(f)] == []


def test_the_arbiter_names_no_side_step() -> None:
    tree = ast.parse((_FLOW / "handlers" / "arbiter.py").read_text(encoding="utf-8"))

    literals = {
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }

    assert literals & _SIDE_STEPS == set()


def test_a_key_held_in_a_name_passes(tmp_path: Path) -> None:
    f = tmp_path / "named.py"
    f.write_text(
        "def run(context, step):\n"
        "    context.feedback[step.name] = 1\n"
        "    return context.feedback.pop(KEY, None)\n"
    )

    assert _literal_keys(f) == []


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n")

    assert _literal_keys(f) == [f"{f}:unparsable"]


def test_every_literal_form_is_found(tmp_path: Path) -> None:
    f = tmp_path / "literal.py"
    f.write_text(
        "def run(context, name):\n"
        "    context.feedback[f'{name}:x'] = 1\n"
        "    context.feedback.get('a')\n"
        "    context.feedback.pop('b', None)\n"
        "    context.feedback.setdefault('c', {})\n"
        "    return 'd' not in context.feedback\n"
    )

    assert _literal_keys(f) == [f"{f}:{line}" for line in (2, 3, 4, 5, 6)]
