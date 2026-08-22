# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the builder imports at module level is what its `context.yaml` says it may import.

Proves: TECH-068 AD-3

`AD-3` was approved on 2026-08-21 and never executed. Nothing noticed for the whole ticket, and the
reason is exactly why the decision was needed: **`allowed_imports` is read by nothing.** `tach`
works from `tach.toml`, which already permits the crossing; the archetype rule lives only in
`context.yaml`, and `grep` says no script and no test has ever opened that key.

So the declaration was documentation about itself. `SF-02` shipped marked `Committed ✅` with "the
`AD-3` boundary declared" among its Outputs, and the boundary was not declared.

This is the guardrail that ships with the fix. It reads the module-level `specweaver.*` imports of
every module in the package and asserts each one is covered by a declared prefix.

**Module level only, deliberately.** The anti-pattern `AD-3` names is *hiding a dependency inline*,
and a test that also swept inline imports would silently bless them by making them declarable.
`build_target`'s inline `specweaver.assurance.graph.loader` is a real undeclared crossing; it is
NOT in `AD-3`'s scope, it stays inline, and it is recorded in Known Boundary Violations rather than
waved through here. Lifting it means adding `specweaver.assurance` to this package's allowed set,
which is an architectural claim nobody has made.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

PACKAGE = Path(__file__).resolve().parents[5] / "src" / "specweaver" / "graph" / "core" / "builder"


def _declared() -> list[str]:
    context = yaml.safe_load((PACKAGE / "context.yaml").read_text(encoding="utf-8"))
    return [str(entry) for entry in context.get("allowed_imports", [])]


def _module_level_specweaver_imports(source: Path) -> set[str]:
    """Every `specweaver.*` module imported outside any function or class body.

    Walks the whole tree and PRUNES declaration bodies, rather than reading `tree.body` and
    special-casing what may nest inside it. The first version did the latter and the red team
    found two shapes it silently missed: a plain `import specweaver.x` inside `if TYPE_CHECKING:`
    (only `ImportFrom` was read there), and a module-level `try: ... except ImportError:` fallback
    (not read at all). Both are module-level dependencies, neither is an inline import, and a
    guardrail with a hole in it is the exact defect this whole gate exists to find.

    A declaration body is where an INLINE import lives, and `AD-3` names hiding a dependency there
    as the anti-pattern — so descending into one would legitimise it.
    """
    found: set[str] = set()
    stack: list[ast.AST] = list(ast.parse(source.read_text(encoding="utf-8")).body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("specweaver"):
            found.add(node.module or "")
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("specweaver"))
        else:
            stack.extend(ast.iter_child_nodes(node))
    return found


def _undeclared(source: Path) -> set[str]:
    declared = _declared()
    own = "specweaver.graph.core.builder"
    return {
        module
        for module in _module_level_specweaver_imports(source)
        if not module.startswith(own)
        and not any(module == d or module.startswith(f"{d}.") for d in declared)
    }


def test_every_module_level_crossing_is_declared() -> None:
    """Happy path, and the claim `AD-3` makes: the file and the contract agree."""
    offenders = {
        source.name: sorted(_undeclared(source))
        for source in sorted(PACKAGE.glob("*.py"))
        if _undeclared(source)
    }
    assert offenders == {}, (
        f"module-level imports absent from builder/context.yaml allowed_imports: {offenders}"
    )


def test_the_adapters_crossing_ad_3_approved_is_actually_declared() -> None:
    """Boundary: the specific crossing `AD-3` was approved FOR, named rather than implied.

    The test above passes for a package that imports nothing at all. This one fails if the
    declaration is dropped while the import stays, which is the state `AD-3` found.
    """
    assert "specweaver.workspace.ast.adapters" in _declared()


def test_the_declaration_is_not_a_blanket() -> None:
    """Hostile: `specweaver` on its own would satisfy every assertion here and mean nothing."""
    assert "specweaver" not in _declared()
    assert not any(d.rstrip(".*") == "specweaver" for d in _declared())


def test_neither_evasion_path_hides_a_crossing(tmp_path: Path) -> None:
    """Hostile: the two shapes that slipped past the first version of the reader.

    A guardrail is only worth what it cannot be walked around. Both of these declare a real
    module-level dependency and neither is an inline import, so both must be seen.
    """
    source = tmp_path / "evasive.py"
    source.write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import specweaver.sneaky.one\n"
        "try:\n"
        "    from specweaver.sneaky.two import thing\n"
        "except ImportError:\n"
        "    thing = None\n",
        encoding="utf-8",
    )

    assert _module_level_specweaver_imports(source) == {
        "specweaver.sneaky.one",
        "specweaver.sneaky.two",
    }


def test_an_inline_import_is_still_not_counted(tmp_path: Path) -> None:
    """The control for the test above: widening the reader must not swallow the anti-pattern.

    If this passed by accident the guardrail would report every hidden import as declared-or-not
    rather than as hidden, and `AD-3`'s whole subject would become invisible again.
    """
    source = tmp_path / "inline.py"
    source.write_text(
        "def f():\n    from specweaver.hidden import thing\n    return thing\n"
        "class C:\n    def m(self):\n        import specweaver.also_hidden\n",
        encoding="utf-8",
    )

    assert _module_level_specweaver_imports(source) == set()


def test_the_reader_finds_something_to_check() -> None:
    """The subject-located guard: an empty sweep reports clean for a package that moved.

    Pattern 8 — an absence proof over a tree that does not exist is a proof of nothing. One test
    holds this so the assertions above do not each restate it.
    """
    sources = list(PACKAGE.glob("*.py"))
    assert sources, f"no builder sources found at {PACKAGE} — the layout moved"
    assert any(_module_level_specweaver_imports(s) for s in sources), (
        "no module-level specweaver import found at all — the reader is looking at the wrong thing"
    )
    assert _declared(), "context.yaml declares no allowed_imports — nothing is being checked"
