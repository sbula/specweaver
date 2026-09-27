# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import pytest

pytest.importorskip("openai")

from specweaver.infrastructure.llm.adapters.qwen import QwenAdapter

_ADDRESS = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"


class TestQwenAdapter:
    def test_provider_metadata(self) -> None:
        adapter = QwenAdapter(api_key="test", base_url=_ADDRESS)
        assert adapter.provider_name == "qwen"
        assert adapter.api_key_env_var == "DASHSCOPE_API_KEY"
        assert "qwen3-max" in QwenAdapter.default_costs

    def test_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test")
        assert QwenAdapter(base_url=_ADDRESS).available() is True
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        assert QwenAdapter(api_key="", base_url=_ADDRESS).available() is False

    def test_client_init(self) -> None:
        pytest.importorskip("openai")
        adapter = QwenAdapter(api_key="test", base_url=_ADDRESS)
        client = adapter._get_client()
        assert client.api_key == "test"
        assert str(client.base_url) == _ADDRESS + "/"
