# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check` on a spec: a `## Scenarios` section is optional, and one that is there must be valid.

Proves: B-FLOW-01 FR-1

| Bucket | Case |
|---|---|
| Happy | a spec as `sw draft` writes it, without Scenarios: S07 passes |
| Boundary | valid scenario YAML: S07 passes |
| Degradation | not applicable: no service is called |
| Hostile | broken scenario YAML: S07 fails and `sw check` exits 1 |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_SPEC = """# Greeter

## 1. Purpose

Greets a user by name.

## 2. Contract

```python
def greet(name: str) -> str: ...
```

- `greet("Ada")` MUST return `"Hello, Ada"`.
- `greet("")` MUST raise ValueError.

## 3. Protocol

1. Check the name. 2. Return the greeting.

## 4. Policy

| Error | Behavior |
|:---|:---|
| Empty name | Raise ValueError |

## 5. Boundaries

| Concern | Owned By |
|:---|:---|
| I/O | Caller |

## Done Definition

- [ ] Tested
"""


def _s07(tmp_path: Path, extra: str = "") -> tuple[str, int]:
    assert runner.invoke(app, ["init", "greet", "--path", str(tmp_path)]).exit_code == 0
    spec = tmp_path / "specs" / "greeter_spec.md"
    spec.write_text(_SPEC + extra, encoding="utf-8")
    result = runner.invoke(app, ["check", str(spec), "--project", str(tmp_path)])
    line = next(ln for ln in result.output.splitlines() if "S07" in ln)
    return line, result.exit_code


def test_a_drafted_spec_without_scenarios_passes_s07(tmp_path: Path) -> None:
    # Proves: B-FLOW-01 FR-1
    line, _ = _s07(tmp_path)
    assert "PASS" in line.upper(), line


def test_valid_scenarios_pass_s07(tmp_path: Path) -> None:
    scenarios = (
        "\n## Scenarios\n\n```yaml\n- name: happy\n  function_under_test: greet\n"
        "  input_summary: Ada\n  expected_behavior: returns Hello, Ada\n```\n"
    )
    line, _ = _s07(tmp_path, scenarios)
    assert "PASS" in line.upper(), line


def test_broken_scenarios_fail_the_check(tmp_path: Path) -> None:
    # Proves: B-FLOW-01 FR-1
    line, code = _s07(tmp_path, "\n## Scenarios\n\n```yaml\n- name: [broken\n```\n")
    assert "FAIL" in line.upper(), line
    assert code == 1
