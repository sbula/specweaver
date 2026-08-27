# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What "too big" means, measured the way cAST measures it.

Proves: B-SENS-03 FR-11

The budget counted every character, so **indentation decided where code was cut**. Deeply nested
Java and flat Python were judged by different standards for the same amount of code, and
reformatting a file moved its chunk boundaries without a line of it changing.

cAST (EMNLP 2025 Findings) measures *"chunk size by the number of non-whitespace characters rather
than by lines"*, for exactly that consistency across coding styles and languages. Adopted
`[agreed 2026-08-26]`.

**The honest consequence, stated rather than discovered later**: a non-whitespace budget leaves
*raw* chunk length unbounded, so deeply indented source produces physically larger chunks. cAST
accepts the same trade. A model with a hard input cap is `A-SENS-02`'s problem to clamp, and
`NFR-3` says so.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers


@pytest.fixture(scope="module")
def python_parser() -> object:
    for exts, parser in get_default_parsers().items():
        if ".py" in exts:
            return parser
    raise AssertionError("no Python parser registered")


def _body(statements: int, indent: int) -> str:
    """A function whose body is `statements` lines, each indented `indent` spaces."""
    pad = " " * indent
    # A realistic statement width. `x = 0` is three non-whitespace characters, so a fixture built
    # from it needs ~670 lines to reach a 2,000 budget -- and the guards below caught that the
    # first draft did not. The assertions are about the MEASURE, so the fixture has to be able to
    # cross the budget in the unit being measured.
    lines = "\n".join(f"{pad}some_variable_{n} = {n} + 1" for n in range(statements))
    return f"def wide():\n{lines}\n"


def _chunks(parser: object, code: str, max_chars: int) -> list[str]:
    # **Body layer only.** `FR-12` added a skeleton chunk per symbol, and `FR-17` binds the
    # body layer -- both halves -- because a skeleton is a description and a signature
    # concatenated rather than a slice of the file.
    return [
        c.text
        for c in chunk_source(
            code, path="m.py", parser=parser, language="python", max_chars=max_chars
        )
        if c.layer == "body"
    ]


class TestChunkSourceMeasuresNonWhitespace:
    def test_whitespace_does_not_count_towards_the_budget(self, python_parser: object) -> None:
        """[Happy path] A symbol that is over the budget in raw characters but under it in
        non-whitespace stays whole."""
        code = _body(statements=40, indent=60)
        raw = len(code)
        solid = len("".join(code.split()))
        assert raw > 2000 and solid < 2000, f"fixture is wrong: raw={raw} solid={solid}"

        assert len(_chunks(python_parser, code, max_chars=2000)) == 1

    def test_non_whitespace_over_the_budget_does_split(self, python_parser: object) -> None:
        """[Happy path] The control at the other end. Without it, a budget that never split
        anything would satisfy the assertion above."""
        code = _body(statements=400, indent=4)
        assert len("".join(code.split())) > 2000
        assert len(_chunks(python_parser, code, max_chars=2000)) > 1

    def test_indentation_does_not_change_where_code_is_cut(self, python_parser: object) -> None:
        """[Boundary] **The assertion that can tell the two measures apart**, and the only one.

        The same code at two indentation depths must yield the same number of chunks. Under a raw
        count the indented version is far larger and cuts into more pieces, so reformatting a file
        would move its chunk boundaries — and re-embedding a whole repository is the cost of that.
        """
        flat = _body(statements=300, indent=4)
        deep = _body(statements=300, indent=40)
        assert len(deep) > len(flat) * 1.5, "fixture must actually differ in raw size"

        assert len(_chunks(python_parser, flat, max_chars=2000)) == len(
            _chunks(python_parser, deep, max_chars=2000)
        )

    def test_the_default_budget_is_unchanged(self, python_parser: object) -> None:
        """[Boundary] `FR-11` changes the UNIT, not the number. 4,000 is a guess agreed to stay one
        `[agreed 2026-08-26]`, and recalibrating it is a precondition on `A-SENS-02` — not something
        this boundary may quietly move while changing how it is counted."""
        from specweaver.workspace.analyzers import chunking

        assert chunking._DEFAULT_MAX_CHARS == 4000


class TestChunkSourceBudgetEdges:
    def test_a_symbol_of_pure_whitespace_never_splits(self, python_parser: object) -> None:
        """[Hostile] Nothing to measure. A budget of zero non-whitespace must not loop or divide by
        anything."""
        code = "def blank():\n" + "\n".join(" " * 200 for _ in range(50)) + "\n    pass\n"
        assert len(_chunks(python_parser, code, max_chars=10)) >= 1

    def test_a_tiny_budget_still_terminates(self, python_parser: object) -> None:
        """[Hostile] A budget smaller than a single line. Splitting is on line boundaries, so a
        line that cannot fit is emitted whole rather than dropped or looped over."""
        code = _body(statements=20, indent=4)
        chunks = _chunks(python_parser, code, max_chars=1)
        assert len(chunks) > 1
        assert "".join(chunks).replace("\n", "") == code.replace("\n", "")

    def test_nothing_is_lost_whatever_the_budget(self, python_parser: object) -> None:
        """[Boundary] `FR-17` under a changed measure. Every non-blank character still lands
        somewhere — the point of changing the unit was consistency, not permission to drop code."""
        code = _body(statements=200, indent=12)
        for budget in (1, 50, 500, 5000):
            joined = "".join(_chunks(python_parser, code, max_chars=budget))
            assert "".join(joined.split()) == "".join(code.split()), f"lost content at {budget}"
