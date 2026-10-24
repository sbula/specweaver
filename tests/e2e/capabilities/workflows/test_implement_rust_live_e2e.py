# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real Gemini and real cargo: `sw implement` on a Rust crate works on Rust files end to end.

Proves: TECH-078 FR-1
Proves: TECH-078 FR-3
Proves: TECH-078 FR-4

The demo of `TECH-078` (its design, "Works For Real"). Run nightly by `scripts/live.py`; the key is
`GEMINI_API_KEY` in the real `~/.specweaver/keys.env`, never printed. A run is retried only while
nothing was generated (a busy 503 or a throttled 429), up to five times a minute apart: a full run
costs several Gemini requests of the nightly 20. Whether the model's own tests pass is the model's
quality, not what this proves.

| Bucket | Case |
|---|---|
| Happy | the code and the tests land at `src/greeter.rs` and `tests/greeter.rs`; `lib.rs` declares the module |
| Boundary | cargo runs the task's tests; C02 and C03 judge the Rust file by its Rust tests |
| Degradation | the quota stops the run: skipped as `provider quota` by the e2e conftest |
| Hostile | no key: the run fails and says so |
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.core.config.bootstrap.llm_settings_loader import load_keys
from specweaver.interfaces.cli.main import app
from tests.e2e.gemini_budget import BUDGET

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
hosted_spend_per_run = 0.10
tokens_per_run = 150000
agent_turns = 10
"""
_SPEC = """# Greeter

## 1. Purpose

Return a greeting for a person's name.

## 2. Contract

```rust
pub fn greet(name: &str) -> Result<String, String>
```

`greet("Ada")` MUST return `Ok("Hello, Ada")`; `greet("")` MUST return `Err`.
"""


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
def test_sw_implement_on_a_rust_crate_with_real_gemini(tmp_path: Path, _isolate_env: Path) -> None:
    real = os.environ.get("SPECWEAVER_LIVE_KEYS")
    if not real or not load_keys(Path(real)).get("GEMINI_API_KEY"):
        pytest.fail(f"GEMINI_API_KEY is not in {real}; run through scripts/live.py")
    shutil.copy2(real, _isolate_env / "keys.env")
    (_isolate_env / "settings.toml").write_text(_SETTINGS, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "live-rust", "--path", str(project)]).exit_code == 0
    (project / "Cargo.toml").write_text(
        '[package]\nname = "greet"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8"
    )
    (project / "specs" / "greeter_spec.md").write_text(_SPEC, encoding="utf-8")

    code, tests = project / "src" / "greeter.rs", project / "tests" / "greeter.rs"
    for attempt in range(5):
        result = runner.invoke(
            app,
            ["implement", str(project / "specs" / "greeter_spec.md"), "--project", str(project)],
        )
        generated = code.is_file() and tests.is_file()
        if generated or BUDGET.stopped or attempt == 4:  # busy shows only in the log
            break
        time.sleep(60)

    output = " ".join(result.output.split())
    assert code.is_file(), output
    assert "pub fn greet" in code.read_text(encoding="utf-8"), output
    assert tests.is_file(), output
    assert "mod greeter" in (project / "src" / "lib.rs").read_text(encoding="utf-8"), output
    ran = re.search(r"tests: (\d+) passed, (\d+) failed", output)
    assert ran and int(ran[1]) + int(ran[2]) > 0, output
    assert re.search(r"code validation: \d+/2 rules passed", output), output
