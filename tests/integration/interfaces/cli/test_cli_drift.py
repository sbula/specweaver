# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw drift check` end to end through the pipeline runner.

Proves: B-VAL-01 FR-6
Proves: C-FLOW-13 FR-9
Proves: B-FLOW-05 FR-3

Cited under `specweaver-dev` §3.2c, from `INT-US-10-SF01-MIG`. Mutant: the command renamed, so the
documented invocation no longer exists — 9 fail here and at e2e.

`--plan` is a REQUIRED option, and that is the shape of the FR-2 descope recorded in
`B-VAL-01_sf02_implementation_plan.md`: the plan is named by the caller, never resolved from the
file's lineage UUID.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli._core import get_db
from specweaver.interfaces.cli.main import app
from tests.fixtures.db_utils import register_test_project, set_test_active_project
from tests.scripted_llm import doubled_llm

runner = CliRunner()


@pytest.fixture
def dummy_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    proj = tmp_path / "dummy_proj"
    proj.mkdir()

    data_dir = proj / ".specweaver"
    data_dir.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))

    db = get_db()
    register_test_project(db, "dummy_proj", str(proj))
    set_test_active_project(db, "dummy_proj")

    plan_path = proj / "plan.yaml"
    plan_path.write_text("""
spec_path: "specs/test_spec.md"
spec_name: "Test"
spec_hash: "123"
timestamp: "2026-01-01T00:00:00Z"
file_layout:
  - path: "src/test.py"
    action: "create"
    purpose: "Test file"
tasks:
  - sequence_number: 1
    name: "Task 1"
    description: "Do it"
    files: ["src/test.py"]
    dependencies: []
    expected_signatures:
      "src/test.py":
        - name: "my_func"
          parameters: ["x", "y"]
          return_type: "int"
    """)

    src_dir = proj / "src"
    src_dir.mkdir()
    src_file = src_dir / "test.py"
    src_file.write_text("def my_func(x, y) -> int:\n    return x + y\n")
    return proj


def test_drift_check_success(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    result = runner.invoke(
        app,
        [
            "drift",
            "check",
            str(target_path),
            "--plan",
            str(plan_path),
            "--project",
            str(dummy_project),
        ],
    )
    assert result.exit_code == 0
    assert "signatures match specification" in result.stdout


def test_drift_check_failed(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    # Introduce error drift
    target_path.write_text("def bad_func() -> int:\n    return 0\n")

    result = runner.invoke(
        app,
        [
            "drift",
            "check",
            str(target_path),
            "--plan",
            str(plan_path),
            "--project",
            str(dummy_project),
        ],
    )
    assert result.exit_code == 42
    assert "AST Drift Detected" in result.stdout
    assert "missing_function" not in result.stdout  # Should say missing expected method my_func
    assert "my_func" in result.stdout


def test_drift_check_file_not_found(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    result = runner.invoke(
        app,
        [
            "drift",
            "check",
            "nonexistent.py",
            "--plan",
            str(plan_path),
            "--project",
            str(dummy_project),
        ],
    )
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_drift_check_warning(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    # Introduce warning drift (wrong parameter name)
    target_path.write_text("def my_func(a, b) -> int:\n    return a + b\n")

    result = runner.invoke(
        app,
        [
            "drift",
            "check",
            str(target_path),
            "--plan",
            str(plan_path),
            "--project",
            str(dummy_project),
        ],
    )
    # WARNING shouldn't crash with 1
    assert result.exit_code == 0
    assert "Warnings for test.py" in result.stdout
    assert "warning" in result.stdout


def test_drift_check_invalid_project(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    result = runner.invoke(
        app,
        [
            "drift",
            "check",
            str(target_path),
            "--plan",
            str(plan_path),
            "--project",
            "random/missing/dir",
        ],
    )
    assert result.exit_code == 1
    assert "Error:" in result.stdout


def test_drift_check_analyze(dummy_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"
    target_path.write_text("def missing() -> int: return 0\n")

    class MockAdapter:
        async def generate(self, *args: list[str], **kwargs: dict[str, str]) -> object:
            class MockResp:
                text = "Mock LLM Root Cause"

            return MockResp()

    with doubled_llm(MockAdapter()):
        result = runner.invoke(
            app,
            [
                "drift",
                "check",
                str(target_path),
                "--plan",
                str(plan_path),
                "--project",
                str(dummy_project),
                "--analyze",
            ],
        )
    assert result.exit_code == 42
    assert "LLM Root-Cause Analysis" in result.stdout
    assert "Mock LLM Root Cause" in result.stdout


_HOSTED_MACHINE = """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[roles]
default = "m@hosted"

[models."m"]
max_output = 100
usd_per_million_input = 1
usd_per_million_output = 1
thinking_in_output_cap = true

[brake]
hosted_spend_per_run = 100
tokens_per_run = 1000000
agent_turns = 5
"""


def test_drift_analyze_keeps_the_target_projects_private_rule(
    dummy_project: Path, tmp_path: Path
) -> None:
    import httpx2

    from tests.fake_http import fake_httpx2

    (dummy_project / ".specweaver" / "settings.toml").write_text(_HOSTED_MACHINE)
    (dummy_project / "specweaver.toml").write_text("[llm]\nprivate_only = true\n")
    other = tmp_path / "other"
    other.mkdir()
    register_test_project(get_db(), "other", str(other))
    set_test_active_project(get_db(), "other")
    target_path = dummy_project / "src" / "test.py"
    target_path.write_text("def missing() -> int: return 0\n")

    with fake_httpx2(lambda _request: httpx2.Response(500)) as seen:
        result = runner.invoke(
            app,
            [
                "drift",
                "check",
                str(target_path),
                "--plan",
                str(dummy_project / "plan.yaml"),
                "--project",
                str(dummy_project),
                "--analyze",
            ],
        )

    assert seen == []
    assert "private servers only" in " ".join(result.output.split())


_TINY_LIMIT_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 1000 }

[models."qwen3-coder-next"]
tokens_per_run = 50

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000000
agent_turns = 5
"""


def test_drift_analyze_stopped_by_the_brake_still_fails_on_drift(dummy_project: Path) -> None:
    import httpx2

    from tests.fake_http import fake_httpx2

    (dummy_project / ".specweaver" / "settings.toml").write_text(_TINY_LIMIT_MACHINE)
    target_path = dummy_project / "src" / "test.py"
    target_path.write_text("def missing() -> int: return 0\n")

    with fake_httpx2(lambda _request: httpx2.Response(500)) as seen:
        result = runner.invoke(
            app,
            [
                "drift",
                "check",
                str(target_path),
                "--plan",
                str(dummy_project / "plan.yaml"),
                "--project",
                str(dummy_project),
                "--analyze",
            ],
        )

    output = " ".join(result.output.split())
    assert seen == []
    assert result.exit_code == 42, result.output
    assert "signatures match" not in output
    assert "AST Drift Detected" in output
    assert 'models."qwen3-coder-next".tokens_per_run' in output
    assert "analysis failed" not in output
