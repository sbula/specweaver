# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A REST endpoint's call carries its role, so the role's own limit applies over REST too.

Proves: B-FLOW-05 FR-5

The seam: `interfaces.api` builds its router from the settings files; the router stamps the task;
the collector scopes the call by it.

| Bucket | Case |
|---|---|
| Happy | the implement endpoint's call counts against `roles.implement.spend_per_run` |
| Boundary | a role the file does not set falls back to `default`, and so does its limit |
| Degradation | not applicable — a missing setting is the endpoint's 500, proven elsewhere |
| Hostile | not applicable — no request input reaches the scope |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.infrastructure.llm.models import TaskType
from specweaver.interfaces.api.v1._llm import api_router

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[roles]
implement = { model = "m@hosted", max_output_tokens = 100, spend_per_run = 3 }
default = { model = "m@hosted", max_output_tokens = 100, spend_per_run = 7 }

[models."m"]
usd_per_million_input = 1.0
usd_per_million_output = 1.0
thinking_in_output_cap = true

[brake]
hosted_spend_per_run = 20
tokens_per_run = 1000000
agent_turns = 10
"""


@pytest.fixture
def _machine_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))


@pytest.mark.usefixtures("_machine_file")
@pytest.mark.parametrize(
    ("task", "role_key"),
    [
        (TaskType.IMPLEMENT, "roles.implement.spend_per_run"),
        (TaskType.REVIEW, "roles.default.spend_per_run"),
    ],
)
def test_an_endpoints_call_counts_against_its_roles_limit(
    tmp_path: Path, task: TaskType, role_key: str
) -> None:
    router = api_router(tmp_path, "demo", [task])

    routed = router.get_for_task(task)

    keys = {limit.key for limit in routed.adapter.scope(routed.config).limits}
    assert role_key in keys
