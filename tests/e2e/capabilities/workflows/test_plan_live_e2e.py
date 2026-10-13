# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real Gemini writes a plan the schema accepts, saved beside the spec.

Proves: D-INTL-03 FR-2

Run nightly by `scripts/live.py`. The key is `GEMINI_API_KEY` in the real `~/.specweaver/keys.env`
(`scripts/live.py` names it in `SPECWEAVER_LIVE_KEYS`); its value is never printed. A missing key
fails rather than skips. A failed run is retried up to five times, a minute apart: a busy (503)
or throttled (429) provider shows only in the log.

| Bucket | Case |
|---|---|
| Happy | a plan-only run against real Gemini saves a `PlanArtifact` with at least one file |
| Degradation | a busy provider is retried, then the run fails naming the reason |
| Hostile | no key: the run fails and says so |
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specweaver.core.config.bootstrap.llm_settings_loader import load_keys
from specweaver.interfaces.cli.main import app
from specweaver.workflows.planning.models import PlanArtifact

pytestmark = [pytest.mark.live, pytest.mark.e2e]

runner = CliRunner()

_MODEL = "gemini-3.8-flash"
_SETTINGS = f"""[servers.gemini]
kind = "gemini"
api_key_env = "GEMINI_API_KEY"
private = false
max_parallel = 1

[roles]
default = {{ model = "{_MODEL}@gemini", max_output_tokens = 3000 }}

[brake]
hosted_spend_per_run = 0.08
tokens_per_run = 100000
agent_turns = 10
"""
_SPEC = """# Greeter

## 1. Purpose

Return a greeting for a person's name.

## 2. Contract

```python
def greet(name: str) -> str: ...
```

`greet("Ada")` MUST return `"Hello, Ada"`; `greet("")` MUST raise `ValueError`.
"""
_PIPELINE = """name: plan_only
steps:
  - name: plan_spec
    action: plan
    target: spec
"""


def test_gemini_writes_a_valid_plan(tmp_path: Path, _isolate_env: Path) -> None:
    # Proves: D-INTL-03 FR-2
    real = os.environ.get("SPECWEAVER_LIVE_KEYS")
    if not real or not load_keys(Path(real)).get("GEMINI_API_KEY"):
        pytest.fail(f"GEMINI_API_KEY is not in {real}; run through scripts/live.py")
    shutil.copy2(real, _isolate_env / "keys.env")
    (_isolate_env / "settings.toml").write_text(_SETTINGS, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "live-plan", "--path", str(project)]).exit_code == 0
    (project / "specs" / "greeter_spec.md").write_text(_SPEC, encoding="utf-8")
    (project / "plan_only.yaml").write_text(_PIPELINE, encoding="utf-8")

    for attempt in range(5):
        result = runner.invoke(
            app,
            [
                "run",
                str(project / "plan_only.yaml"),
                "specs/greeter_spec.md",
                "--project",
                str(project),
            ],
        )
        if result.exit_code == 0 or attempt == 4:  # a busy model shows only in the log
            break
        time.sleep(60)

    assert result.exit_code == 0, result.output
    data = YAML(typ="safe").load((project / "specs" / "greeter_spec_plan.yaml").read_text())
    plan = PlanArtifact.model_validate(data)
    assert plan.file_layout
