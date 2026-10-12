# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The spend brake against real Gemini: one review goes through, one is stopped before sending.

Also: a secret in the project vault reaches Gemini masked.

Proves: B-FLOW-05 NFR-4
Proves: B-FLOW-07 FR-1, FR-2, FR-4
Proves: E-INTL-01 FR-2
Proves: E-INTL-01 FR-3
Proves: E-INTL-03 FR-1
Proves: E-INTL-03 FR-2

Run nightly by `scripts/live.py`. The key is `GEMINI_API_KEY` in the real `~/.specweaver/keys.env`,
copied into the test's data directory (`scripts/live.py` names it in `SPECWEAVER_LIVE_KEYS`); its value is never printed. A missing key fails rather than
skips: a live run that skips proves nothing and looks green. A provider that is
busy (503) or throttled (429) is retried up to five times, a minute apart; the brake caps each.

| Bucket | Case |
|---|---|
| Happy | a review under its limit reaches Gemini, gets a verdict, and its spend is recorded |
| Happy | a spec holding a vault secret: what is sent to Gemini holds only the mask |
| Happy | a code review sends the spec and the code to Gemini and gets a verdict |
| Boundary | a limit below one call's worst case stops the call; nothing is sent or recorded; two finished reviews give the next one a step limit |
| Degradation | a busy or throttled provider is retried, then fails naming the reason |
| Hostile | no key: the run fails and says so |
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.core.config.bootstrap.llm_settings_loader import load_keys
from specweaver.interfaces.cli.main import app

pytestmark = [pytest.mark.live, pytest.mark.e2e]

runner = CliRunner()


_MODEL = "gemini-3.8-flash"
_TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
#: Busy answers cost nothing; the free tier is often busy for minutes.
_ATTEMPTS = 5
_SPEC = "# Greeter\n\n## 1. Purpose\n\nReturn the text 'hello'.\n"


def _settings(limit_usd: float, extra: str = "") -> str:
    return (
        extra
        + f"""[servers.gemini]
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
    )


@pytest.fixture
def project(tmp_path: Path, _isolate_env: Path) -> Path:
    real = os.environ.get("SPECWEAVER_LIVE_KEYS")
    if not real or not load_keys(Path(real)).get("GEMINI_API_KEY"):
        pytest.fail(f"GEMINI_API_KEY is not in {real}; run through scripts/live.py")
    shutil.copy2(real, _isolate_env / "keys.env")
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


def _review(project: Path, data_dir: Path, limit_usd: float, extra: str = ""):
    (data_dir / "settings.toml").write_text(_settings(limit_usd, extra), encoding="utf-8")
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


def test_finished_reviews_give_the_next_one_a_step_limit(project: Path, _isolate_env: Path) -> None:
    from specweaver.core.config.database import Database
    from specweaver.infrastructure.llm.store import step_history_limit

    steps = "[step_limits]\npercentile = 90\nmin_steps = 2\n\n"
    for _ in range(2):
        result = _review(project, _isolate_env, 0.03, steps)
        assert "VERDICT: ACCEPTED" in result.output or "VERDICT: DENIED" in result.output, (
            result.output
        )

    limit = step_history_limit(
        Database(_isolate_env / "specweaver.db"),
        task_type="review",
        model=_MODEL,
        dal_level="DAL_C",
        unit="usd",
        steps=2,
        percentile=90,
    )

    assert limit is not None and 0 < limit < 0.03


_VAULT_TOKEN = "vault-tok-8f3k2m9q7z"


def _record_sent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Wrap the real SDK calls to record what they send; each call still reaches Gemini."""
    from google.genai.models import AsyncModels

    sent: list[str] = []
    for name in ("generate_content", "count_tokens"):
        real = getattr(AsyncModels, name)

        async def spy(self, *args, _real=real, **kwargs):
            sent.append(repr(kwargs.get("contents")) + repr(kwargs.get("config")))
            return await _real(self, *args, **kwargs)

        monkeypatch.setattr(AsyncModels, name, spy)
    return sent


def test_a_vault_secret_reaches_gemini_masked(
    project: Path, _isolate_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What leaves is recorded at the SDK; every call still goes to Gemini."""
    sent = _record_sent(monkeypatch)
    (project / ".specweaver" / "vault.env").write_text(f"DEPLOY_TOKEN={_VAULT_TOKEN}\n")
    (project / "greeter_spec.md").write_text(
        f"{_SPEC}\nThe service authenticates with the token {_VAULT_TOKEN}.\n", encoding="utf-8"
    )

    result = _review(project, _isolate_env, 0.03)

    assert "VERDICT" in result.output, result.output
    assert sent, "nothing was sent to Gemini"
    assert not [s for s in sent if _VAULT_TOKEN in s], "the vault secret left unmasked"
    assert any("***RESTRICTED***" in s for s in sent)


def test_a_code_review_reaches_gemini_with_spec_and_code(
    project: Path, _isolate_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _record_sent(monkeypatch)
    code = project / "greeter.py"
    code.write_text("def greet() -> str:\n    return 'hello'\n", encoding="utf-8")
    (_isolate_env / "settings.toml").write_text(_settings(0.03), encoding="utf-8")

    for attempt in range(_ATTEMPTS):
        result = runner.invoke(
            app,
            [
                "review",
                str(code),
                "--spec",
                str(project / "greeter_spec.md"),
                "--project",
                str(project),
            ],
        )
        if not any(mark in result.output for mark in _TRANSIENT) or attempt == _ATTEMPTS - 1:
            break
        time.sleep(60)

    assert "VERDICT: ACCEPTED" in result.output or "VERDICT: DENIED" in result.output, result.output
    assert any("return 'hello'" in s and "Return the text" in s for s in sent)
