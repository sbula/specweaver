# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import patch

from specweaver.validation.models import Status
from specweaver.validation.rules.code.c09_traceability import TraceabilityRule


def test_passes_when_no_frs_found():
    """If the spec has no functional requirements, the traceability matrix trivially passes."""
    rule = TraceabilityRule()
    with patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._find_project_root", return_value=Path("/tmp/root")), \
         patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._extract_all_requirements", return_value=set()):
        result = rule.check(spec_text="", spec_path=Path("/tmp/root/app.py"))

    assert result.status == Status.PASS
    assert "No explicit requirement tags" in result.message


def test_extracts_all_requirements(tmp_path):
    """Ensure the rule extracts exactly the FR and NFR targets from all specs in the specs directory."""
    root = tmp_path / "fake_project"
    specs_dir = root / "specs"
    specs_dir.mkdir(parents=True)

    (specs_dir / "comp1.md").write_text("Hello FR-1 and NFR-2")
    (specs_dir / "comp2.md").write_text("Other FR-99")

    rule = TraceabilityRule()
    target_ids = rule._extract_all_requirements(root)

    assert target_ids == {"FR-1", "NFR-2", "FR-99"}


def test_finds_project_root_and_tests(tmp_path):
    """Ensure we crawl up to find pyproject.toml and retrieve matching test files."""
    root = tmp_path / "fake_project"
    root.mkdir()
    (root / "pyproject.toml").touch()

    tests_dir = root / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_dummy.py"
    test_file.touch()

    code_file = root / "src" / "app.py"
    code_file.parent.mkdir(parents=True)
    code_file.touch()

    rule = TraceabilityRule()
    found_root = rule._find_project_root(code_file)
    assert found_root == root

    found_files = rule._discover_test_files(root)
    assert test_file in found_files


def test_ast_comment_extraction(tmp_path):
    """Ensure we correctly use tree-sitter to find trace tags exclusively in comments."""
    test_file = tmp_path / "test_fake.py"

    source_code = '''
def test_something():
    # @trace(FR-100)
    fake_string = "# @trace(FR-999)"
    assert False, "@trace(FR-555)"
    """
    @trace(NFR-200)
    """
'''
    test_file.write_text(source_code)

    rule = TraceabilityRule()
    with patch(
        "specweaver.validation.rules.code.c09_traceability.TraceabilityRule._discover_test_files",
        return_value=[test_file],
    ):
        mapped = rule._find_and_parse_tests(Path("/tmp/root"))

    assert "FR-100" in mapped
    assert "NFR-200" not in mapped
    assert "FR-999" not in mapped
    assert "FR-555" not in mapped


def test_fails_with_missing_frs():
    """Ensure the matrix fails if target IDs are unmapped."""
    with patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._find_project_root", return_value=Path("/tmp/root")), \
         patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._extract_all_requirements", return_value={"FR-1", "FR-2", "FR-3"}), \
         patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._find_and_parse_tests", return_value={"FR-1", "FR-2"}):
        rule = TraceabilityRule()
        result = rule.check(spec_text="", spec_path=Path("/tmp/root/app.py"))

    assert result.status == Status.FAIL
    assert "1 requirements lack" in result.message
    assert len(result.findings) == 1
    assert "FR-3 is unmapped" in result.findings[0].message


def test_passes_when_all_frs_mapped():
    """Ensure the matrix passes if all target IDs are mapped."""
    with patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._find_project_root", return_value=Path("/tmp/root")), \
         patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._extract_all_requirements", return_value={"FR-1", "FR-2", "FR-3"}), \
         patch("specweaver.validation.rules.code.c09_traceability.TraceabilityRule._find_and_parse_tests", return_value={"FR-1", "FR-2", "FR-3"}):
        rule = TraceabilityRule()
        result = rule.check(spec_text="", spec_path=Path("/tmp/root/app.py"))

    assert result.status == Status.PASS


def test_idempotent_multiple_tags(tmp_path):
    """Ensure multiple tests mapping the exact same requirement deduplicate successfully."""
    test_file_1 = tmp_path / "test_fake1.py"
    test_file_2 = tmp_path / "test_fake2.py"

    test_file_1.write_text("# @trace(FR-99)")
    test_file_2.write_text("# @trace(FR-99)")

    rule = TraceabilityRule()
    with patch(
        "specweaver.validation.rules.code.c09_traceability.TraceabilityRule._discover_test_files",
        return_value=[test_file_1, test_file_2],
    ):
        mapped = rule._find_and_parse_tests(Path("/tmp/root"))

    assert "FR-99" in mapped
    assert len(mapped) == 1


def test_missing_spec_file_graceful():
    """Ensure the rule handles None or missing project_root gracefully during discovery."""
    rule = TraceabilityRule()
    # Missing explicit project root handled gracefully without crashing
    result = rule.check(spec_text="", spec_path=None)
    assert result.status == Status.PASS
    assert "No valid workspace root found to assess traceability." in result.message


def test_ast_regex_boundaries(tmp_path):
    """Ensure regex captures standard variants like no spaces, ignoring trailing chars."""
    test_file = tmp_path / "test_bounds.py"
    test_file.write_text('''
    #@trace(FR-100)
    # @trace(NFR-200) trailing text
    #        @trace(FR-300)
    # this is not a trace FR-400
    ''')

    rule = TraceabilityRule()
    with patch(
        "specweaver.validation.rules.code.c09_traceability.TraceabilityRule._discover_test_files",
        return_value=[test_file],
    ):
        mapped = rule._find_and_parse_tests(Path("/tmp/root"))

    assert "FR-100" in mapped
    assert "NFR-200" in mapped
    assert "FR-300" in mapped
    assert "FR-400" not in mapped
