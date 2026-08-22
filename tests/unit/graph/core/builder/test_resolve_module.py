# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which collected file an import names, and when it names none.

Proves: TECH-068 FR-8, FR-13

The whole resolution rule — longest-suffix-first matching, the package `__init__` fallback, the
case-insensitivity RT-21 depends on, and ambiguity collapsing to `None` — was exercised only through
integration tests that write real files to disk. Every branch is reachable from a pure function
taking two arguments, so the slow route was buying nothing.

`NFR-8` is a scope statement carrying **[proof: none]**, and nothing anywhere pinned the agreement
that makes it hold: `resolve_module` lowercases its candidates because `normalize_path` lowercases
before hashing, and a case-SENSITIVE match here would disagree with the hash it is about to compute.
Two functions, one assumption, and no test of the pair — the shape `TECH-058` had.
"""

from __future__ import annotations

import pytest

from specweaver.graph.core.builder.mapper import _matches_stem, _module_segments, resolve_module
from specweaver.graph.core.engine.hashing import SemanticHasher


class TestModuleSegments:
    @pytest.mark.parametrize(
        ("module", "expected"),
        [
            ("a.b", ["a", "b"]),
            ("crate::alpha::beta", ["crate", "alpha", "beta"]),
            ("a/b", ["a", "b"]),
            (".sibling", ["sibling"]),
            ("..pkg.mod", ["pkg", "mod"]),
        ],
    )
    def test_every_language_spells_a_path_its_own_way(
        self, module: str, expected: list[str]
    ) -> None:
        """Happy path: Python dots, Rust colons, Go and TypeScript slashes, one answer.

        Empty parts falling out is what turns a relative `.sibling` into `['sibling']` without a
        special case for it.
        """
        assert _module_segments(module) == expected

    @pytest.mark.parametrize("module", ["", ".", "...", "::", "///"])
    def test_a_module_that_names_nothing_has_no_segments(self, module: str) -> None:
        """Hostile: separators alone. The caller uses this to skip the import entirely."""
        assert _module_segments(module) == []


class TestMatchesStem:
    def test_a_file_is_its_own_stem(self) -> None:
        """Happy path."""
        assert _matches_stem("src/alpha/beta.rs", "alpha/beta")

    def test_a_package_matches_through_its_init(self) -> None:
        """Boundary: `a.b` names a directory when that directory has an `__init__`."""
        assert _matches_stem("src/a/b/__init__.py", "a/b")

    def test_a_partial_segment_does_not_match(self) -> None:
        """Boundary, and the one a naive `endswith` gets wrong.

        `notbeta.py` ends with `beta.py`, and it is a different file.
        """
        assert not _matches_stem("src/alpha/notbeta.py", "alpha/beta")
        assert not _matches_stem("src/xbeta.py", "beta")

    def test_a_file_with_no_suffix_still_matches(self) -> None:
        """Boundary: `rsplit('.', 1)` on a name with no dot must not eat the name."""
        assert _matches_stem("src/Makefile", "Makefile")


class TestResolveModule:
    _FILES = frozenset(
        {
            "src/alpha/beta.rs",
            "src/alpha/gamma.rs",
            "src/pkg/__init__.py",
            "src/other/beta.py",
        }
    )

    def test_a_dotted_module_finds_the_file_it_names(self) -> None:
        """Happy path: `crate::alpha::beta` finds `src/alpha/beta.rs` — `crate` is not a directory.

        Longest suffix first is what makes that work: the full stem misses, and the walk shortens
        until `alpha/beta` matches.
        """
        assert resolve_module("crate::alpha::beta", self._FILES) == "src/alpha/beta.rs"

    def test_a_package_resolves_to_its_init(self) -> None:
        """Happy path for the second shape a module can take."""
        assert resolve_module("pkg", self._FILES) == "src/pkg/__init__.py"

    def test_a_module_matching_nothing_is_unresolved(self) -> None:
        """Boundary: the stdlib is not ours, and saying so is the correct answer."""
        assert resolve_module("os.path", self._FILES) is None

    def test_a_name_in_two_files_is_unresolved_rather_than_guessed(self) -> None:
        """Graceful degradation: `beta` is in two directories, so it names no single file.

        `ADR-006` makes the graph the truth store — a reader seeing a visible unknown is better
        served than one following an invented dependency.
        """
        assert resolve_module("beta", self._FILES) is None

    def test_ambiguity_does_not_fall_through_to_a_shorter_stem(self) -> None:
        """Boundary: the walk must STOP on ambiguity, not keep shortening until something sticks.

        Continuing would let a two-way tie at one depth be resolved by an unrelated single match at
        the next — a fabricated dependency produced by the search order alone.
        """
        files = frozenset({"a/thing.py", "b/thing.py", "thing.py"})

        assert resolve_module("x.thing", files) is None

    def test_an_empty_collected_set_resolves_nothing(self) -> None:
        """Boundary: correct for a single-file ingest, not a defect."""
        assert resolve_module("alpha.beta", frozenset()) is None

    @pytest.mark.parametrize("module", ["", ".", "::"])
    def test_a_module_naming_nothing_resolves_to_nothing(self, module: str) -> None:
        """Hostile: no segments, no lookup, no crash."""
        assert resolve_module(module, self._FILES) is None

    def test_a_windows_path_is_matched_like_a_posix_one(self) -> None:
        """Hostile: collection on Windows yields backslashes and imports never do."""
        assert (
            resolve_module("alpha.beta", frozenset({"src\\alpha\\beta.rs"}))
            == "src\\alpha\\beta.rs"
        )


class TestResolveModuleAgreesWithHashing:
    """The pair `NFR-8` rests on, and which nothing asserted.

    `resolve_module` lowercases its candidates for one reason: `SemanticHasher.normalize_path`
    lowercases before hashing (RT-21), so a case-sensitive match here would resolve to a path whose
    hash belongs to a different node. Both halves are plainly visible and neither file mentions the
    other — exactly the asymmetry `TECH-058` was.
    """

    def test_a_differently_cased_import_resolves(self) -> None:
        """Happy path: `Alpha.Beta` must find `src/alpha/beta.rs`."""
        assert resolve_module("Alpha.Beta", frozenset({"src/alpha/beta.rs"})) == "src/alpha/beta.rs"

    def test_resolution_and_hashing_make_the_same_paths_equal(self) -> None:
        """The agreement itself, stated without either side's implementation in the assertion.

        If `normalize_path` ever stopped lowercasing, resolution would keep matching case-blind and
        hand back a path hashing to something else. This is what says so.
        """
        upper, lower = "SRC/Alpha/Beta.rs", "src/alpha/beta.rs"
        same_hash = SemanticHasher.normalize_path(upper) == SemanticHasher.normalize_path(lower)

        # BOTH directions. Lowering only the candidates passes the first of these and fails the
        # second, which is exactly the bug this file found: `import Models` against a collected
        # `Models.py` ghosted, while `from models import ...` against the same file resolved.
        resolves = [
            resolve_module("alpha.beta", frozenset({upper})) is not None,
            resolve_module("Alpha.Beta", frozenset({lower})) is not None,
            resolve_module("ALPHA.BETA", frozenset({upper})) is not None,
        ]

        assert all(r is same_hash for r in resolves), (
            f"resolution and hashing disagree about whether case matters (hash-equal={same_hash}, "
            f"resolves={resolves}) — one of them will be pointing at a node the other never created"
        )
