# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E Test to ensure sw scan generates an operative tach.toml."""

import os
import subprocess
from pathlib import Path


def test_e2e_tach_sync_generates_valid_boundaries(tmp_path: Path):
    """E2E Test demonstrating tach sync and tach check execute seamlessly."""
    project_dir = tmp_path / "validating-tach-project"
    project_dir.mkdir()

    # 1. Setup mock python files ensuring context inferrer picks them up
    api_dir = project_dir / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "__init__.py").write_text("")
    (api_dir / "main.py").write_text("import src.core\n")

    core_dir = project_dir / "src" / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "__init__.py").write_text("")
    (core_dir / "logic.py").write_text("def hello(): pass\n")

    # Write a base constitution so init doesn't break
    (project_dir / "CONSTITUTION.md").write_text("# Project Constitution\n")

    # 2. Run sw init
    env = os.environ.copy()
    env["SPECWEAVER_DATA_DIR"] = str(tmp_path / "appdata")
    env["PYTHONIOENCODING"] = "utf-8"

    cli_cmd = ["python", "-c", "from specweaver.cli.main import app; app(prog_name='sw')"]

    subprocess.run(
        [*cli_cmd, "init", "validating-tach-project", "--path", str(project_dir)],
        env=env,
        check=True,
        capture_output=True,
    )

    # 3. Write explicit context.yamls
    (api_dir / "context.yaml").write_text(
        "name: src.api\nlevel: module\narchetype: orchestrator\nconsumes: [src.core]\n"
    )
    (core_dir / "context.yaml").write_text(
        "name: src.core\nlevel: module\narchetype: pure-logic\nconsumes: []\n"
    )

    # 4. Run sw scan to trigger the tach sync
    try:
        result = subprocess.run(
            [*cli_cmd, "scan"],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        stdout_str = e.stdout.replace("\n", " | ") if e.stdout else ""
        stderr_str = e.stderr.replace("\n", " | ") if e.stderr else ""
        raise Exception(f"Exit {e.returncode}. STDOUT: {stdout_str} STDERR: {stderr_str}") from e

    # 5. Assert output
    output = result.stdout + "\n" + result.stderr
    assert "Tach Sync" in output, f"Output was: {output}"

    # 6. Verify tach.toml exists physically
    tach_config = project_dir / "tach.toml"
    assert tach_config.exists()
    assert "src.api" in tach_config.read_text()

    # 7. Run tach check to ensure the generated file is perfectly valid
    tach_res = subprocess.run(
        ["tach", "check"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
    )

    # It should pass flawlessly
    assert tach_res.returncode == 0
    tach_output = tach_res.stdout + "\n" + tach_res.stderr
    assert "All modules validated" in tach_output or "validated" in tach_output
