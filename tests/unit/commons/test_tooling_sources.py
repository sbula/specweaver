# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Finding the test runner a project declares somewhere other than `pyproject.toml`.

Rung 2 of the coverage gap. 48 of the 121 corpus repositories declare pytest outside the manifest —
31 in `tox.ini`, the rest across a family of `requirements` spellings
(`docs/analysis/dependency_layout_corpus_2026-08-18.md`).

**The scope here is narrower than the file count suggests, and deliberately so.** All 30 real
`tox.ini` files from that corpus were parsed while writing this: 891 of their dependency lines carry
`{...}` interpolation — tox factors like `py3{10-14}: -r reqs.pip` and `{[testenv]deps}`
back-references — against 236 plain requirement lines. Resolving those means implementing tox's
substitution engine, and only 18 of the 30 projects have a plain `pytest` line at all. So the reader
takes what it can read and reports what it skipped; it does not pretend to be tox.

Proves: TECH-031 FR-7
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.commons.tooling_sources import declared_pytest

if TYPE_CHECKING:
    from pathlib import Path


class TestDeclaredPytest:
    """What to install, from the first source that names a runner we can actually read."""

    def test_a_requirements_file_is_installed_whole(self, tmp_path: Path) -> None:
        """No parsing: `uv pip install -r` already understands the format, including its includes.

        Installing the whole file rather than a pytest line also brings the plugins the suite needs,
        which a runner without `pytest-asyncio` would fail on just as surely as one without pytest.
        """
        (tmp_path / "requirements-dev.txt").write_text("pytest>=8\npytest-cov\nruff\n")

        source = declared_pytest(tmp_path)

        assert source is not None
        assert source.requirement_files == ("requirements-dev.txt",)
        assert source.packages == ()

    def test_a_file_that_does_not_name_pytest_is_not_a_source(self, tmp_path: Path) -> None:
        """The control. Installing a dev requirements file with no runner in it buys nothing and
        can fail the prepare phase on a dependency the tests never needed."""
        (tmp_path / "requirements-dev.txt").write_text("ruff\nmypy\n")

        assert declared_pytest(tmp_path) is None

    def test_a_nested_requirements_path_is_found(self, tmp_path: Path) -> None:
        (tmp_path / "requirements").mkdir()
        (tmp_path / "requirements" / "test.txt").write_text("pytest\n")

        source = declared_pytest(tmp_path)

        assert source is not None
        assert source.requirement_files == ("requirements/test.txt",)

    def test_a_tox_deps_block_contributes_its_plain_lines(self, tmp_path: Path) -> None:
        """The whole block, not just the pytest line — the rest is what the suite runs against."""
        (tmp_path / "tox.ini").write_text(
            "[tox]\nenvlist = py311\n\n[testenv]\ndeps =\n    pytest>=8\n    pytest-cov\n    mock\n"
            "commands = pytest {posargs}\n"
        )

        source = declared_pytest(tmp_path)

        assert source is not None
        assert source.packages == ("pytest>=8", "pytest-cov", "mock")

    def test_tox_lines_that_need_the_substitution_engine_are_skipped_and_reported(
        self, tmp_path: Path
    ) -> None:
        """891 of 236+891 real dependency lines look like this. Silently dropping them would make
        an incomplete environment look like a complete one."""
        (tmp_path / "tox.ini").write_text(
            "[testenv]\ndeps =\n    pytest\n    {[testenv:lint]deps}\n"
            "    py3{10-14}: -r requirements/light.pip\n    lint: ruff\n    -c constraints.txt\n"
        )

        source = declared_pytest(tmp_path)

        assert source is not None
        assert source.packages == ("pytest",)
        assert len(source.skipped) == 4, source.skipped
        assert any("{[testenv:lint]deps}" in s for s in source.skipped)
        assert any("lint: ruff" in s for s in source.skipped)

    def test_a_tox_include_becomes_a_requirements_file(self, tmp_path: Path) -> None:
        """`-r` is translatable without the substitution engine, so it is translated rather than
        skipped. `-rfile.txt` with no space is valid tox and appears in the corpus."""
        (tmp_path / "tox.ini").write_text(
            "[testenv]\ndeps =\n    pytest\n    -r dev-requirements.txt\n    -rextra.txt\n"
        )

        source = declared_pytest(tmp_path)

        assert source is not None
        assert source.requirement_files == ("dev-requirements.txt", "extra.txt")

    def test_a_tox_block_without_pytest_is_not_a_source(self, tmp_path: Path) -> None:
        """Installing a lint toolchain does not make `python -m pytest` work."""
        (tmp_path / "tox.ini").write_text("[testenv]\ndeps =\n    ruff\n    mypy\n")

        assert declared_pytest(tmp_path) is None

    def test_a_requirements_file_wins_over_tox(self, tmp_path: Path) -> None:
        """Both is common. The requirements file needs no parsing at all, so it is the safer read —
        and installing both risks two conflicting pins of the same package."""
        (tmp_path / "requirements-dev.txt").write_text("pytest\n")
        (tmp_path / "tox.ini").write_text("[testenv]\ndeps =\n    pytest==1.0\n")

        source = declared_pytest(tmp_path)

        assert source is not None
        assert source.requirement_files == ("requirements-dev.txt",)
        assert source.packages == ()

    def test_a_project_declaring_nothing_yields_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("no tooling here\n")

        assert declared_pytest(tmp_path) is None

    def test_an_unreadable_tox_file_is_not_an_error(self, tmp_path: Path) -> None:
        """Reading a foreign format is best-effort; it must never break the prepare phase."""
        (tmp_path / "tox.ini").write_text("[[[not ini at all\npytest\n")

        assert declared_pytest(tmp_path) is None
