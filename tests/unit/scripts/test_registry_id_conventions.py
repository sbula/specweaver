# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test is named for what it exercises, and a unit test class names its subject.

Two naming rules that outlive the tickets that added them. The first refuses a registry id anywhere
in a test's filename, class name or function name, in every tier. The second requires a unit test
class to name the class or function it exercises, ratcheted against a frozen per-directory count so
the pre-existing ones do not have to be fixed at once.

**All fixtures use synthetic ids.** A real story id anywhere in this module would hand that story
every requirement token below — the defect these very rules exist to stop, reproduced one file over.
The fixtures use the snake_case spelling the rule matches (`tech_999`), which is a different string
from the canonical form the citation scan reads — so they trigger the rule while naming nothing.

**Why this duplicates a little of `test_check_conventions.py`.** That module names a different
story, so tagging it would credit that story with these tokens. This asserts the rules' observable
behaviour rather than the checker's internals, which is what these requirements actually claim. The
overlap is the price of the attribution rule and is recorded rather than hidden.

Proves: TECH-025 FR-6.
Proves: TECH-025 FR-7.
Proves: TECH-025 FR-8.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]

#: The rule matches the SNAKE_CASE spelling a filename or symbol uses (`tech_\d{3}`), while the
#: citation scan matches the canonical `TECH-NNN`. Those are different strings, so a fixture can
#: trigger the rule without naming any story at all — which is what makes this module safe to write.
#: `999` belongs to no ticket regardless.
SAMPLE_SNAKE = "tech_999"

#: For the one fixture that needs a canonical-form id, in a docstring the rule never inspects.
SAMPLE_ID = "SAMPLE-1"


def _token(n: int) -> str:
    return f"FR-{n}"


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _conventions() -> ModuleType:
    return _load("check_conventions")


def _write(tmp_path: Path, rel: str, body: str = "") -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# A registry id may not name a test — file, class or function, in any tier
# ---------------------------------------------------------------------------


def test_a_registry_id_in_a_test_filename_is_rejected(tmp_path: Path) -> None:
    """The original shape of the rule, and still the commonest."""
    mod = _conventions()
    path = _write(tmp_path, f"tests/unit/test_{SAMPLE_SNAKE}_thing.py")

    violations = mod.check_registry_ids_in_names(path, repo_root=tmp_path)

    assert [v.rule for v in violations] == ["R5"]
    assert "filename" in violations[0].message


def test_a_registry_id_in_a_class_or_function_name_is_rejected(tmp_path: Path) -> None:
    """Names inside the file, not just the file itself.

    The rule's first version inspected filenames only, and offenders survived it purely by being
    spelled as a class or a function instead.
    """
    mod = _conventions()
    body = (
        f"class Test{SAMPLE_SNAKE.title().replace('_', '')}Behaviour:\n"
        "    def test_ok(self) -> None:\n        pass\n\n\n"
        f"def test_{SAMPLE_SNAKE}_regression() -> None:\n    pass\n"
    )
    path = _write(tmp_path, "tests/unit/test_named_for_its_subject.py", body)

    violations = mod.check_registry_ids_in_names(path, repo_root=tmp_path)

    assert len(violations) == 2, [v.message for v in violations]
    assert all(v.rule == "R5" for v in violations)
    assert all("test name" in v.message for v in violations)


def test_the_rule_covers_every_tier(tmp_path: Path) -> None:
    """Boundary: integration and e2e are not exempt.

    Three offenders once survived by living outside the one directory the rule inspected, so the
    tiers are asserted rather than assumed.
    """
    mod = _conventions()
    for tier in ("unit", "integration", "e2e"):
        path = _write(tmp_path, f"tests/{tier}/test_{SAMPLE_SNAKE}_thing.py")
        assert mod.check_registry_ids_in_names(path, repo_root=tmp_path), tier


def test_a_sub_feature_suffix_is_caught_too(tmp_path: Path) -> None:
    """Boundary: the `_sf<N>` form is a registry reference wearing a different shape."""
    mod = _conventions()
    body = "def test_dispatcher_delegation_sf4() -> None:\n    pass\n"
    path = _write(tmp_path, "tests/unit/test_dispatcher_delegation.py", body)

    assert mod.check_registry_ids_in_names(path, repo_root=tmp_path)


def test_a_citation_tag_in_a_docstring_is_not_a_violation(tmp_path: Path) -> None:
    """The rule inspects NAMES only, and this is why that matters.

    A trailing citation tag is the one sanctioned place a registry id may appear in a test, and the
    coverage gate reads it. Flagging it here would put the two gates in direct contradiction and
    make the citation convention impossible to satisfy — so the exemption is pinned, not assumed.
    """
    mod = _conventions()
    tag = f"Proves: {SAMPLE_ID} {_token(2)}."
    body = f'"""Tests the thing.\n\n{tag}\n"""\n\n\ndef test_thing() -> None:\n    pass\n'
    path = _write(tmp_path, "tests/unit/test_thing.py", body)

    assert mod.check_registry_ids_in_names(path, repo_root=tmp_path) == []


def test_a_file_outside_the_tests_tree_is_out_of_scope(tmp_path: Path) -> None:
    """Boundary: the rule is about test names; source and script names are governed elsewhere."""
    mod = _conventions()
    path = _write(tmp_path, f"src/specweaver/{SAMPLE_SNAKE}_helper.py")

    assert mod.check_registry_ids_in_names(path, repo_root=tmp_path) == []


# ---------------------------------------------------------------------------
# A unit test class names its subject, ratcheted against a frozen baseline
# ---------------------------------------------------------------------------


def test_the_class_naming_baseline_exists_and_is_frozen() -> None:
    """The ratchet needs a baseline; without one the rule cannot report growth at all.

    Asserted rather than assumed because an absent baseline is indistinguishable from a clean
    repository when the check only reports directories whose count grew.
    """
    mod = _conventions()

    baseline = mod.load_naming_baseline()

    assert baseline is not None, "no frozen baseline — the ratchet cannot detect growth"
    assert baseline, "baseline is empty"


def test_the_baseline_records_a_count_per_directory() -> None:
    """The ratchet is per-directory, so one badly-named class cannot hide behind another's fix."""
    mod = _conventions()

    baseline = mod.load_naming_baseline()
    counts = baseline.get("counts", baseline)

    assert isinstance(counts, dict) and counts
    assert all(isinstance(v, int) and v >= 0 for v in counts.values()), counts


# ---------------------------------------------------------------------------
# This module guards its own citation footprint
# ---------------------------------------------------------------------------


def test_this_module_names_no_real_story() -> None:
    """Every fixture id here is synthetic, and that is load-bearing rather than tidy.

    A real id in any fixture would be credited with this module's requirement tokens by the very
    scan these rules protect.
    """
    source = Path(__file__).read_text(encoding="utf-8")

    tokens = re.findall(r"FR-\d+", source)
    assert sorted(set(tokens)) == [_token(n) for n in (6, 7, 8)], f"unexpected: {tokens}"

    stories = set(re.findall(r"\b(?:TECH|INT-US)-\d+\b", source))
    assert stories == {"TECH-025"}, f"this file must name one story only, found: {stories}"
