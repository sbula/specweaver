# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The arbiter's verdict model, prompt, model call and text guards live in `workflows/arbitration`,
and that module neither runs the sandbox nor reaches back into the flow engine.

Proves: TECH-082 FR-5, TECH-082 NFR-2

The handler imports these names to use them, so a name check on `arbiter.py` would always pass;
the scan looks for definitions instead.

| Bucket | Case |
|---|---|
| Happy | the new home holds the moved names; `arbiter.py` defines none of them; the new module imports no `sandbox` and no `core.flow` |
| Boundary | a re-export `X = verdict.X` counts as a definition; an import does not |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | an aliased `import specweaver.core.flow as f` is found |
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

_SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"
_HOME = _SRC / "workflows" / "arbitration"
_HANDLER = _SRC / "core" / "flow" / "handlers" / "arbiter.py"
_BARRED = ("specweaver.sandbox", "specweaver.core.flow")
_MOVED = (
    "ArbitrateVerdict",
    "ArbitrateResult",
    "ARBITRATE_INSTRUCTIONS",
    "UnreadableVerdictError",
    "arbitrate",
    "evidence_text",
    "SCENARIO_VOCABULARY",
    "guard_coding_feedback",
    "scenario_safe",
    "code_trace",
    "with_trace",
)
_OLD_NAMES = (*_MOVED, "_guard_coding_feedback", "_with_trace")


def _tree(path: Path) -> ast.Module | str:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # expected: named, so an unreadable file cannot pass as clean
        return f"{path}:unparsable"


def _defined(path: Path, names: tuple[str, ...]) -> list[str]:
    """Each top-level class, function or assignment in `path` that defines one of `names`."""
    tree = _tree(path)
    if isinstance(tree, str):
        return [tree]
    found = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            targets = [node.name]
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        else:
            continue
        found += [n for n in targets if n in names]
    return found


def _barred_imports(path: Path) -> list[str]:
    tree = _tree(path)
    if isinstance(tree, str):
        return [tree]
    found = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        if any(n == b or n.startswith(b + ".") for n in names for b in _BARRED):
            found.append(f"{path}:{node.lineno}")
    return found


def test_the_new_home_holds_the_moved_names() -> None:
    verdict = importlib.import_module("specweaver.workflows.arbitration.verdict")

    assert [n for n in _MOVED if not hasattr(verdict, n)] == []


def test_the_handler_defines_none_of_them() -> None:
    assert _defined(_HANDLER, _OLD_NAMES) == []


def test_the_new_module_imports_no_sandbox_and_no_flow() -> None:
    files = sorted(_HOME.glob("*.py"))

    assert files
    assert [hit for f in files for hit in _barred_imports(f)] == []


def test_a_re_export_counts_and_an_import_does_not(tmp_path: Path) -> None:
    f = tmp_path / "h.py"
    f.write_text(
        "from x.verdict import arbitrate\nimport x.verdict as v\nscenario_safe = v.scenario_safe\n",
        encoding="utf-8",
    )

    assert _defined(f, _OLD_NAMES) == ["scenario_safe"]


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n", encoding="utf-8")

    assert _defined(f, _OLD_NAMES) == [f"{f}:unparsable"]
    assert _barred_imports(f) == [f"{f}:unparsable"]


def test_an_aliased_flow_import_is_found(tmp_path: Path) -> None:
    f = tmp_path / "alias.py"
    f.write_text("def run():\n    import specweaver.core.flow as f\n", encoding="utf-8")

    assert _barred_imports(f) == [f"{f}:2"]
