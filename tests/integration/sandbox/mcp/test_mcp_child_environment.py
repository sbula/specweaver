# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An MCP server does not inherit this process's credentials.

Proves: TECH-010 FR-1, TECH-010 FR-2

`MCPExecutor` was the last raw `subprocess.Popen` in `sandbox/`, and it passed the config's `env`
straight through. When a `context.yaml` declares no `env` — the common case — that argument is
`None`, and `Popen` then hands the child **the entire parent environment**.

Reproduced before the fix: with `ANTHROPIC_API_KEY` set in this process, a server started by
`MCPExecutor` read it back verbatim. The server is an external binary named by the analysed
project's own configuration, so that is a credential handed to third-party code on the strength of a
config file.

`TECH-010` observed that `SubprocessExecutor.execute()` cannot host this process — it is one-shot and
`communicate()` waits for exit, while MCP is long-lived and bidirectional. What it CAN share is the
environment discipline, which is what these tests pin: the allowlist and the credential strip, not
the call shape.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.mcp.core.executor import MCPExecutor

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

SECRET = "sk-secret-should-not-leak"


def _probe(tmp_path: Path, variable: str) -> str:
    """Start a server that records what it inherited, and return what it saw."""
    out = tmp_path / "seen.txt"
    script = tmp_path / "probe.py"
    script.write_text(
        f"import os, time\n"
        f"open({str(out)!r}, 'w').write(os.environ.get({variable!r}, '<absent>'))\n"
        f"time.sleep(0.2)\n",
        encoding="utf-8",
    )
    executor = MCPExecutor([sys.executable, str(script)], None)
    try:
        for _ in range(50):
            if out.exists():
                break
            time.sleep(0.05)
    finally:
        executor.close()
    return out.read_text(encoding="utf-8") if out.exists() else "(the probe never ran)"


def test_a_credential_is_not_handed_to_the_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reproduction, inverted. Before the fix this returned the key verbatim."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)

    assert _probe(tmp_path, "ANTHROPIC_API_KEY") == "<absent>"


def test_a_variable_outside_the_allowlist_is_not_handed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stripping only known credential NAMES would still leak everything else in the environment."""
    monkeypatch.setenv("SOME_INTERNAL_HOST", "10.0.0.1")

    assert _probe(tmp_path, "SOME_INTERNAL_HOST") == "<absent>"


def test_the_server_still_gets_what_it_needs_to_run(tmp_path: Path) -> None:
    """The control. An empty environment would pass both tests above and break every real server."""
    assert _probe(tmp_path, "PATH") not in ("", "<absent>")


def test_configured_environment_still_reaches_the_server(tmp_path: Path) -> None:
    """`mcp_servers[].env` is how a project configures its own server, and it must still work."""
    out = tmp_path / "seen.txt"
    script = tmp_path / "probe.py"
    script.write_text(
        f"import os, time\n"
        f"open({str(out)!r}, 'w').write(os.environ.get('MCP_DB', '<absent>'))\n"
        f"time.sleep(0.2)\n",
        encoding="utf-8",
    )
    executor = MCPExecutor([sys.executable, str(script)], {"MCP_DB": "postgres://demo"})
    try:
        for _ in range(50):
            if out.exists():
                break
            time.sleep(0.05)
    finally:
        executor.close()

    assert out.read_text(encoding="utf-8") == "postgres://demo"


def test_a_credential_injected_by_configuration_is_still_stripped(tmp_path: Path) -> None:
    """A config naming a credential must not be a way back in — same rule the executor already has."""
    out = tmp_path / "seen.txt"
    script = tmp_path / "probe.py"
    script.write_text(
        f"import os, time\n"
        f"open({str(out)!r}, 'w').write(os.environ.get('OPENAI_API_KEY', '<absent>'))\n"
        f"time.sleep(0.2)\n",
        encoding="utf-8",
    )
    executor = MCPExecutor([sys.executable, str(script)], {"OPENAI_API_KEY": SECRET})
    try:
        for _ in range(50):
            if out.exists():
                break
            time.sleep(0.05)
    finally:
        executor.close()

    assert out.read_text(encoding="utf-8") == "<absent>"


def test_the_environment_is_isolated_from_this_process(tmp_path: Path) -> None:
    """`os.environ` must not be mutated on the way — the parent keeps what it had."""
    before = dict(os.environ)

    _probe(tmp_path, "PATH")

    assert dict(os.environ) == before
