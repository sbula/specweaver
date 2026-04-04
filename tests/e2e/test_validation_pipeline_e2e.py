# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — sw check validation pipeline variants.

Exercises:
  - All 11 spec rules fire on a well-formed spec (test 15)
  - Domain profile narrows the active pipeline, changing which overrides apply (test 16)
  - Disabling a rule via --set skips that rule (test 17)
  - Code validation pipeline runs C01-C08 (test 18)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_proj_counter = 0


def _unique_name(prefix: str = "vp") -> str:
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


_GOOD_SPEC = """\
# greet_service

## 1. Purpose

Returns a personalized greeting for a given name.

## 2. Contract

```python
def greet(name: str) -> str:
    \"\"\"Return a greeting for the given name.\"\"\"
```

### Examples

```python
>>> greet("Alice")
"Hello, Alice!"
>>> greet("")
"Hello, World!"
```

## 3. Protocol

1. Accept a `name` parameter of type `str`.
2. If `name` is empty, use `"World"` as default.
3. Return the string `"Hello, {name}!"`.

## 4. Policy

### Error Handling

| Error Condition | Behavior |
|---|---|
| `name` is not a string | Raise `TypeError` |

### Limits

| Parameter | Default | Range |
|---|---|---|
| `name` length | N/A | 1-100 characters |

## 5. Boundaries

| Concern | Owned By |
|---|---|
| Input validation beyond type | Caller |
| Internationalization | Not in scope |

## Done Definition

- [ ] All unit tests pass with coverage >= 80%
- [ ] `greet("")` returns `"Hello, World!"`
- [ ] `TypeError` raised for non-string input
"""

# Code that passes most code rules (C01, C02-C03 skipped, C06, C07, C08)
_CLEAN_CODE = '''\
"""Greet service — clean implementation."""

from __future__ import annotations


def greet(name: str) -> str:
    """Return a greeting for the given name.

    Args:
        name: The name to greet.

    Returns:
        A greeting string like "Hello, Alice!".

    Raises:
        TypeError: If name is not a string.
    """
    if not isinstance(name, str):
        msg = f"Expected str, got {type(name).__name__}"
        raise TypeError(msg)
    name = name.strip()
    if not name:
        name = "World"
    return f"Hello, {name}!"
'''


def _init_project_with_spec(tmp_path: Path) -> tuple[Path, Path]:
    """Create an initialized project and write the canonical good spec."""
    project_dir = tmp_path / _unique_name("proj")
    project_dir.mkdir()
    result = runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])
    assert result.exit_code == 0

    spec = project_dir / "specs" / "greet_service_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(_GOOD_SPEC, encoding="utf-8")
    return project_dir, spec


# ===========================================================================
# Test 15: All 11 spec rules fire
# ===========================================================================


class TestValidateOnlyAllRulesFire:
    """sw check on a good spec with --level component shows all S01-S11 IDs."""

    def test_validate_only_all_rules_fire(self, tmp_path: Path) -> None:
        """Validate a complete spec — every spec rule ID should appear in output."""
        project_dir, spec = _init_project_with_spec(tmp_path)

        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--project", str(project_dir)],
        )

        # Exit code can be 0 (all pass) or 1 (some fail) — never a crash
        assert result.exit_code in (0, 1), f"check crashed: {result.output}"

        # All 11 spec rule IDs must appear in output
        for rule_id in [
            "S01",
            "S02",
            "S03",
            "S04",
            "S05",
            "S06",
            "S07",
            "S08",
            "S09",
            "S10",
            "S11",
        ]:
            assert rule_id in result.output, f"Rule {rule_id} missing from output:\n{result.output}"


# ===========================================================================
# Test 16: Profile-aware pipeline narrows/modifies rules
# ===========================================================================


class TestValidateOnlyWithProfileOverride:
    """Setting a domain profile changes the active pipeline for sw check."""

    def test_validate_only_with_profile_override(self, tmp_path: Path) -> None:
        """Set web-app profile → sw check uses web-app YAML (has relaxed S05/S03 thresholds).

        Verifies that:
        - sw config set-profile web-app succeeds
        - sw check --level component picks up the profile-based pipeline
        - All spec rules still fire (web-app profile extends default, doesn't remove rules)
        - The profile name appears in output or the command completes normally
        """
        project_dir, spec = _init_project_with_spec(tmp_path)

        # Activate the project and set the web-app domain profile
        # sw config set-profile acts on the active project (no --project flag)
        runner.invoke(app, ["use", project_dir.name])
        set_profile = runner.invoke(
            app,
            ["config", "set-profile", "web-app"],
        )
        assert set_profile.exit_code == 0, f"set-profile failed: {set_profile.output}"

        # Run sw check — should auto-select validation_spec_web_app pipeline
        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--project", str(project_dir)],
        )
        assert result.exit_code in (0, 1), f"check crashed: {result.output}"

        # All rules should still fire (web-app extends default)
        for rule_id in ["S01", "S03", "S05"]:
            assert rule_id in result.output, (
                f"Rule {rule_id} missing with web-app profile:\n{result.output}"
            )

        # Explicitly passing --pipeline beats the profile
        explicit_result = runner.invoke(
            app,
            [
                "check",
                str(spec),
                "--pipeline",
                "validation_spec_default",
                "--project",
                str(project_dir),
            ],
        )
        assert explicit_result.exit_code in (0, 1), (
            f"explicit pipeline check crashed: {explicit_result.output}"
        )
        assert "S01" in explicit_result.output


# ===========================================================================
# Test 17: Disable a rule via --set → that rule is skipped
# ===========================================================================


class TestValidateOnlyWithDisableOverride:
    """Using --set S01.enabled=false skips S01 from the output."""

    def test_validate_only_with_disable_override(self, tmp_path: Path) -> None:
        """Disable S01 via --set → S01 not present in check output."""
        project_dir, spec = _init_project_with_spec(tmp_path)

        # First run without disable — S01 must appear
        result_with = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--project", str(project_dir)],
        )
        assert "S01" in result_with.output, "S01 should appear without disable flag"

        # Now disable S01 via --set
        result_without = runner.invoke(
            app,
            [
                "check",
                str(spec),
                "--level",
                "component",
                "--project",
                str(project_dir),
                "--set",
                "S01.enabled=false",
            ],
        )
        assert result_without.exit_code in (0, 1), (
            f"check with disable crashed: {result_without.output}"
        )
        # S01 should NOT appear in results when disabled
        assert "S01" not in result_without.output, (
            f"S01 should be absent when disabled:\n{result_without.output}"
        )
        # Other rules should still fire
        assert "S02" in result_without.output or "S03" in result_without.output, (
            "Other rules should still run when S01 is disabled"
        )


# ===========================================================================
# Test 18: Code validation pipeline runs C01-C08
# ===========================================================================


class TestCodeValidationPipeline:
    """sw check --level code fires C01-C08 code rules on a Python file."""

    def test_code_validation_pipeline(self, tmp_path: Path) -> None:
        """Check a clean Python file at code level — all Cx rule IDs appear."""
        project_dir = tmp_path / _unique_name("proj")
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        # Write a reasonably clean Python file
        code_file = project_dir / "src" / "greet_service.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text(_CLEAN_CODE, encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", str(code_file), "--level", "code", "--project", str(project_dir)],
        )
        assert result.exit_code in (0, 1), f"code check crashed: {result.output}"

        # C01 (syntax) always fires; others may or may not depending on file
        assert "C01" in result.output, f"C01 missing from code check:\n{result.output}"

        # At least the static rules that don't require test runners should appear
        for rule_id in ["C06", "C07", "C08"]:
            assert rule_id in result.output, (
                f"Rule {rule_id} missing from code check:\n{result.output}"
            )

    def test_code_validation_detects_violations(self, tmp_path: Path) -> None:
        """Code with known violations → those rules report FAIL."""
        project_dir = tmp_path / _unique_name("proj")
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        # Code that violates C06 (bare except) and C07 (orphan TODO)
        bad_code = (
            '"""Bad module."""\n\n'
            "# TODO: fix this later\n\n\n"
            "def broken() -> None:\n"
            "    try:\n"
            "        pass\n"
            "    except:\n"
            '        print("caught")\n'
        )
        code_file = project_dir / "src" / "bad_module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text(bad_code, encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", str(code_file), "--level", "code", "--project", str(project_dir)],
        )
        # Should report failures (exit code 1)
        assert result.exit_code == 1 or "FAIL" in result.output
        assert "C06" in result.output or "C07" in result.output, (
            f"Expected C06 or C07 violation in output:\n{result.output}"
        )


# ===========================================================================
# Test 19: AST Drift Engine validates pipeline boundaries (Pending SF-2)
# ===========================================================================


class TestCodeValidationDriftEngine:
    """sw check --level code interfaces with the AST Drift Engine."""

    def test_code_validation_method_drift(self, tmp_path: Path) -> None:
        """E5: Validate sw drift check FAILs when the generated codebase drops a planned method."""
        project_dir, _spec = _init_project_with_spec(tmp_path)

        # Write a plan.yaml
        plan_path = project_dir / "plan.yaml"
        plan_path.write_text("""
spec_path: "specs/greet_service_spec.md"
spec_name: "Test"
spec_hash: "123"
timestamp: "2026-01-01T00:00:00Z"
file_layout:
  - path: "src/greet.py"
    action: "create"
    purpose: "Greeting module"
tasks:
  - sequence_number: 1
    name: "Task 1"
    description: "Do it"
    files: ["src/greet.py"]
    dependencies: []
    expected_signatures:
      "src/greet.py":
        - name: "missing_method"
          parameters: []
          return_type: "None"
""")
        code_file = project_dir / "src" / "greet.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("def unrelated():\n    pass\n")

        result = runner.invoke(
            app,
            [
                "drift",
                "check",
                str(code_file),
                "--plan",
                str(plan_path),
                "--project",
                str(project_dir),
            ],
        )
        assert result.exit_code == 1
        assert "AST Drift Detected" in result.stdout
        assert "missing_method" in result.stdout

    def test_code_validation_workspace_drift(self, tmp_path: Path) -> None:
        """E6: Validate sw drift check FAILs when the generated codebase is missing an entire file."""
        project_dir, _spec = _init_project_with_spec(tmp_path)

        plan_path = project_dir / "plan.yaml"
        plan_path.write_text("""
spec_path: "specs/greet_service_spec.md"
spec_name: "Test"
spec_hash: "123"
timestamp: "2026-01-01T00:00:00Z"
file_layout:
  - path: "src/missing.py"
    action: "create"
    purpose: "Test"
tasks:
  - sequence_number: 1
    name: "missing"
    description: "m"
    files: ["src/missing.py"]
""")
        # Target file does not exist
        missing_file = project_dir / "src" / "missing.py"
        result = runner.invoke(
            app,
            [
                "drift",
                "check",
                str(missing_file),
                "--plan",
                str(plan_path),
                "--project",
                str(project_dir),
            ],
        )
        assert result.exit_code == 1
        assert "File not found" in result.stdout

    def test_code_validation_parameter_drift(self, tmp_path: Path) -> None:
        """E7: Validate sw drift check raises WARNING end-to-end for mismatched parameters."""
        project_dir, _spec = _init_project_with_spec(tmp_path)

        plan_path = project_dir / "plan.yaml"
        plan_path.write_text("""
spec_path: "specs/greet_service_spec.md"
spec_name: "Test"
spec_hash: "123"
timestamp: "2026-01-01T00:00:00Z"
file_layout:
  - path: "src/greet.py"
    action: "create"
    purpose: "Greeting module"
tasks:
  - sequence_number: 1
    name: "Task 1"
    description: "Do it"
    files: ["src/greet.py"]
    dependencies: []
    expected_signatures:
      "src/greet.py":
        - name: "my_func"
          parameters: ["x"]
          return_type: "int"
""")
        code_file = project_dir / "src" / "greet.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        # Differing parameters (y instead of x)
        code_file.write_text("def my_func(y) -> int:\n    return 0\n")

        result = runner.invoke(
            app,
            [
                "drift",
                "check",
                str(code_file),
                "--plan",
                str(plan_path),
                "--project",
                str(project_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Warnings for greet.py" in result.stdout
        assert "warning" in result.stdout
