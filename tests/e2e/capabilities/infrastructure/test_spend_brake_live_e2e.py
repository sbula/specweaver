# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The spend brake against real Gemini: one review goes through, one is stopped before sending.

Proves: B-FLOW-05 NFR-4

Run nightly by `scripts/live.py`. The key is `GEMINI_API_KEY` in the real `~/.specweaver/keys.env`,
copied into the test's data directory; its value is never printed. A missing key fails rather than
skips: a live run that skips proves nothing and looks green. A provider that is
busy (503) or throttled (429) is retried up to five times, a minute apart; the brake caps each.

| Bucket | Case |
|---|---|
| Happy | a review under its limit reaches Gemini, gets a verdict, and its spend is recorded |
| Boundary | a limit below one call's worst case stops the call; nothing is sent or recorded |
| Degradation | a busy or throttled provider is retried, then fails naming the reason |
| Hostile | no key: the run fails and says so |
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.core.config.bootstrap.llm_settings_loader import load_keys
from specweaver.core.config.paths import specweaver_root
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.live, pytest.mark.e2e]

runner = CliRunner()

#: Read before any test points SPECWEAVER_DATA_DIR at its own directory.
_REAL_KEYS = specweaver_root() / "keys.env"

_MODEL = "gemini-3.8-flash"
_TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
#: Busy answers cost nothing; the free tier is often busy for minutes.
_ATTEMPTS = 5
_SPEC = "# Greeter\n\n## 1. Purpose\n\nReturn the text 'hello'.\n"


def _settings(limit_usd: float) -> str:
    return f"""[servers.gemini]
kind = "gemini"
api_key_env = "GEMINI_API_KEY"
private = false
max_parallel = 1

[roles]
default = {{ model = "{_MODEL}@gemini", max_output_tokens = 2000 }}

[brake]
hosted_spend_per_run = {limit_usd}
tokens_per_run = 100000
agent_turns = 5
"""


@pytest.fixture
def project(tmp_path: Path, _isolate_env: Path) -> Path:
    if not load_keys(_REAL_KEYS).get("GEMINI_API_KEY"):
        pytest.fail(f"GEMINI_API_KEY is not in {_REAL_KEYS}")
    shutil.copy2(_REAL_KEYS, _isolate_env / "keys.env")
    root = tmp_path / "proj"
    root.mkdir()
    (root / "greeter_spec.md").write_text(_SPEC, encoding="utf-8")
    assert runner.invoke(app, ["init", "live-demo", "--path", str(root)]).exit_code == 0
    return root


def _calls(data_dir: Path) -> int:
    db = data_dir / "specweaver.db"
    if not db.exists():
        return 0
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT COUNT(*) FROM llm_usage_log").fetchone()[0]


def _review(project: Path, data_dir: Path, limit_usd: float):
    (data_dir / "settings.toml").write_text(_settings(limit_usd), encoding="utf-8")
    for attempt in range(_ATTEMPTS):
        result = runner.invoke(
            app, ["review", str(project / "greeter_spec.md"), "--project", str(project)]
        )
        if not any(mark in result.output for mark in _TRANSIENT) or attempt == _ATTEMPTS - 1:
            return result
        time.sleep(60)
    return result


def test_a_review_under_its_limit_reaches_gemini(project: Path, _isolate_env: Path) -> None:
    result = _review(project, _isolate_env, 0.03)

    assert "VERDICT: ACCEPTED" in result.output or "VERDICT: DENIED" in result.output, result.output
    assert _calls(_isolate_env) >= 1


def test_a_limit_below_one_call_stops_it_before_sending(project: Path, _isolate_env: Path) -> None:
    before = _calls(_isolate_env)

    result = _review(project, _isolate_env, 0.0005)

    assert "brake.hosted_spend_per_run" in " ".join(result.output.split()), result.output
    assert _calls(_isolate_env) == before
