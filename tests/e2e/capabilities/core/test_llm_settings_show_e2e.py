# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw config show` — what each LLM setting is, and where it came from (US-16 paths P4, P7).

Proves: C-FLOW-13 FR-3, FR-4, FR-5, FR-9
Proves: B-FLOW-07 FR-8, B-FLOW-07 FR-9

| Bucket | Case |
|---|---|
| Happy | machine and project files → each role with its value and origin |
| Boundary | no settings files at all → every brake value shown as unset; a set one shows its line |
| Degradation | a typo in the machine file → exit 1 naming the file and the line (P4) |
| Hostile | a project file that defines a server → exit 1, told to use the machine file (P7) |
| Hostile | a private-only project with a role on a hosted server → exit 1, naming the rule (P3) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
draft = "qwen3-coder-next@gb10"
"""


def _project(tmp_path: Path, llm_section: str = "") -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    if llm_section:
        (project / "specweaver.toml").write_text(llm_section, encoding="utf-8")
    result = runner.invoke(app, ["init", "show-demo", "--path", str(project)])
    assert result.exit_code == 0, result.output
    return project


def test_each_value_shows_where_it_came_from(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path, '[llm.roles]\nimplement = "qwen3-coder-next@gb10"\n')

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "roles.draft = qwen3-coder-next@gb10")
    draft_line = _MACHINE.splitlines().index('draft = "qwen3-coder-next@gb10"') + 1
    assert shows(result.output, f"{_isolate_env / 'settings.toml'}:{draft_line}")
    assert shows(result.output, "roles.implement = qwen3-coder-next@gb10")
    assert shows(result.output, "specweaver.toml:2")


def test_without_files_the_brake_values_are_unset(tmp_path: Path, _mock_db: Database) -> None:
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    for key in ("hosted_spend_per_run", "tokens_per_run", "agent_turns"):
        assert shows(
            result.output, f"brake.{key} = unset — required by any command that calls a model"
        )
    assert not shows(result.output, "brake.hosted_spend_per_run = 20")


def test_a_set_brake_value_shows_its_line(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    text = _MACHINE + "\n[brake]\nhosted_spend_per_run = 20\n"
    (_isolate_env / "settings.toml").write_text(text, encoding="utf-8")
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "brake.hosted_spend_per_run = 20")
    line = text.splitlines().index("hosted_spend_per_run = 20") + 1
    assert shows(result.output, f"{_isolate_env / 'settings.toml'}:{line}")


def test_a_typo_in_the_machine_file_stops_with_its_line(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(
        _MACHINE.replace("max_parallel = 4", "max_paralel = 4"), encoding="utf-8"
    )
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), result.exception  # a refusal, not a crash
    typo_line = _MACHINE.splitlines().index("max_parallel = 4") + 1
    assert shows(result.output, f"{_isolate_env / 'settings.toml'}:{typo_line}")
    assert shows(result.output, "max_paralel")


def test_a_project_cannot_define_a_server(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path, '[llm.servers.evil]\nkind = "openai-compatible"\nbase_url = "http://evil"\n')

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    assert shows(result.output, "machine settings file")


def test_a_project_without_a_root_path_still_shows_the_machine_settings(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path, monkeypatch
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)
    from specweaver.interfaces.cli import _core

    class _RegistryWithoutRoot:
        def get_active_project(self) -> str:
            return "show-demo"

        def get_project(self, name: str) -> dict:
            return {"name": name, "root_path": None}

    monkeypatch.setattr(_core, "run_repo_op", lambda fn: fn(_RegistryWithoutRoot()))

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "roles.draft = qwen3-coder-next@gb10")


def test_a_private_project_with_a_hosted_role_is_refused(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    machine = (
        _MACHINE + '\n[servers.anthropic]\nkind = "anthropic"\nprivate = false\nmax_parallel = 3\n'
    )
    (_isolate_env / "settings.toml").write_text(machine, encoding="utf-8")
    _project(
        tmp_path, '[llm]\nprivate_only = true\n\n[llm.roles]\nreview = "claude-opus@anthropic"\n'
    )

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    assert shows(result.output, "specweaver.toml:2")
    assert shows(result.output, "review")


def test_a_role_shows_the_output_limit_and_sampling_a_call_uses(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "roles.draft.max_output_tokens = 65536 (catalogue)")
    assert shows(result.output, "roles.draft.top_k = 40 (catalogue)")
    assert shows(result.output, "roles.default = unset")


def test_a_value_the_server_never_receives_says_so(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    machine = (
        _MACHINE
        + '\n[servers.openai]\nkind = "openai"\nprivate = false\nmax_parallel = 2\n'
        + '\n[roles.review]\nmodel = "gpt-5.4@openai"\nmax_output_tokens = 2000\ntemperature = 0.3\n'
    )
    (_isolate_env / "settings.toml").write_text(machine, encoding="utf-8")
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "roles.review.temperature = 0.3 — not sent: openai ignores it")
    assert shows(result.output, "roles.draft.temperature = 1.0 (catalogue)")


def test_step_limits_are_shown_with_their_lines(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    text = _MACHINE + "\n[step_limits]\npercentile = 90\nmin_steps = 10\n"
    (_isolate_env / "settings.toml").write_text(text, encoding="utf-8")
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    line = text.splitlines().index("percentile = 90") + 1
    assert shows(
        result.output, f"step_limits.percentile = 90 ({_isolate_env / 'settings.toml'}:{line})"
    )
    assert shows(result.output, "step_limits.min_steps = 10")


def test_without_step_limits_show_says_they_are_off(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert shows(result.output, "step_limits = off — [step_limits] is not set")
