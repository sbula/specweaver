# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for recency weighting utilities."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from specweaver.standards.recency import compute_half_life, recency_weight

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# recency_weight()
# ---------------------------------------------------------------------------


class TestRecencyWeight:
    """Tests for exponential decay weight calculation."""

    def test_file_modified_now_has_weight_one(self) -> None:
        """A file modified right now should have weight ≈ 1.0."""
        now = time.time()
        weight = recency_weight(now, half_life_days=365)
        assert weight == pytest.approx(1.0, abs=0.01)

    def test_file_modified_one_half_life_ago_has_weight_half(self) -> None:
        """A file modified exactly one half-life ago should have weight ≈ 0.5."""
        one_year_ago = time.time() - (365 * 86400)
        weight = recency_weight(one_year_ago, half_life_days=365)
        assert weight == pytest.approx(0.5, abs=0.02)

    def test_file_modified_two_half_lives_ago_has_weight_quarter(self) -> None:
        """Two half-lives → weight ≈ 0.25."""
        two_years_ago = time.time() - (730 * 86400)
        weight = recency_weight(two_years_ago, half_life_days=365)
        assert weight == pytest.approx(0.25, abs=0.02)

    def test_very_old_file_has_near_zero_weight(self) -> None:
        """A file from 10 half-lives ago should have weight ≈ 0.001."""
        ten_lives_ago = time.time() - (3650 * 86400)
        weight = recency_weight(ten_lives_ago, half_life_days=365)
        assert weight < 0.01

    def test_weight_is_always_positive(self) -> None:
        """Exponential decay never reaches zero."""
        ancient = time.time() - (36500 * 86400)  # 100 years
        weight = recency_weight(ancient, half_life_days=365)
        assert weight > 0

    def test_future_mtime_returns_weight_at_most_one(self) -> None:
        """If mtime is in the future (clock skew), clamp to 1.0."""
        future = time.time() + (86400 * 30)
        weight = recency_weight(future, half_life_days=365)
        assert weight <= 1.0

    def test_short_half_life_decays_faster(self) -> None:
        """Shorter half-life should give lower weight for the same age."""
        six_months_ago = time.time() - (180 * 86400)
        w_short = recency_weight(six_months_ago, half_life_days=180)
        w_long = recency_weight(six_months_ago, half_life_days=730)
        assert w_short < w_long

    def test_zero_half_life_raises(self) -> None:
        """Half-life of zero should raise ValueError."""
        with pytest.raises(ValueError, match="half_life_days"):
            recency_weight(time.time(), half_life_days=0)

    def test_negative_half_life_raises(self) -> None:
        """Negative half-life should raise ValueError."""
        with pytest.raises(ValueError, match="half_life_days"):
            recency_weight(time.time(), half_life_days=-10)


# ---------------------------------------------------------------------------
# compute_half_life()
# ---------------------------------------------------------------------------


class TestComputeHalfLife:
    """Tests for auto-computing half-life from project age."""

    def test_young_project_gets_minimum_half_life(self, tmp_path: Path) -> None:
        """A project < 1 year old should get 180-day half-life (minimum)."""
        # Create a file 6 months old
        f = tmp_path / "recent.py"
        f.write_text("pass")
        half_life = compute_half_life(tmp_path)
        assert half_life == pytest.approx(180, abs=10)

    def test_mid_age_project_gets_proportional_half_life(
        self, tmp_path: Path,
    ) -> None:
        """A 5-year-old project should get ~600-day half-life."""
        f = tmp_path / "old.py"
        f.write_text("pass")
        # Mock mtime to 5 years ago
        five_years_ago = time.time() - (5 * 365 * 86400)
        import os
        os.utime(f, (five_years_ago, five_years_ago))
        half_life = compute_half_life(tmp_path)
        assert 500 < half_life < 700

    def test_legacy_project_gets_maximum_half_life(self, tmp_path: Path) -> None:
        """A 30-year-old project should get 730-day cap (maximum)."""
        f = tmp_path / "ancient.py"
        f.write_text("pass")
        thirty_years_ago = time.time() - (30 * 365 * 86400)
        import os
        os.utime(f, (thirty_years_ago, thirty_years_ago))
        half_life = compute_half_life(tmp_path)
        assert half_life == pytest.approx(730, abs=10)

    def test_empty_directory_returns_minimum(self, tmp_path: Path) -> None:
        """Directory with no files should return minimum half-life."""
        half_life = compute_half_life(tmp_path)
        assert half_life == pytest.approx(180, abs=10)

    def test_only_considers_source_files(self, tmp_path: Path) -> None:
        """Should only consider source files (.py, .js, .ts), not .txt."""
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        ten_years_ago = time.time() - (10 * 365 * 86400)
        import os
        os.utime(txt, (ten_years_ago, ten_years_ago))

        py = tmp_path / "new.py"
        py.write_text("pass")
        # py file is brand new (just created)

        half_life = compute_half_life(tmp_path)
        # Should use py file age, not txt — project is young
        assert half_life == pytest.approx(180, abs=10)


# ---------------------------------------------------------------------------
# _find_oldest_source_mtime()
# ---------------------------------------------------------------------------


class TestFindOldestSourceMtime:
    """Tests for _find_oldest_source_mtime edge cases."""

    def test_no_source_files_returns_none(self, tmp_path: Path) -> None:
        """Directory with only non-source files → None."""
        from specweaver.standards.recency import _find_oldest_source_mtime

        (tmp_path / "readme.md").write_text("hello")
        (tmp_path / "config.yaml").write_text("key: val")
        (tmp_path / "data.json").write_text("{}")

        assert _find_oldest_source_mtime(tmp_path) is None

    def test_empty_directory_returns_none(self, tmp_path: Path) -> None:
        """Empty directory → None."""
        from specweaver.standards.recency import _find_oldest_source_mtime

        assert _find_oldest_source_mtime(tmp_path) is None

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Files inside hidden directories (.hidden/) are ignored."""
        import os

        from specweaver.standards.recency import _find_oldest_source_mtime

        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        old_file = hidden / "ancient.py"
        old_file.write_text("pass")
        ancient = time.time() - (50 * 365 * 86400)
        os.utime(old_file, (ancient, ancient))

        # Visible file is recent
        visible = tmp_path / "recent.py"
        visible.write_text("pass")

        mtime = _find_oldest_source_mtime(tmp_path)
        # Should use the visible file, not the hidden one
        assert mtime is not None
        assert mtime > ancient

    def test_skips_pycache(self, tmp_path: Path) -> None:
        """Files inside __pycache__ are ignored."""
        import os

        from specweaver.standards.recency import _find_oldest_source_mtime

        cache = tmp_path / "__pycache__"
        cache.mkdir()
        cached = cache / "module.cpython-313.py"
        cached.write_text("pass")
        ancient = time.time() - (50 * 365 * 86400)
        os.utime(cached, (ancient, ancient))

        visible = tmp_path / "main.py"
        visible.write_text("pass")

        mtime = _find_oldest_source_mtime(tmp_path)
        assert mtime is not None
        assert mtime > ancient

    def test_finds_oldest_among_multiple_files(self, tmp_path: Path) -> None:
        """Returns the oldest mtime when multiple source files exist."""
        import os

        from specweaver.standards.recency import _find_oldest_source_mtime

        new_file = tmp_path / "new.py"
        new_file.write_text("pass")

        old_file = tmp_path / "old.py"
        old_file.write_text("pass")
        three_years_ago = time.time() - (3 * 365 * 86400)
        os.utime(old_file, (three_years_ago, three_years_ago))

        mtime = _find_oldest_source_mtime(tmp_path)
        assert mtime is not None
        assert mtime == pytest.approx(three_years_ago, abs=1)

    def test_recognizes_multiple_source_extensions(self, tmp_path: Path) -> None:
        """Should recognize .js, .ts, .go, .rs, etc. as source files."""

        from specweaver.standards.recency import _find_oldest_source_mtime

        for ext in (".js", ".ts", ".go", ".rs", ".java"):
            f = tmp_path / f"file{ext}"
            f.write_text("content")

        mtime = _find_oldest_source_mtime(tmp_path)
        assert mtime is not None

