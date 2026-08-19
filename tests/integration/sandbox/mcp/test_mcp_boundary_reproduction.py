# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The MCP boundary checks what actually runs, not what the config calls it.

Proves: TECH-063 FR-1, TECH-063 FR-2, TECH-063 FR-3

`C-INTL-02` NFR-2 says executions must run through an isolated container runtime and a bare
executable is forbidden. The guard read `command[0]` as a string and compared it to
`{"docker", "podman"}` — then handed the same config's `env` to `Popen`, which resolves `argv[0]`
through the PATH in that env. The check validated a *name* while the config controlled what the
name resolved to.

**This was reproduced before it was fixed**, because the ticket was argued from reading, and a
security finding argued only from reading is a hypothesis. A directory holding a shell script named
`docker`, passed as `env={"PATH": that_directory}`, was accepted by the guard and executed: the
script wrote its marker. That reproduction is the first test below, now inverted into a guard.

The command reaches here from `mcp_servers` in the analysed project's own `context.yaml`, during
context assembly for review and generation prompts. Nobody has to invoke anything, and a repository
carrying its own `context.yaml` is the normal brownfield case this tool exists for.
"""

from __future__ import annotations

import shutil
import stat
import sys
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.mcp.core.atom import MCPAtom

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

#: Whichever runtime this machine actually has. Pinning `docker` made the suite pass or fail on what
#: happened to be installed, which is a property of the box rather than of the boundary.
RUNTIME = next((name for name in ("docker", "podman") if shutil.which(name)), None)
needs_runtime = pytest.mark.skipif(RUNTIME is None, reason="no container runtime installed")


def _fake_runtime(directory: Path, name: str) -> Path:
    """A script that impersonates a container runtime and records that it ran."""
    marker = directory / "ran"
    script = directory / name
    script.write_text(
        f"#!/bin/sh\necho compromised > {marker}\nwhile read _; do :; done\n", encoding="utf-8"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return marker


@needs_runtime
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX PATH resolution semantics")
def test_a_config_supplied_path_cannot_decide_which_runtime_runs(tmp_path: Path) -> None:
    """The reproduction, inverted.

    Before the fix, this exact arrangement was accepted by the guard and the impersonating script
    ran — verified by its marker file. The assertion is on RESOLUTION rather than on launching:
    proving it a second time by starting a process means starting a real container runtime inside a
    unit-speed test, and the resolved path is the thing that decides which binary that would be.
    """
    _fake_runtime(tmp_path, RUNTIME)

    atom = MCPAtom(command=[RUNTIME, "run", "alpine"], env={"PATH": str(tmp_path)})

    assert atom._command[0] == shutil.which(RUNTIME)
    assert not atom._command[0].startswith(str(tmp_path)), (
        "the config's PATH still chose the binary"
    )


@needs_runtime
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX PATH resolution semantics")
def test_the_impersonator_does_not_run_when_the_executor_starts(tmp_path: Path) -> None:
    """The same reproduction, carried through to an actual launch against the real runtime.

    `podman 5.7.0` is installed here, so this starts a genuine process rather than asserting about
    one. `--version` is used deliberately: it needs no image, no network and no daemon, and the claim
    under test is *which binary was launched*, not what a container then did.

    Before the fix, the marker existed after this ran.
    """
    marker = _fake_runtime(tmp_path, RUNTIME)

    atom = MCPAtom(command=[RUNTIME, "--version"], env={"PATH": str(tmp_path)})
    atom._ensure_started()
    try:
        atom._executor._process.wait(timeout=15)
    finally:
        atom._executor._process.kill()

    assert not marker.exists(), "the impersonating script on the config's PATH was executed"


@needs_runtime
def test_the_runtime_is_resolved_to_an_absolute_path(tmp_path: Path) -> None:
    """Resolution happens once, from the trusted environment, before the config is consulted."""
    atom = MCPAtom(command=[RUNTIME, "run", "alpine"], env={"PATH": str(tmp_path)})

    assert atom._command[0].startswith("/"), atom._command


@needs_runtime
@pytest.mark.parametrize("argument", ["--privileged", "--network=host", "--pid=host"])
def test_an_escaping_argument_is_refused(argument: str) -> None:
    """`docker` itself is an escape: `argv[0]` is `docker` while the flags leave the container."""
    with pytest.raises(ValueError, match="NFR-2"):
        MCPAtom(command=[RUNTIME, "run", argument, "alpine"])


@needs_runtime
@pytest.mark.parametrize("mount", ["/:/host", "/var/run/docker.sock:/var/run/docker.sock"])
def test_a_host_mount_is_refused(mount: str) -> None:
    with pytest.raises(ValueError, match="NFR-2"):
        MCPAtom(command=[RUNTIME, "run", "-v", mount, "alpine"])


def test_the_interpreter_is_not_reachable_from_configuration(tmp_path: Path) -> None:
    """The carve-out's comment said "internal test infrastructure" and it ran on every construction.

    An exact interpreter path is conventional and discoverable (`.venv/bin/python`), so a
    `context.yaml` naming it got arbitrary code with the boundary satisfied.
    """
    with pytest.raises(ValueError, match="NFR-2"):
        MCPAtom(command=[sys.executable, str(tmp_path / "server.py")])


@needs_runtime
def test_an_ordinary_container_command_is_still_accepted() -> None:
    """The control. A guard that refused everything would pass every test above."""
    atom = MCPAtom(command=[RUNTIME, "run", "-i", "--rm", "alpine"])

    assert atom._command[1:] == ["run", "-i", "--rm", "alpine"]
