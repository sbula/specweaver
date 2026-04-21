# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import patch

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c09_traceability import TraceabilityRule


def test_passes_when_no_frs_found():
    """If the spec has no functional requirements, the traceability matrix trivially passes."""
    rule = TraceabilityRule()
    with (
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._find_project_root",
            return_value=Path("/tmp/root"),
        ),
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._extract_all_requirements",
            return_value=set(),
        ),
    ):
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
    """Ensure we crawl up to find pyproject.toml."""
    root = tmp_path / "fake_project"
    root.mkdir()
    (root / "pyproject.toml").touch()

    code_file = root / "src" / "app.py"
    code_file.parent.mkdir(parents=True)
    code_file.touch()

    rule = TraceabilityRule()
    found_root = rule._find_project_root(code_file)
    assert found_root == root


def test_ast_comment_extraction(tmp_path):
    """Ensure we delegate successfully to AnalyzerFactory for multiple languages."""
    root = tmp_path / "fake_project"
    root.mkdir()
    (root / "pyproject.toml").touch()

    tests_dir = root / "tests"
    tests_dir.mkdir()

    # Python test
    test_py = tests_dir / "test_fake.py"
    test_py.write_text(
        "def test_something():\n"
        "    # @trace(FR-100)\n"
        '    fake_string = "# @trace(FR-999)"\n'
        '    assert False, "@trace(FR-555)"\n'
        '    """\n'
        "    @trace(NFR-200)\n"
        '    """\n'
    )

    # Java test
    test_java = tests_dir / "MyFakeTest.java"
    test_java.write_text("class MyFakeTest {\n    // @trace(FR-101)\n    void test() {}\n}\n")

    # Rust test
    test_rust = tests_dir / "my_fake_scenarios.rs"
    test_rust.write_text("// @trace(FR-102)\nfn test() {}\n")

    rule = TraceabilityRule()
    mapped = rule._find_and_parse_tests(root)

    # Note: Python's NFR-200 was inside a block string which is parsed as an expression statement, not a comment,
    # so it correctly shouldn't be included if only real "comment" tokens are matched.
    assert "FR-100" in mapped
    assert "FR-101" in mapped
    assert "FR-102" in mapped
    assert "FR-999" not in mapped
    assert "FR-555" not in mapped


def test_fails_with_missing_frs():
    """Ensure the matrix fails if target IDs are unmapped."""
    with (
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._find_project_root",
            return_value=Path("/tmp/root"),
        ),
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._extract_all_requirements",
            return_value={"FR-1", "FR-2", "FR-3"},
        ),
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._find_and_parse_tests",
            return_value={"FR-1", "FR-2"},
        ),
    ):
        rule = TraceabilityRule()
        result = rule.check(spec_text="", spec_path=Path("/tmp/root/app.py"))

    assert result.status == Status.FAIL
    assert "1 requirements lack" in result.message
    assert len(result.findings) == 1
    assert "FR-3 is unmapped" in result.findings[0].message


def test_passes_when_all_frs_mapped():
    """Ensure the matrix passes if all target IDs are mapped."""
    with (
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._find_project_root",
            return_value=Path("/tmp/root"),
        ),
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._extract_all_requirements",
            return_value={"FR-1", "FR-2", "FR-3"},
        ),
        patch(
            "specweaver.assurance.validation.rules.code.c09_traceability.TraceabilityRule._find_and_parse_tests",
            return_value={"FR-1", "FR-2", "FR-3"},
        ),
    ):
        rule = TraceabilityRule()
        result = rule.check(spec_text="", spec_path=Path("/tmp/root/app.py"))

    assert result.status == Status.PASS


def test_idempotent_multiple_tags(tmp_path):
    """Ensure multiple tests mapping the exact same requirement deduplicate successfully."""
    root = tmp_path / "fake_project"
    root.mkdir()

    test_file_1 = root / "test_fake1.py"
    test_file_2 = root / "test_fake2.py"

    test_file_1.write_text("# @trace(FR-99)")
    test_file_2.write_text("# @trace(FR-99)")

    rule = TraceabilityRule()
    mapped = rule._find_and_parse_tests(root)

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
    """Ensure regex captures standard variants like multiple traces."""
    root = tmp_path / "fake_project"
    root.mkdir()

    test_file = root / "test_bounds.py"
    test_file.write_text(
        "#@trace(FR-100)\n"
        "# @trace(NFR-200) trailing text\n"
        "#        @trace(FR-300)\n"
        "# this is not a trace FR-400\n"
    )

    rule = TraceabilityRule()
    mapped = rule._find_and_parse_tests(root)

    assert "FR-100" in mapped
    assert "NFR-200" in mapped
    assert "FR-300" in mapped
    assert "FR-400" not in mapped


def test_c09_extracts_analyzer_factory_via_di(tmp_path):
    """Ensure the rule successfully extracts AnalyzerFactory from the DI context payload, avoiding global imports."""
    from unittest.mock import MagicMock

    root = tmp_path / "fake_project"

    mock_analyzer = MagicMock()
    mock_analyzer.extract_test_mapped_requirements.return_value = {"FR-777", "NFR-888"}

    mock_factory = MagicMock()
    mock_factory.get_all_analyzers.return_value = [mock_analyzer]

    rule = TraceabilityRule()
    rule.context = {"analyzer_factory": mock_factory}

    mapped = rule._find_and_parse_tests(root)

    assert "FR-777" in mapped
    assert "NFR-888" in mapped
    mock_factory.get_all_analyzers.assert_called_once()
    mock_analyzer.extract_test_mapped_requirements.assert_called_once_with(root)
