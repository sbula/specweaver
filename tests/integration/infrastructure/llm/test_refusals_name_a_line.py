# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A refusal of the resolved settings names the line to fix, never line 0.

Proves: C-FLOW-13 FR-4

| Bucket | Case |
|---|---|
| Happy | not applicable — a usable file is proven by the router tests |
| Boundary | an unpriced hosted model names its role's line |
| Degradation | a key variable that is not set names its server's line |
| Hostile | not applicable — the file is the user's own |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.router import build_router

pytestmark = pytest.mark.integration

_HOSTED = """\
[servers.cloud]
kind = "openai-compatible"
base_url = "http://cloud.example/v1"
private = false
max_parallel = 2
api_key_env = "CLOUD_KEY"

[roles]
review = { model = "unpriced-model@cloud", max_output_tokens = 100 }

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000
agent_turns = 5
"""


def _refusal(monkeypatch, *, key_set: bool) -> SettingsFileError:
    if key_set:
        monkeypatch.setenv("CLOUD_KEY", "set-0123456789")
    else:
        monkeypatch.delenv("CLOUD_KEY", raising=False)
    files = LlmSettingsFiles.from_texts(
        machine_text=_HOSTED, machine_source="settings.toml", project_text="", project_source="-"
    )
    with pytest.raises(SettingsFileError) as caught:
        build_router(files, project="demo", roles=[TaskType.REVIEW]).get_for_task(TaskType.REVIEW)
    return caught.value


def _line(text: str) -> int:
    return _HOSTED.splitlines().index(text) + 1


def test_an_unpriced_model_names_a_line(monkeypatch) -> None:
    refusal = _refusal(monkeypatch, key_set=True)

    assert refusal.line == _line(
        'review = { model = "unpriced-model@cloud", max_output_tokens = 100 }'
    )


def test_an_unset_key_variable_names_its_line(monkeypatch) -> None:
    refusal = _refusal(monkeypatch, key_set=False)

    assert refusal.line == _line('api_key_env = "CLOUD_KEY"')
