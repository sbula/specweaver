# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""These tests need a stdio server they can start without an image, a registry or a network.

The MCP boundary refuses a bare interpreter, which is the point of it — a `context.yaml` naming
`.venv/bin/python` used to get arbitrary code with the boundary reporting compliance. The seam is
opened here, in test scope, rather than left open in production: patching a module constant needs
in-process code execution, and configuration has none.

Declared autouse in a conftest rather than repeated at 16 call sites, so the exemption is visible in
one place and cannot be granted by accident.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _allow_interpreter_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specweaver.sandbox.mcp.core.atom._ALLOW_INTERPRETER", True)
