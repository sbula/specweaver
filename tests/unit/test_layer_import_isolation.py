# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Two layers must not reach into the sandbox, and both claims are absence proofs.

The validation layer reads pre-hydrated QA results out of `Rule.context` instead of executing QA
itself, and the interfaces layer delegates rather than importing execution. Neither claim had a
test.

**Why this lives in its own module rather than beside the other architecture invariants.** The FR
citation scan attributes whole-file: a file that names a story is credited with *every* requirement
token it contains, whatever those tokens were written for. The architecture module names a
different story and already carries six requirement tokens, so adding TECH-002's tags there would
have handed TECH-002 three requirements it does not prove -- measured, not feared. This module
therefore names exactly one story and carries exactly the two tokens it earns, and
`test_this_module_carries_only_the_tokens_it_earns` pins that.

The scanner itself is shared, not copied: it is imported from the architecture module below.
Importing does not copy that module's story name into this file's source, so the logic is reused
without the citation being reused.

Proves: TECH-002 FR-5.
Proves: TECH-002 FR-6.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.fixtures.arch_scanners import import_offenders

#: `src/specweaver/`. Derived here rather than imported from the architecture test module: this
#: file needs no test module's state, and borrowing one would execute its collection-time code.
SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "specweaver"


#: Requirement ids are assembled rather than written out. Writing one as a literal — even inside
#: an assertion about how many literals this file holds — creates the very token being counted.
#: That is not hypothetical: the first version of `test_this_module_carries_only_the_tokens_it_earns`
#: spelled its two expected ids out in the assertion and failed itself, reporting four tokens where
#: two were expected. It then failed a second time on a comment that quoted them while explaining
#: the first failure. The two in the module docstring's tags are the only literals this file holds.
def _token(n: int) -> str:
    return f"FR-{n}"


#: The prefix neither layer may import. A tuple because the scanner takes one.
SANDBOX_PREFIXES = ("specweaver.sandbox",)

#: The two roots this module asserts about, relative to `src/specweaver/`.
VALIDATION_ROOT = SRC_ROOT / "assurance" / "validation"
INTERFACES_ROOT = SRC_ROOT / "interfaces"


# ---------------------------------------------------------------------------
# The guard that stops everything below being an ornament
# ---------------------------------------------------------------------------


def test_the_scanned_roots_exist_and_contain_modules() -> None:
    """Both invariants below are ABSENCE proofs, and absence is what a missing tree returns.

    The sibling architecture module has a guard of this shape, but it asserts *its own* paths --
    the sandbox tree, `core/config/*.py`, two llm modules. Neither root scanned here is covered by
    it, so this proof does not inherit it and has to earn it. Without this test a renamed layer or
    a moved test file turns both invariants into ornaments that go on passing.

    Recursive on purpose: a non-recursive check would pass on a package holding only `__init__.py`,
    which is exactly the shape a half-moved layer leaves behind.
    """
    for root in (VALIDATION_ROOT, INTERFACES_ROOT):
        assert root.is_dir(), f"{root} does not exist — the scan below inspects nothing"
        assert list(root.rglob("*.py")), f"{root} holds no modules — the scan below is vacuous"


def test_a_nonexistent_root_reports_clean_which_is_why_that_guard_exists() -> None:
    """Demonstrates the failure mode rather than asserting it cannot happen.

    Pointed at a path that does not exist the scanner reports no offenders — indistinguishable from
    a layer that is genuinely clean. That is the whole argument for the guard above, so it is
    proven here instead of being asserted in prose.
    """
    assert import_offenders(SRC_ROOT / "no_such_layer", SANDBOX_PREFIXES, recursive=True) == []


# ---------------------------------------------------------------------------
# The two live invariants
# ---------------------------------------------------------------------------


def test_validation_layer_does_not_import_the_sandbox() -> None:
    """No module under `assurance/validation/` imports the sandbox, at any depth.

    `tach` also enforces this: the layer declares a dependency list that omits the sandbox, and a
    planted import makes `tach check` fail. This test is not redundant with that. It is the
    *citable* proof -- the test that runs `tach` carries no requirement tag of its own and shells
    out to a bare `tach` binary, which is silently absent unless the virtualenv's `bin` is on PATH.
    Observed failing exactly that way while this was written.

    Do not delete this as a duplicate of the tach run without first reading the sibling invariant
    below, which has no second enforcement at all.
    """
    assert import_offenders(VALIDATION_ROOT, SANDBOX_PREFIXES, recursive=True) == []


def test_interfaces_layer_does_not_import_the_sandbox() -> None:
    """No module under `interfaces/` imports the sandbox, at any depth.

    Unlike the validation layer above, **nothing else enforces this**. `specweaver.interfaces` is
    not a declared module in `tach.toml`, so the boundary checker has no opinion about it. This
    test is the only guard, and deleting it removes the constraint entirely rather than leaving a
    second copy behind.
    """
    assert import_offenders(INTERFACES_ROOT, SANDBOX_PREFIXES, recursive=True) == []


# ---------------------------------------------------------------------------
# Synthetic probes — these prove the LOGIC, and touch no real tree
# ---------------------------------------------------------------------------


def test_a_planted_import_is_detected(tmp_path: Path) -> None:
    """Hostile: the scanner reports an offender rather than passing everything."""
    (tmp_path / "rule.py").write_text("from specweaver.sandbox.registry import ToolRegistry\n")

    assert import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True) == [
        "rule.py: specweaver.sandbox.registry"
    ]


def test_a_plain_import_statement_is_detected_too(tmp_path: Path) -> None:
    """Hostile: `import x` and `from x import y` are different AST nodes; both must be seen."""
    (tmp_path / "adapter.py").write_text("import specweaver.sandbox.executor\n")

    assert import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True) == [
        "adapter.py: specweaver.sandbox.executor"
    ]


def test_a_deferred_import_inside_a_function_is_still_an_offender(tmp_path: Path) -> None:
    """Hostile: deferring an import does not make the dependency go away.

    The repo's cycle gate rejects deferring an import as a way to break a cycle; the same reasoning
    applies to a layer boundary, so the walk is whole-module rather than import-time only.
    """
    (tmp_path / "lazy.py").write_text(
        "def build():\n    from specweaver.sandbox.registry import ToolRegistry\n    return ToolRegistry\n"
    )

    assert import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True) == [
        "lazy.py: specweaver.sandbox.registry"
    ]


def test_recursion_finds_an_offender_in_a_nested_package(tmp_path: Path) -> None:
    """Boundary: the two live scans MUST be recursive or they inspect almost nothing.

    The validation layer keeps its rules in `rules/code/` and `rules/spec/`; a top-level-only scan
    there would walk past every rule and pass on an empty set. This is one half of a decision the
    sibling probe checks from the other side.
    """
    nested = tmp_path / "rules" / "code"
    nested.mkdir(parents=True)
    (nested / "c03.py").write_text("from specweaver.sandbox.registry import ToolRegistry\n")

    assert import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True) == [
        "c03.py: specweaver.sandbox.registry"
    ]
    assert import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=False) == []


def test_an_unrelated_import_is_not_reported(tmp_path: Path) -> None:
    """Happy: the scanner is specific, not a blanket import ban."""
    (tmp_path / "rule.py").write_text("from specweaver.core.config import settings\nimport re\n")

    assert import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True) == []


def test_an_unparseable_module_raises_instead_of_being_skipped(tmp_path: Path) -> None:
    """Degradation: a module the scanner cannot read must not be silently treated as clean.

    Skipping is how an absence proof goes quietly vacuous. The error names the offending file,
    because an architecture test failing with a bare syntax error sends the reader to the wrong
    place.
    """
    (tmp_path / "broken.py").write_text("def oops(:\n")

    with pytest.raises(SyntaxError, match=r"broken\.py"):
        import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True)


def test_every_prefix_in_the_tuple_is_matched(tmp_path: Path) -> None:
    """Boundary: `prefixes` takes more than one entry, and each must actually be checked.

    Both live callers here pass a single-element tuple, so nothing else in this module would
    notice if the parameter silently matched only the first. The other caller passes six.
    """
    (tmp_path / "a.py").write_text("from specweaver.sandbox.registry import ToolRegistry\n")
    (tmp_path / "b.py").write_text("from specweaver.graph.lineage import track\n")
    (tmp_path / "c.py").write_text("from specweaver.core.config import settings\n")

    found = import_offenders(tmp_path, ("specweaver.sandbox", "specweaver.graph"), recursive=True)

    assert found == ["a.py: specweaver.sandbox.registry", "b.py: specweaver.graph.lineage"]


def test_an_empty_prefix_tuple_finds_nothing(tmp_path: Path) -> None:
    """Boundary: `str.startswith(())` is always False, so an empty tuple reports a clean tree.

    That is inherited from the standard library rather than chosen, which is exactly why it is
    pinned here. A caller that computed its prefixes and arrived at an empty tuple would otherwise
    receive a confident all-clear over a directory full of violations.
    """
    (tmp_path / "rule.py").write_text("from specweaver.sandbox.registry import ToolRegistry\n")

    assert import_offenders(tmp_path, (), recursive=True) == []


def test_a_sibling_relative_import_carries_no_module_path(tmp_path: Path) -> None:
    """Degradation: `from . import x` sets the node's module to None and must not crash.

    The docstring claims relative imports cannot reach out of a package, so they are ignored
    rather than matched. Nothing verified the `None` case did not raise on the way to being
    ignored.
    """
    (tmp_path / "pkg.py").write_text("from . import sibling\nfrom .. import parent\n")

    assert import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True) == []


def test_a_non_utf8_module_raises_undecorated(tmp_path: Path) -> None:
    """Degradation: the path-naming wrapper covers parse errors only, and says so.

    A file that is not valid UTF-8 fails at the read, before any parsing, so it surfaces as a
    `UnicodeDecodeError` without the path prefix. Pinned because the docstring previously promised
    the path would be named on any failure, which was true only for malformed *syntax*.
    """
    (tmp_path / "binary.py").write_bytes(b"\xff\xfe import specweaver.sandbox\n")

    with pytest.raises(UnicodeDecodeError):
        import_offenders(tmp_path, SANDBOX_PREFIXES, recursive=True)


# ---------------------------------------------------------------------------
# This module guards its own citation footprint
# ---------------------------------------------------------------------------


def test_this_module_carries_only_the_tokens_it_earns() -> None:
    """The citation scan credits a story every requirement token in a file that names it.

    So this file may name exactly one story and hold exactly the two tokens in its own tags. A
    later contributor adding an innocent comment that mentions a third requirement, or naming a
    second story while explaining something, would silently credit work nobody did -- which is the
    defect this whole module was moved out of another file to avoid.

    The pattern below is built from a character class rather than written literally, so counting
    the tokens does not create one.
    """
    source = Path(__file__).read_text(encoding="utf-8")

    tokens = re.findall(r"FR-\d+", source)
    assert sorted(set(tokens)) == [_token(5), _token(6)], f"unexpected tokens: {tokens}"
    assert len(tokens) == 2, f"expected exactly two tokens, found {len(tokens)}: {tokens}"

    stories = set(re.findall(r"\b(?:TECH|INT-US)-\d+\b", source))
    assert stories == {"TECH-002"}, f"this file must name one story only, found: {stories}"
