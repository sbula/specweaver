from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

runner = CliRunner()

@pytest.fixture
def mock_dal_project(tmp_path: Path) -> Path:
    proj = tmp_path / "mock_dal_project"
    proj.mkdir()

    (proj / "tests").mkdir()
    (proj / "tests" / "unit").mkdir()

    # Write a dummy python file that triggers C06 (bare except) which is a WARN
    dummy_code = "def bad_func():\n    try:\n        pass\n    except:\n        pass\n"
    (proj / "tests" / "unit" / "test_dummy.py").write_text(dummy_code)

    # Create a custom pipeline that ONLY runs C06 so we don't fail on coverage/tests/tach
    pipeline_dir = proj / ".specweaver" / "pipelines"
    pipeline_dir.mkdir(parents=True)
    pipeline_yaml = "name: custom_warn_pipeline\nsteps:\n  - rule: C06\n    name: 'Check Bare Except'\n"
    (pipeline_dir / "custom_warn_pipeline.yaml").write_text(pipeline_yaml)

    return proj


def test_validation_check_enforces_strict_dal_failure(mock_dal_project: Path):
    """Test that `sw check` enforces Fail-at-end behavior with DAL_A targets."""

    # Configure DAL_A
    (mock_dal_project / "context.yaml").write_text("operational:\n  dal_level: DAL_A")

    # With DAL_A, is_strict is True, meaning warnings should trigger an exit(1)
    result = runner.invoke(app, [
        "check",
        "--pipeline", "custom_warn_pipeline",
        "--project", str(mock_dal_project),
        str(mock_dal_project / "tests" / "unit" / "test_dummy.py")
    ])

    # Since DAL_A is strict, warnings count as failures -> Exit code 1
    assert result.exit_code == 1
    assert "PASSED with warnings" in result.stdout or "FAILED" in result.stdout


def test_validation_check_allows_warnings_on_lenient_dal(mock_dal_project: Path):
    """Test that `sw check` allows warnings for DAL_E targets."""

    # Configure DAL_E
    (mock_dal_project / "context.yaml").write_text("operational:\n  dal_level: DAL_E")

    result = runner.invoke(app, [
        "check",
        "--pipeline", "custom_warn_pipeline",
        "--project", str(mock_dal_project),
        str(mock_dal_project / "tests" / "unit" / "test_dummy.py")
    ])

    # Since DAL_E is NOT strict, warnings don't trigger exit(1)
    assert result.exit_code == 0
    assert "PASSED with warnings" in result.stdout
