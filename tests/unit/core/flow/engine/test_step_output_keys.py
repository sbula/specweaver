# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each handler output key the engine reads is named once, in `engine/step_outputs.py`.

Proves: TECH-082 FR-8

A key spelled by hand in the writer and again in the reader is two strings that must agree with
nothing forcing them to.

| Bucket | Case |
|---|---|
| Happy | the five names carry the wire values the stored runs already hold |
| Boundary | a key held in a name (`output[RESULTS]`) passes; three non-output uses are allowed by name |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | a dict key, a subscript, a `.get` argument and an `in` test are each found |
"""

from __future__ import annotations

import ast
from pathlib import Path

from specweaver.core.flow.engine import step_outputs

_SRC = Path(__file__).resolve().parents[5] / "src" / "specweaver"
_FLOW = _SRC / "core" / "flow"
_DECLARED = _FLOW / "engine" / "step_outputs.py"
#: Modules outside `core/flow` that read a step's output.
_OUTSIDE_READERS = (
    _SRC / "interfaces" / "api" / "v1" / "implement.py",
    _SRC / "workflows" / "implementation" / "interfaces" / "cli.py",
    _SRC / "workflows" / "drafting" / "interfaces" / "cli.py",
    _SRC / "assurance" / "standards" / "interfaces" / "cli.py",
)
_KEYS = frozenset({"plan", "plan_path", "results", "verdict", "files_touched"})
#: (file, function, literal) uses that are not step output keys.
_NOT_OUTPUT = frozenset(
    {
        ("display.py", "__call__", "verdict"),  # a `gate_result` event argument
        ("review.py", "_judge_conflicts", "verdict"),  # a `ReviewResult` field update
        ("drift.py", "execute", "plan_path"),  # a step param
        ("hydration.py", "hydrate_plan_context", "plan"),  # a `PlanContext` field update
    }
)


def _literal(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and node.value in _KEYS:
        return str(node.value)
    return None


def _uses(node: ast.AST) -> list[tuple[int, str]]:
    """The output-key literals `node` uses itself, as (line, key)."""
    if isinstance(node, ast.Dict):
        found = [_literal(k) for k in node.keys]
        return [(node.lineno, key) for key in found if key]
    if isinstance(node, ast.Subscript):
        key = _literal(node.slice)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        key = _literal(node.args[0]) if node.func.attr == "get" and node.args else None
    elif isinstance(node, ast.Compare) and isinstance(node.ops[0], (ast.In, ast.NotIn)):
        key = _literal(node.left)
    else:
        key = None
    return [(node.lineno, key)] if key else []


def _hand_spelled(path: Path) -> list[str]:
    """Each output key spelled as a literal in `path`, as `file:line key`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # expected: named, so an unreadable file cannot pass as clean
        return [f"{path}:unparsable"]
    owner: dict[int, str] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(fn):
                owner[id(inner)] = fn.name
    return [
        f"{path}:{line} {key}"
        for node in ast.walk(tree)
        for line, key in _uses(node)
        if (path.name, owner.get(id(node), ""), key) not in _NOT_OUTPUT
    ]


def test_the_names_carry_the_stored_wire_values() -> None:
    names = (
        step_outputs.PLAN,
        step_outputs.PLAN_PATH,
        step_outputs.RESULTS,
        step_outputs.VERDICT,
        step_outputs.FILES_TOUCHED,
    )

    assert names == ("plan", "plan_path", "results", "verdict", "files_touched")


def test_no_output_key_is_spelled_by_hand() -> None:
    files = sorted(f for f in _FLOW.rglob("*.py") if f != _DECLARED) + list(_OUTSIDE_READERS)

    assert all(f.is_file() for f in _OUTSIDE_READERS)
    assert [hit for f in files for hit in _hand_spelled(f)] == []


def test_a_key_held_in_a_name_passes(tmp_path: Path) -> None:
    f = tmp_path / "named.py"
    f.write_text("def r(output):\n    return output.get(RESULTS), {VERDICT: 1}, output[PLAN]\n")

    assert _hand_spelled(f) == []


def test_an_allowed_use_passes_only_in_its_own_function(tmp_path: Path) -> None:
    f = tmp_path / "drift.py"
    f.write_text(
        "def execute(step):\n    return step.params.get('plan_path')\n"
        "def other(output):\n    return output.get('plan_path')\n"
    )

    assert _hand_spelled(f) == [f"{f}:4 plan_path"]


def test_every_literal_form_is_found(tmp_path: Path) -> None:
    f = tmp_path / "spelled.py"
    f.write_text(
        "def w(output):\n"
        "    out = {'results': [], 'note': 1}\n"
        "    output['verdict']\n"
        "    output.get('plan_path')\n"
        "    'files_touched' in output\n"
    )

    assert sorted(_hand_spelled(f)) == [
        f"{f}:2 results",
        f"{f}:3 verdict",
        f"{f}:4 plan_path",
        f"{f}:5 files_touched",
    ]


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n")

    assert _hand_spelled(f) == [f"{f}:unparsable"]
