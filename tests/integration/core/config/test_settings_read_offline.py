# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The settings and the shipped model list are read with no network at all.

Proves: C-FLOW-13 NFR-3

Every socket connection is refused for the test; the real loader, the real list and a model's
price book are read anyway. The daily price refresh (`TECH-074`) is a separate step, proven to keep
the last prices offline by its own tests.

| Bucket | Case |
|---|---|
| Happy | both settings files, the keys and the shipped list load, and a price is known |
| Boundary | not applicable — there is one way to read them |
| Degradation | not applicable — nothing here may need the network |
| Hostile | the refusal is real: a connection attempt in the same test fails |
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.infrastructure.llm.catalogue import CATALOGUE_FILE, Catalogue
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.price_store import price_book

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("network refused by the test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_settings_and_the_list_load_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline: None
) -> None:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.toml").write_text(
        '[servers.anthropic]\nkind = "anthropic"\napi_key_env = "KEY"\nprivate = false\n'
        'max_parallel = 1\n\n[roles]\ndefault = "claude-opus-5-5@anthropic"\n',
        encoding="utf-8",
    )
    project = tmp_path / "proj"
    project.mkdir()
    (project / "specweaver.toml").write_text("[llm]\nprivate_only = false\n", encoding="utf-8")

    files = load_llm_settings(project)
    catalogue = Catalogue.from_text(CATALOGUE_FILE.read_text(encoding="utf-8"))
    book = price_book(
        None,
        catalogue,
        server_name="anthropic",
        server=files.machine.servers["anthropic"],
        model="claude-opus-5-5",
        overrides=files.machine.models,
    )

    price = book.default(TokenKind.INPUT)
    assert price is not None and price.usd_per_million > 0


def test_the_refusal_is_real(offline: None) -> None:
    with pytest.raises(OSError, match="refused by the test"):
        socket.create_connection(("models.dev", 443), timeout=1)
