# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for strict Rust SARIF parsing logic."""

import pytest

from specweaver.loom.commons.test_runner.rust.parsers import parse_clippy_complexity


def test_parse_clippy_complexity_strict_mapping() -> None:
    data = {
        "runs": [{
            "results": [{
                "ruleId": "clippy::cognitive_complexity",
                "properties": {"complexity": 18},
                "message": {"text": "High complexity"},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": "src/main.rs"},
                        "region": {"startLine": 20}
                    }
                }]
            }]
        }]
    }

    # Test above threshold
    violations = parse_clippy_complexity(data, 10)
    assert len(violations) == 1
    assert violations[0].complexity == 18
    assert violations[0].file == "src/main.rs"

    # Test below threshold
    violations = parse_clippy_complexity(data, 20)
    assert len(violations) == 0

def test_parse_clippy_complexity_hard_fails_without_property() -> None:
    data = {
        "runs": [{
            "results": [{
                "ruleId": "clippy::cognitive_complexity",
                "message": {"text": "High complexity"},
            }]
        }]
    }

    with pytest.raises(ValueError, match=r"HARD FAIL: SARIF property 'complexity'.*"):
        parse_clippy_complexity(data, 10)
