# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run` reads a project's `[sandbox]` by the name it is registered under, not its folder.

Proves: D-EXEC-02 FR-1

A project named `orders` in a folder `svc` asked for worktree isolation and ran without it: the
setting was looked up for a project called `svc`, which does not exist, and the lookup is
best-effort, so it stayed off without a word.

| Bucket | Case |
|---|---|
| Happy | a project whose name differs from its folder gets its isolation setting |
| Boundary | a project named like its folder still gets it |
| Degradation | not applicable — an unregistered folder has no settings to read |
| Hostile | not applicable — no input crosses a trust boundary |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration
runner = CliRunner()


@pytest.mark.parametrize("name", ["orders", "svc"])
def test_the_isolation_setting_is_read_for_the_registered_project(
    tmp_path: Path, name: str
) -> None:
    folder = tmp_path / "svc"
    folder.mkdir()
    assert runner.invoke(app, ["init", name, "--path", str(folder)]).exit_code == 0
    (folder / "specweaver.toml").write_text(
        "[sandbox]\nenforce_worktree_isolation = true\n", encoding="utf-8"
    )
    spec = folder / "specs" / "a_spec.md"
    spec.write_text("# A\n", encoding="utf-8")
    seen: dict[str, Any] = {}

    class _Runner:
        def __init__(self, _pipeline: Any, context: Any, **_kwargs: Any) -> None:
            seen["context"] = context

        async def run(self) -> None:
            raise SystemExit(0)

    with patch("specweaver.core.flow.engine.runner.PipelineRunner", _Runner):
        runner.invoke(app, ["run", "validate_only", str(spec), "--project", str(folder)])

    assert seen["context"].isolation.enforce_isolation is True
