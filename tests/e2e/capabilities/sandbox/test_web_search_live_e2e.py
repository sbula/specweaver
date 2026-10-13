# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A review agent's web tools against the real internet: Tavily answers, a public page reads.

Proves: E-SENS-02 FR-1
Proves: E-SENS-02 FR-2
Proves: E-SENS-02 FR-5

Run nightly by `scripts/live.py`. The key is `TAVILY_API_KEY` in the real `~/.specweaver/keys.env`
(`scripts/live.py` names it in `SPECWEAVER_LIVE_KEYS`); its value is never printed. A missing key
fails rather than skips. One search costs one Tavily credit; the free plan has 1,000 a month.

| Bucket | Case |
|---|---|
| Happy | the settings files give the reviewer web_search; Tavily returns public URLs |
| Happy | read_url reads a real public page as text |
| Hostile | read_url refuses the cloud metadata address, with the network there |
| Degradation | no key: the run fails and says so |
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from specweaver.core.config.bootstrap.llm_settings_loader import load_keys, load_llm_settings
from specweaver.core.flow.handlers.review import _build_tool_dispatcher
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.resolve import RoleResolver
from specweaver.infrastructure.llm.router import ModelRouter

pytestmark = [pytest.mark.live, pytest.mark.e2e]

_SETTINGS = """\
[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = "m@local"

[search]
api_key_env = "TAVILY_API_KEY"
"""


@pytest.fixture
def tools(tmp_path: Path, _isolate_env: Path):  # type: ignore[no-untyped-def]
    real = os.environ.get("SPECWEAVER_LIVE_KEYS")
    if not real or not load_keys(Path(real)).get("TAVILY_API_KEY"):
        pytest.fail(f"TAVILY_API_KEY is not in {real}; run through scripts/live.py")
    shutil.copy2(real, _isolate_env / "keys.env")
    (_isolate_env / "settings.toml").write_text(_SETTINGS, encoding="utf-8")

    files = load_llm_settings(None)
    router = ModelRouter(RoleResolver(files, telemetry_project="live", budget=SpendBudget()))
    context = RunContext(
        model=ModelAccess(llm_router=router), project_path=tmp_path, spec_path=tmp_path / "s.md"
    )
    dispatcher = _build_tool_dispatcher(context, role="reviewer", adapter=object())
    assert dispatcher is not None
    return dispatcher


async def test_the_reviewer_searches_the_real_web(tools) -> None:  # type: ignore[no-untyped-def]
    # Proves: E-SENS-02 FR-5
    answer = await tools.execute(
        "web_search", {"query": "pydantic v2 strict mode documentation", "max_results": 3}
    )

    assert "error" not in answer, answer.get("error")
    results = answer["results"]
    assert 1 <= len(results) <= 3
    assert all(r["url"].startswith("https://") and r["title"] for r in results)


async def test_a_public_page_reads_and_the_metadata_address_does_not(tools) -> None:  # type: ignore[no-untyped-def]
    # Proves: E-SENS-02 FR-2
    page = await tools.execute("read_url", {"url": "https://example.com/"})
    assert "Example Domain" in page.get("content", ""), page

    refused = await tools.execute("read_url", {"url": "http://169.254.169.254/latest/meta-data/"})
    assert "not a public address" in refused["error"]
