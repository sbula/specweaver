from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app


def test_drift_check_rot_cmd_staged():
    runner = CliRunner()
    result = runner.invoke(app, ["drift", "check-rot", "--staged"])

    # Should exit cleanly (exit 0) since it's a stub in SF-1
    # It should print something acknowledging it's checking staged files
    assert result.exit_code == 0
    assert "Checking AST drift for staged files" in result.stdout


def test_drift_check_rot_cmd_no_staged():
    runner = CliRunner()
    # It requires --staged or defaults to False. If we want it to be explicit,
    # let's test what happens when not providing --staged
    result = runner.invoke(app, ["drift", "check-rot"])

    assert result.exit_code == 0
    assert "Checking AST drift for all target files" in result.stdout
