# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from specweaver.planning.ui_extractor import extract_ui_requirements


def test_extract_ui_requirements_no_protocol():
    spec = "# Some Spec\n\nNo protocol here."
    assert extract_ui_requirements(spec) is None


def test_extract_ui_requirements_empty_protocol():
    spec = "## Protocol\n\n## Next section"
    assert extract_ui_requirements(spec) is None


def test_extract_ui_requirements_no_ui_keywords():
    spec = "## Protocol\n\nJust returning regular JSON data."
    assert extract_ui_requirements(spec) is None


def test_extract_ui_requirements_with_ui_keywords():
    spec = "## Protocol\n\nThe UI will show a dashboard view with a button."
    result = extract_ui_requirements(spec)
    assert result is not None
    assert "dashboard view" in result.description


def test_extract_ui_requirements_contract_section():
    spec = "## Contract\n\nThe web frontend calls this endpoint."
    result = extract_ui_requirements(spec)
    assert result is not None
    assert "web frontend" in result.description


def test_extract_ui_requirements_keywords_outside_section():
    spec = "The UI will have a dashboard.\n\n## Not Protocol\n\nStuff here."
    assert extract_ui_requirements(spec) is None


def test_extract_ui_requirements_multiple_protocols():
    spec = "## Protocol\n\nThe UI dashboard.\n\n## Protocol\n\nMore frontend stuff."
    result = extract_ui_requirements(spec)
    assert result is not None
    assert "The UI dashboard" in result.description
    assert "More frontend stuff" in result.description


def test_extract_ui_requirements_sub_headers_ignored():
    spec = "### Protocol\n\nThis frontend requires a dashboard."
    assert extract_ui_requirements(spec) is None
