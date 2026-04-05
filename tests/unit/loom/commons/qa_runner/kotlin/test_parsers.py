# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for strict Kotlin SARIF parsing logic."""

import pytest

from specweaver.loom.commons.qa_runner.kotlin.parsers import parse_detekt_complexity


def test_parse_detekt_complexity_strict_mapping() -> None:
    data = {
        "runs": [
            {
                "results": [
                    {
                        "ruleId": "ComplexMethod",
                        "properties": {"complexity": 18},
                        "message": {"text": "High complexity"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "src/App.kt"},
                                    "region": {"startLine": 20},
                                }
                            }
                        ],
                    }
                ]
            }
        ]
    }

    # Test above threshold
    violations = parse_detekt_complexity(data, 10)
    assert len(violations) == 1
    assert violations[0].complexity == 18
    assert violations[0].file == "src/App.kt"

    # Test below threshold
    violations = parse_detekt_complexity(data, 20)
    assert len(violations) == 0


def test_parse_detekt_complexity_hard_fails_without_property() -> None:
    data = {
        "runs": [
            {
                "results": [
                    {
                        "ruleId": "ComplexMethod",
                        "message": {"text": "High complexity"},
                    }
                ]
            }
        ]
    }

    with pytest.raises(ValueError, match=r"HARD FAIL: SARIF property 'complexity'.*"):
        parse_detekt_complexity(data, 10)
