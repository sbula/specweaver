# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The MCP boundary resolves a container runtime against the machine it runs on.

That resolution is the fix for a real bypass — `Popen` resolves `argv[0]` through the PATH of the
`env` it is handed, and that `env` comes from the analysed project's `context.yaml`, so comparing
`command[0]` to a NAME validated nothing the config could not redirect.

The assembler's own tests are about `mcp_servers` reaching the atom, not about which runtimes are
installed. Answering `shutil.which` for both keeps them a property of the code rather than of the
box: they used to name `docker`, and would now pass or fail on whether this machine has it.
"""

from __future__ import annotations

import shutil

import pytest

_REAL_WHICH = shutil.which


@pytest.fixture(autouse=True)
def _container_runtimes_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    def which(name: str, *args: object, **kwargs: object) -> str | None:
        if name in ("docker", "podman"):
            return f"/usr/bin/{name}"
        return _REAL_WHICH(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(shutil, "which", which)
