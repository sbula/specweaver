# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-03 SF-03 T1: DALLevel.rank strictness ordering.

The rank gives DALLevel a comparable strictness order (DAL_A strictest → DAL_E least)
so a configurable isolation threshold can ask "is this DAL at least as strict as X?".
"""

from __future__ import annotations

from specweaver.commons.enums.dal import DALLevel


class TestDALLevelRank:
    def test_strict_descending_order(self):
        # [Happy] A is strictest, E is least strict.
        assert (
            DALLevel.DAL_A.rank
            > DALLevel.DAL_B.rank
            > DALLevel.DAL_C.rank
            > DALLevel.DAL_D.rank
            > DALLevel.DAL_E.rank
        )

    def test_threshold_equality_is_inclusive(self):
        # [Boundary] a level meets its own threshold (>= comparison at the boundary).
        assert DALLevel.DAL_B.rank >= DALLevel.DAL_B.rank

    def test_dal_b_meets_but_dal_c_misses_a_dal_b_threshold(self):
        # [Boundary] the DAL_B default threshold: A/B qualify, C/D/E do not.
        threshold = DALLevel.DAL_B.rank
        assert DALLevel.DAL_A.rank >= threshold
        assert DALLevel.DAL_B.rank >= threshold
        assert DALLevel.DAL_C.rank < threshold
        assert DALLevel.DAL_D.rank < threshold
        assert DALLevel.DAL_E.rank < threshold

    def test_every_level_has_a_distinct_int_rank(self):
        # [Boundary] all five levels are ranked, distinct, and integer-typed (no KeyError).
        ranks = [level.rank for level in DALLevel]
        assert all(isinstance(r, int) for r in ranks)
        assert len(set(ranks)) == len(list(DALLevel))

    def test_rank_aligns_with_is_strict(self):
        # [Boundary] the is_strict set (A/B) is exactly the top two ranks — the two concepts agree.
        strict = sorted((lvl for lvl in DALLevel if lvl.is_strict), key=lambda x: x.rank)
        top_two = sorted(DALLevel, key=lambda x: x.rank)[-2:]
        assert set(strict) == set(top_two)
