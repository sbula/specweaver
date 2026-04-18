# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for strict Java SARIF parsing logic."""

import pytest

from specweaver.workspace.parsers.java.parsers import parse_pmd_complexity


def test_parse_pmd_complexity_strict_mapping() -> None:
    data = {
        "runs": [
            {
                "results": [
                    {
                        "ruleId": "CyclomaticComplexity",
                        "properties": {"complexity": 15},
                        "message": {"text": "High complexity"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "src/Main.java"},
                                    "region": {"startLine": 10},
                                }
                            }
                        ],
                    }
                ]
            }
        ]
    }

    # Test above threshold
    violations = parse_pmd_complexity(data, 10)
    assert len(violations) == 1
    assert violations[0].complexity == 15
    assert violations[0].file == "src/Main.java"

    # Test below threshold
    violations = parse_pmd_complexity(data, 20)
    assert len(violations) == 0


def test_parse_pmd_complexity_hard_fails_without_property() -> None:
    data = {
        "runs": [
            {
                "results": [
                    {
                        "ruleId": "CyclomaticComplexity",
                        "message": {"text": "High complexity"},
                    }
                ]
            }
        ]
    }

    with pytest.raises(ValueError, match=r"HARD FAIL: SARIF property 'complexity'.*"):
        parse_pmd_complexity(data, 10)
