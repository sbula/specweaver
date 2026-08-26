# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The `exposes:` list a generated `context.yaml` carries, pinned exactly.

Proves: B-SENS-03 NFR-5

**Why this is integration and not unit.** The claim spans three modules:
`list_symbols(visibility=["public"])` in `workspace/ast/parsers` → `extract_public_symbols` in
`workspace/analyzers` → `ContextInferrer` in `workspace/context` → a `context.yaml` on disk. A unit
test of the parser cannot make this claim, because the thing at risk is what the *chain* produces.
SF-01 rewrites the first link, and this is the only test that sees the last one move.

**Why it does not duplicate `test_scan_and_infer.py`.** That file already walks this seam, but
asserts with `in` and `not in`:

    assert "Record" in result.node.exposes
    assert "_internal_helper" not in result.node.exposes

Membership checks cannot notice a set *changing* — a name-mangled member arriving or leaving passes
either way. This file asserts the **exact** list, which is what a regression net needs.

It builds its own project under `tmp_path` rather than extending the shared `sample_project`
fixture, so nothing else in the suite shifts underneath.

**Green on its first run by design** — see `test_visibility_vocabulary.py` for why a
must-not-change requirement cannot be proved with a red, and which probes stand in for one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.context.inferrer import ContextInferrer

if TYPE_CHECKING:
    from pathlib import Path

#: Deliberately holds one of each shape SF-01 predicts a delta for: a dunder that is interface
#: (`__init__`), a dunder that is protocol (`__repr__`), a single-underscore internal, and a
#: name-mangled member that no outsider can legitimately reach.
_MODULE = '''"""Order handling."""


class Order:
    """An order."""

    def __init__(self, total: float) -> None:
        self.total = total

    def __repr__(self) -> str:
        return "Order"

    def submit(self) -> float:
        return self.total

    def _validate(self) -> bool:
        return True

    def __checksum(self) -> int:
        return 1


def place(total: float) -> Order:
    return Order(total)


def _round(value: float) -> float:
    return value
'''


def _infer(tmp_path: Path) -> list[str]:
    module = tmp_path / "orders"
    module.mkdir()
    (module / "handler.py").write_text(_MODULE, encoding="utf-8")

    result = ContextInferrer(AnalyzerFactory).infer_and_write(module)
    assert result.was_generated is True
    assert result.node is not None
    return list(result.node.exposes)


class TestTheExposesListIsExactlyThis:
    def test_the_generated_exposes_list(self, tmp_path: Path) -> None:
        """[Happy path] Measured 2026-08-26. Two entries here are the reason SF-01 exists.

        `Order.__checksum` is **gone** as of 2026-08-26. It used to be here: name-mangled, and in
        the list that says what this module exposes. `Order._validate` and `_round` were always
        correctly absent — the old filter simply stopped looking after one underscore.
        """
        assert _infer(tmp_path) == [
            "Order",
            "Order.__init__",
            "Order.__repr__",
            "Order.submit",
            "place",
        ]

    def test_the_name_mangled_member_is_no_longer_exposed(self, tmp_path: Path) -> None:
        """[Hostile] This read `in` until 2026-08-26 `[agreed 2026-08-26]`, and it was true.

        `__checksum` is name-mangled precisely so nothing outside the class can reach it, and it
        was in the list that tells the rest of the system what this module exposes. `__init__` and
        `__repr__` stay, because a dunder is interface rather than accident — one column apart in
        the source, and opposite answers.
        """
        exposed = _infer(tmp_path)
        assert "Order.__checksum" not in exposed
        assert "Order.__init__" in exposed

    def test_a_single_underscore_member_is_not_exposed(self, tmp_path: Path) -> None:
        """[Happy path] The control. Without it, a filter that dropped *everything* would satisfy
        the assertion above's mirror image and read as a fix."""
        exposed = _infer(tmp_path)
        assert "Order._validate" not in exposed
        assert "_round" not in exposed


class TestTheSeamDegrades:
    def test_a_directory_with_no_source_files_generates_nothing(self, tmp_path: Path) -> None:
        """[Graceful degradation] No analyzable file → no node, and no exception on the way."""
        empty = tmp_path / "empty"
        empty.mkdir()
        (empty / "README.txt").write_text("not source", encoding="utf-8")

        result = ContextInferrer(AnalyzerFactory).infer_and_write(empty)

        assert result.was_generated is False
        assert result.node is None

    def test_a_module_whose_symbols_are_all_internal_exposes_nothing(self, tmp_path: Path) -> None:
        """[Boundary] An empty `exposes:` is a legitimate answer, not a failure to infer."""
        module = tmp_path / "internals"
        module.mkdir()
        (module / "impl.py").write_text(
            '"""Internals."""\n\n\ndef _only() -> int:\n    return 1\n', encoding="utf-8"
        )

        result = ContextInferrer(AnalyzerFactory).infer_and_write(module)

        assert result.node is not None
        assert result.node.exposes == []
