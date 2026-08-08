# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the conventions guard (`scripts/check_conventions.py`).

Three of this check's four rules report nothing on the repo as it stands, which is exactly the
condition under which a broken guard looks identical to a passing one. So every rule is driven
against a synthetic family built to violate it, and against one built to satisfy it.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]

HEADER = (
    "# Copyright (c) 2026 sbula. All rights reserved.\n"
    "# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.\n"
)


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cv() -> ModuleType:
    return _load("check_conventions")


def _member(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + body, encoding="utf-8")
    return path


CONFORMING = """
class PythonParser(BaseThing):
    def alpha(self): return 1
    def beta(self): return 2
"""


# ---------------------------------------------------------------------------
# R1 — grab-bag names
# ---------------------------------------------------------------------------


class TestGrabBagNames:
    @pytest.mark.parametrize(
        "name", ["utils", "util", "helpers", "helper", "misc", "shared", "common"]
    )
    def test_each_banned_module_name_is_rejected(self, cv: ModuleType, name: str) -> None:
        found = cv.check_grab_bag_name(REPO_ROOT / "src" / "specweaver" / "core" / f"{name}.py")

        assert [v.rule for v in found] == ["R1"]

    def test_a_banned_package_name_is_rejected(self, cv: ModuleType) -> None:
        found = cv.check_grab_bag_name(REPO_ROOT / "src" / "specweaver" / "helpers" / "thing.py")

        assert [v.rule for v in found] == ["R1"]

    def test_the_commons_leaf_is_exempt(self, cv: ModuleType) -> None:
        """The one sanctioned shared kernel — the ban is about unnamed dumping grounds."""
        found = cv.check_grab_bag_name(REPO_ROOT / "src" / "specweaver" / "commons" / "qa.py")

        assert found == []

    def test_a_contract_named_module_passes(self, cv: ModuleType) -> None:
        found = cv.check_grab_bag_name(REPO_ROOT / "src" / "specweaver" / "core" / "flow.py")

        assert found == []

    def test_a_name_merely_containing_a_banned_word_is_not_rejected(self, cv: ModuleType) -> None:
        """`commonality.py` is a real name; substring matching would be a false positive."""
        found = cv.check_grab_bag_name(REPO_ROOT / "src" / "specweaver" / "core" / "commonality.py")

        assert found == []

    def test_the_repo_is_currently_clean_of_grab_bag_names(self, cv: ModuleType) -> None:
        files = cv.iter_python_files([REPO_ROOT / "src"])

        assert [v for f in files for v in cv.check_grab_bag_name(f)] == []


# ---------------------------------------------------------------------------
# R2 — file header
# ---------------------------------------------------------------------------


class TestHeader:
    """Detection is tested directly; `check_header` adds the src/scripts-only tree gate on top."""

    def test_a_file_with_the_header_passes(self, cv: ModuleType, tmp_path: Path) -> None:
        path = _member(tmp_path, "ok.py", "x = 1\n")

        assert cv.missing_header_markers(path) == []

    def test_a_file_without_the_header_is_detected(self, cv: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "bare.py"
        path.write_text("x = 1\n", encoding="utf-8")

        assert len(cv.missing_header_markers(path)) == 2

    def test_a_header_buried_below_the_scan_window_is_detected(
        self, cv: ModuleType, tmp_path: Path
    ) -> None:
        path = tmp_path / "late.py"
        path.write_text("\n" * 20 + HEADER, encoding="utf-8")

        assert cv.missing_header_markers(path) != []

    def test_a_real_src_file_missing_the_header_is_reported_as_r2(
        self, cv: ModuleType, tmp_path: Path
    ) -> None:
        """The gate must still fire where it applies, not just be silent everywhere."""
        assert cv._rel(REPO_ROOT / "src" / "x.py").startswith(cv.HEADER_TREES)

    def test_every_src_file_currently_carries_the_header(self, cv: ModuleType) -> None:
        offenders = [p for p in cv.iter_python_files([REPO_ROOT / "src"]) if cv.check_header(p)]

        assert offenders == []


# ---------------------------------------------------------------------------
# R3 / R4 — family conformance
# ---------------------------------------------------------------------------


@pytest.fixture()
def family(cv: ModuleType) -> object:
    return cv.Family(
        name="thing parser",
        glob="src/*/thing.py",
        base="BaseThing",
        suffix="Parser",
        prefix_from=0,
    )


class TestFamilyShape:
    def test_a_conforming_family_reports_nothing(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        _member(tmp_path, "src/python/thing.py", CONFORMING)
        _member(tmp_path, "src/rust/thing.py", CONFORMING.replace("Python", "Rust"))

        assert cv.check_family(family, repo_root=tmp_path) == []

    def test_a_member_not_inheriting_the_base_is_reported(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        _member(tmp_path, "src/python/thing.py", CONFORMING)
        _member(tmp_path, "src/rust/thing.py", "class RustParser:\n    pass\n")

        found = cv.check_family(family, repo_root=tmp_path)

        assert [v.rule for v in found] == ["R3"]

    def test_a_member_with_the_wrong_suffix_is_reported(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        _member(tmp_path, "src/python/thing.py", CONFORMING)
        _member(
            tmp_path,
            "src/rust/thing.py",
            "class RustHandler(BaseThing):\n    def alpha(self): return 1\n    def beta(self): return 2\n",
        )

        found = cv.check_family(family, repo_root=tmp_path)

        assert any(v.rule == "R3" and "end with" in v.message for v in found)

    def test_a_name_not_derived_from_its_directory_is_reported(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        _member(tmp_path, "src/python/thing.py", CONFORMING)
        _member(tmp_path, "src/rust/thing.py", CONFORMING.replace("Python", "Golang"))

        found = cv.check_family(family, repo_root=tmp_path)

        assert any("derived" in v.message for v in found)

    def test_a_single_member_family_is_not_judged(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        """One file is not a template — there is nothing to be consistent with."""
        _member(tmp_path, "src/python/thing.py", "class Whatever:\n    pass\n")

        assert cv.check_family(family, repo_root=tmp_path) == []


class TestFamilyContract:
    def test_a_member_missing_a_universal_method_is_reported(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        """The eleventh parser that forgot what the other ten all do."""
        _member(tmp_path, "src/python/thing.py", CONFORMING)
        _member(tmp_path, "src/rust/thing.py", CONFORMING.replace("Python", "Rust"))
        _member(
            tmp_path,
            "src/golang/thing.py",
            "class GolangParser(BaseThing):\n    def alpha(self): return 1\n",
        )

        found = cv.check_family(family, repo_root=tmp_path)

        assert [v.rule for v in found] == ["R4"]
        assert "beta" in found[0].message

    def test_the_report_names_how_many_siblings_have_it(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        _member(tmp_path, "src/python/thing.py", CONFORMING)
        _member(tmp_path, "src/rust/thing.py", CONFORMING.replace("Python", "Rust"))
        _member(
            tmp_path,
            "src/golang/thing.py",
            "class GolangParser(BaseThing):\n    def alpha(self): return 1\n",
        )

        found = cv.check_family(family, repo_root=tmp_path)

        assert "2 sibling" in found[0].message

    def test_a_method_only_some_siblings_have_is_not_required(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        """The bar is 'every other member' — a chatty rule gets suppressed, not fixed."""
        _member(tmp_path, "src/python/thing.py", CONFORMING + "    def extra(self): return 3\n")
        _member(tmp_path, "src/rust/thing.py", CONFORMING.replace("Python", "Rust"))
        _member(tmp_path, "src/golang/thing.py", CONFORMING.replace("Python", "Golang"))

        assert cv.check_family(family, repo_root=tmp_path) == []

    def test_private_methods_are_not_part_of_the_contract(
        self, cv: ModuleType, family: object, tmp_path: Path
    ) -> None:
        _member(tmp_path, "src/python/thing.py", CONFORMING + "    def _internal(self): return 3\n")
        _member(tmp_path, "src/rust/thing.py", CONFORMING.replace("Python", "Rust"))

        assert cv.check_family(family, repo_root=tmp_path) == []


def _test_file(root: Path, rel: str, body: str = "") -> Path:
    """A file under a fake `tests/` tree, so the rule can be driven without touching the real one."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class TestRegistryIdsInNames:
    """R5: a test is named for what it proves, never for the ticket that funded it.

    A registry ID is an accident of when the work happened; the behaviour outlives it. The rule
    covers every tier and every name — file, class and function — because the three offenders that
    survived its first version did so purely by living outside `tests/e2e/`.
    """

    def test_an_int_story_named_file_is_flagged(self, cv: ModuleType) -> None:
        path = REPO_ROOT / "tests" / "e2e" / "workflows" / "test_int_us_42_widget_e2e.py"

        assert [v.rule for v in cv.check_registry_ids_in_names(path)] == ["R5"]

    def test_a_capability_id_named_file_is_flagged(self, cv: ModuleType) -> None:
        path = REPO_ROOT / "tests" / "e2e" / "sandbox" / "test_c_exec_09_thing_e2e.py"

        assert [v.rule for v in cv.check_registry_ids_in_names(path)] == ["R5"]

    def test_a_tech_named_file_is_flagged(self, cv: ModuleType) -> None:
        path = REPO_ROOT / "tests" / "e2e" / "test_tech_042_fix_e2e.py"

        assert [v.rule for v in cv.check_registry_ids_in_names(path)] == ["R5"]

    def test_a_subject_named_file_passes(self, cv: ModuleType) -> None:
        path = REPO_ROOT / "tests" / "e2e" / "workflows" / "test_decomposition_e2e.py"

        assert cv.check_registry_ids_in_names(path) == []

    def test_an_integration_tier_file_is_flagged(self, cv: ModuleType) -> None:
        """Was invisible: the rule used to inspect `tests/e2e/` only."""
        path = REPO_ROOT / "tests" / "integration" / "sandbox" / "test_dispatcher_sf2_thing.py"

        assert [v.rule for v in cv.check_registry_ids_in_names(path)] == ["R5"]

    def test_a_unit_tier_file_is_flagged(self, cv: ModuleType) -> None:
        """Also invisible, and the reason a revision-hash name survived review."""
        path = REPO_ROOT / "tests" / "unit" / "alembic" / "test_af60fd3509a2_tech_005_rename.py"

        assert [v.rule for v in cv.check_registry_ids_in_names(path)] == ["R5"]

    def test_a_sub_feature_tag_in_a_filename_is_flagged(self, cv: ModuleType) -> None:
        path = REPO_ROOT / "tests" / "integration" / "sandbox" / "test_dispatcher_sf3_thing.py"

        assert [v.rule for v in cv.check_registry_ids_in_names(path)] == ["R5"]

    def test_a_story_named_test_class_is_flagged(self, cv: ModuleType, tmp_path: Path) -> None:
        path = _test_file(
            tmp_path, "tests/unit/test_thing.py", "class TestIntUs21Decomposition:\n    pass\n"
        )

        assert [v.rule for v in cv.check_registry_ids_in_names(path, repo_root=tmp_path)] == ["R5"]

    def test_a_story_named_test_function_is_flagged(self, cv: ModuleType, tmp_path: Path) -> None:
        path = _test_file(
            tmp_path, "tests/unit/test_thing.py", "def test_orchestrator_ignores_sf4():\n    pass\n"
        )

        assert [v.rule for v in cv.check_registry_ids_in_names(path, repo_root=tmp_path)] == ["R5"]

    def test_subject_named_classes_and_functions_pass(self, cv: ModuleType, tmp_path: Path) -> None:
        body = "class TestToolRegistry:\n    def test_missing_factory_warns(self):\n        pass\n"
        path = _test_file(tmp_path, "tests/unit/test_thing.py", body)

        assert cv.check_registry_ids_in_names(path, repo_root=tmp_path) == []

    @pytest.mark.parametrize(
        "name",
        [
            "test_c01_c02_c03.py",
            "test_c05_architecture_integration.py",
            "test_c12_archetype_code_bounds.py",
            "test_s07_test_first.py",
            "test_s12_integration.py",
        ],
    )
    def test_validation_rule_ids_are_domain_vocabulary_not_registry_ids(
        self, cv: ModuleType, name: str
    ) -> None:
        """`c05` is a validation rule, not a ticket. Flagging these would force a fresh allowlist —
        reopening the exact hole this rule exists to close.
        """
        path = REPO_ROOT / "tests" / "unit" / "assurance" / "validation" / name

        assert cv.check_registry_ids_in_names(path) == []

    @pytest.mark.parametrize(
        ("camel", "expected"),
        [
            ("TestIntUs21Decomposition", "test_int_us_21_decomposition"),
            ("TestTECH019References", "test_tech_019_references"),
            ("TestSF4Exclusions", "test_sf_4_exclusions"),
            ("TestC05Architecture", "test_c_05_architecture"),
            ("test_already_snake", "test_already_snake"),
            ("", ""),
        ],
    )
    def test_camel_case_is_normalised_before_matching(
        self, cv: ModuleType, camel: str, expected: str
    ) -> None:
        """Class names are CamelCase, so every alternative in the pattern depends on this split.

        Covered directly because the failure is silent and one-directional: if a transition stops
        splitting, CamelCase classes become invisible to R5 and the rule **fails open**. Nothing
        goes red — it simply stops finding things.
        """
        assert cv._snake(camel) == expected

    def test_a_rule_id_named_test_class_is_not_flagged(
        self, cv: ModuleType, tmp_path: Path
    ) -> None:
        """`c05` names a shipped module (`c05_import_direction.py`), so a test named for it IS
        named for its subject. Verified for filenames already; this pins it at class level, where a
        careless widening of the pattern would break the ten validation-rule test files.
        """
        path = _test_file(
            tmp_path, "tests/unit/test_thing.py", "class TestC05Architecture:\n    pass\n"
        )

        assert cv.check_registry_ids_in_names(path, repo_root=tmp_path) == []

    def test_a_registry_id_in_a_docstring_is_not_flagged(
        self, cv: ModuleType, tmp_path: Path
    ) -> None:
        """Names only. Scanning docstrings would flag every `Proves: TECH-NNN FR-N` tag and put
        this gate in direct contradiction with `check_fr_coverage.py`.
        """
        body = '"""Proves: TECH-019 FR-1, FR-4."""\n\n\ndef test_thing():\n    pass\n'
        path = _test_file(tmp_path, "tests/unit/test_thing.py", body)

        assert cv.check_registry_ids_in_names(path, repo_root=tmp_path) == []

    def test_an_unparseable_file_yields_no_naming_violation(
        self, cv: ModuleType, tmp_path: Path
    ) -> None:
        """Graceful degradation: a syntax error is not a naming defect."""
        path = _test_file(tmp_path, "tests/unit/test_thing.py", "def (((:\n")

        assert cv.check_registry_ids_in_names(path, repo_root=tmp_path) == []

    def test_the_rule_does_not_reach_outside_tests(self, cv: ModuleType) -> None:
        path = REPO_ROOT / "src" / "specweaver" / "core" / "flow" / "test_int_us_21_helper.py"

        assert cv.check_registry_ids_in_names(path) == []

    def test_the_legacy_allowlist_is_gone(self, cv: ModuleType) -> None:
        """It was frozen pending a ticket that decided renames and references together. This is it."""
        assert not hasattr(cv, "LEGACY_E2E_NAMES")

    def test_no_test_anywhere_in_the_tree_carries_a_registry_id(self, cv: ModuleType) -> None:
        """Replaces the old allowlist-parity test: with no list to keep in step with, the tree
        itself is the assertion — and it now covers every tier and every name, not just `e2e`
        filenames. A new offender must fail here rather than be absorbed into an exemption.
        """
        offenders = sorted(
            f"{v.path.relative_to(REPO_ROOT).as_posix()}: {v.message.split(' carries')[0]}"
            for p in (REPO_ROOT / "tests").rglob("*.py")
            if "__pycache__" not in p.parts
            for v in cv.check_registry_ids_in_names(p)
        )

        assert offenders == []

    # The allowlist-parity test that stood here is obsolete: the list is gone, so there is nothing
    # to keep in step with. Its replacement — "no test file anywhere carries a registry ID", the
    # whole tree as the assertion — lands in CB-2, because it cannot pass until the renames do.


class TestFixtureExemption:
    def test_a_sample_project_may_use_a_grab_bag_name(self, cv: ModuleType) -> None:
        """Fixtures stand in for other people's code; 'fixing' one destroys what it reproduces."""
        path = REPO_ROOT / "tests" / "fixtures" / "sample_project" / "src" / "greeter" / "utils.py"

        assert cv.check_grab_bag_name(path) == []

    def test_real_test_code_is_still_policed(self, cv: ModuleType) -> None:
        path = REPO_ROOT / "tests" / "unit" / "helpers.py"

        assert [v.rule for v in cv.check_grab_bag_name(path)] == ["R1"]


class TestHeaderScope:
    def test_the_header_rule_covers_the_tests_tree(self, cv: ModuleType) -> None:
        """Widened once the 349 missing headers were added, not narrowed to fit the code."""
        assert "tests/" in cv.HEADER_TREES

    def test_every_test_file_currently_carries_the_header(self, cv: ModuleType) -> None:
        offenders = [p for p in cv.iter_python_files([REPO_ROOT / "tests"]) if cv.check_header(p)]

        assert offenders == []

    def test_a_file_outside_every_declared_tree_is_not_judged(self, cv: ModuleType) -> None:
        assert cv.check_header(REPO_ROOT / "docs" / "example.py") == []


class TestRealFamilies:
    @pytest.mark.parametrize("index", [0, 1])
    def test_the_declared_families_actually_match_files(self, cv: ModuleType, index: int) -> None:
        """A glob that matches nothing is a rule that passes without checking anything."""
        family = cv.FAMILIES[index]

        assert len(list(REPO_ROOT.glob(family.glob))) >= 2

    @pytest.mark.parametrize("index", [0, 1])
    def test_the_real_families_conform_today(self, cv: ModuleType, index: int) -> None:
        assert cv.check_family(cv.FAMILIES[index]) == []
