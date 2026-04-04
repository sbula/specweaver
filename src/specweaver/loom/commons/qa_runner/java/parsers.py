# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Java test runner parsers for structural SARIF mappings."""

from typing import Any

from specweaver.loom.commons.qa_runner.interface import ComplexityViolation


def parse_pmd_complexity(data: dict[str, Any], max_complexity: int) -> list[ComplexityViolation]:
    """Parse PMD complexities strictly from structural SARIF properties without Regex."""
    violations = []

    for run in data.get("runs", []):
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")

            # PMD explicitly identifies complexity rules
            if "complexity" not in rule_id.lower() and "ncss" not in rule_id.lower():
                continue

            # Pure JSON mapping check. NO REGEX ALLOWED.
            props = result.get("properties", {})
            comp_val = None

            if "complexity" in props:
                comp_val = int(props["complexity"])
            elif "CyclomaticComplexity" in props:
                comp_val = int(props["CyclomaticComplexity"])

            if comp_val is None:
                raise ValueError("HARD FAIL: SARIF property 'complexity' or 'CyclomaticComplexity' missing in complexity violation node. Missing compiler version drift?")

            if comp_val > max_complexity:
                msg = result.get("message", {}).get("text", "")

                # Extract location conservatively
                uri = ""
                line = 0
                for loc in result.get("locations", []):
                    ploc = loc.get("physicalLocation", {})
                    uri = ploc.get("artifactLocation", {}).get("uri", "")
                    line = ploc.get("region", {}).get("startLine", 0)
                    break

                violations.append(ComplexityViolation(
                    file=uri,
                    line=line,
                    function="unknown",
                    complexity=comp_val,
                    message=msg,
                ))

    return violations
