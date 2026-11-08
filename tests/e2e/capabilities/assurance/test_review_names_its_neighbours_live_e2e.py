# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw review` on a module with a neighbour, against real Gemini: the request names the neighbour.

Proves: TECH-088 FR-2

The live demo of `TECH-088`. Before it, `sw review` failed with `AttributeError` on any project whose
`context.yaml` gave the spec's module a neighbour. This asserts on the request and the run, never on
the model's wording (the user, 2026-11-08): what left for Gemini names `payments` as a direct
dependency, and the exit code is the one the run's own verdict gives.

Run nightly by `scripts/live.py`: one try, at most two Gemini requests (`agent_turns = 2`), no
retry (the user, 2026-11-08). The first request is saved to `.tmp/live/`, so a failure shows what was
sent. A missing key fails rather than skips.

| Bucket | Case |
|---|---|
| Happy | the first request carries `payments (direct dependency): Moves money.`; ACCEPTED exits 0 |
| Boundary | the model still calls tools after two rounds: an ERROR naming the round limit, exit 1 |
| Degradation | a busy or throttled provider: an ERROR naming the provider, exit 1; the quota: skipped |
| Hostile | a crash, or an ERROR for any other reason, fails the test |
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.core.config.bootstrap.llm_settings_loader import load_keys
from specweaver.interfaces.cli.main import app

pytestmark = [pytest.mark.live, pytest.mark.e2e]

runner = CliRunner()

_NEIGHBOUR = "payments (direct dependency): Moves money."
_SETTINGS = """[servers.gemini]
kind = "gemini"
api_key_env = "GEMINI_API_KEY"
private = false
max_parallel = 1

[roles]
default = { model = "gemini-3.8-flash@gemini", max_output_tokens = 2000 }

[brake]
hosted_spend_per_run = 0.03
tokens_per_run = 100000
agent_turns = 2
"""
#: Why an ERROR verdict may come from a healthy run: the turn limit, or the provider.
_EXPECTED_ERRORS = ("still calling tools after", "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")
_SAVED = Path(__file__).resolve().parents[4] / ".tmp" / "live" / "review_names_its_neighbours.txt"
_SPEC = (
    "# billing\n\n## 1. Purpose\n\nBills customers through payments.\n\n"
    "## 2. Contract\n\n```python\ndef bill() -> None: ...\n```\n"
)


@pytest.fixture
def shop(tmp_path: Path, _isolate_env: Path) -> Path:
    real = os.environ.get("SPECWEAVER_LIVE_KEYS")
    if not real or not load_keys(Path(real)).get("GEMINI_API_KEY"):
        pytest.fail(f"GEMINI_API_KEY is not in {real}; run through scripts/live.py")
    shutil.copy2(real, _isolate_env / "keys.env")
    (_isolate_env / "settings.toml").write_text(_SETTINGS, encoding="utf-8")

    root = tmp_path / "shop"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "billing_spec.md").write_text(_SPEC, encoding="utf-8")
    for name, text in (
        (
            "billing",
            "name: billing\npurpose: Bills customers.\narchetype: pure-logic\n"
            "consumes:\n  - payments\n",
        ),
        ("payments", "name: payments\npurpose: Moves money.\narchetype: adapter\n"),
    ):
        (root / name).mkdir()
        (root / name / "context.yaml").write_text(text, encoding="utf-8")
    assert runner.invoke(app, ["init", "shop", "--path", str(root)]).exit_code == 0
    return root


def _recording_requests(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What each `generate_content` call sends; every call still reaches Gemini."""
    from google.genai.models import AsyncModels

    sent: list[str] = []
    real = AsyncModels.generate_content

    async def spy(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        sent.append(repr(kwargs.get("contents")))
        if len(sent) == 1:
            _SAVED.parent.mkdir(parents=True, exist_ok=True)
            _SAVED.write_text(sent[0], encoding="utf-8")
        return await real(self, *args, **kwargs)

    monkeypatch.setattr(AsyncModels, "generate_content", spy)
    return sent


def test_the_request_names_the_neighbour(shop: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _recording_requests(monkeypatch)
    spec = str(shop / "specs" / "billing_spec.md")

    result = runner.invoke(app, ["review", spec, "--project", str(shop)])

    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"the review crashed: {result.exception!r}\n{result.output}"
    )
    assert sent, f"no request reached Gemini\n{result.output}"
    assert _NEIGHBOUR in sent[0], f"the first request does not name the neighbour; see {_SAVED}"
    if "VERDICT: ERROR" in result.output:
        assert any(reason in result.output for reason in _EXPECTED_ERRORS), (
            f"an ERROR from neither the turn limit nor the provider\n{result.output}"
        )
    accepted = "VERDICT: ACCEPTED" in result.output
    assert result.exit_code == (0 if accepted else 1), (
        f"exit {result.exit_code} does not match the verdict\n{result.output}"
    )
