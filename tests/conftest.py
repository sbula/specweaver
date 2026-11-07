# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Suite-wide invariants that must hold before anything imports a renderer.

## The suite runs colour-free

Measured 2026-08-15: with `FORCE_COLOR` set — which is how every agent-driven run sees the suite —
**28 tests across all three tiers failed**, and with it unset, none did. Same tree, same commit, one
environment variable.

The escapes land *inside* tokens, not merely around them: Rich highlights the number in
`SpecWeaver v0.1.0`, so the string becomes `v0.\\x1b[1;36m1.0\\x1b[0m` and even a
whitespace-tolerant check misses it. That made "no accepted deltas" unfollowable under an agent:
28 failures always present and never anyone's fault, which is precisely the state that rule exists
to prevent.

**Two consumers, two variables, and confusing them is why the first attempt at this fixed one test
out of 28.** `PY_COLORS` is pytest's own convention, checked first in its `should_do_markup`; Rich
has never heard of it and reads `NO_COLOR` / `FORCE_COLOR` (`rich/console.py:734,970`). The 28
failures are Rich rendering the *CLI's* output, so `NO_COLOR` is the one that matters — and
`FORCE_COLOR` must be cleared too, since an inherited one would otherwise still win.

Set at import time rather than in a fixture because Rich reads the environment when a `Console` is
constructed, and some are built at module import — a fixture would run too late.

**This protects tests nobody has written yet**, which `tests/rendering.py::shows()` cannot: that
helper only guards assertions whose author remembered to use it. Both exist deliberately, the same
belt-and-braces `scripts/_mutate.py` uses, because one guard is one environment variable away from
failing.

A test that genuinely wants colour sets it back for its own duration — see
`tests/unit/interfaces/cli/test_cli_renders_colour.py`.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
from typing import TYPE_CHECKING, Any

import pytest

from tests.baseline_snapshot import BASELINES, rewrites, snapshot
from tests.ci_skips import (  # noqa: F401 -- hooks: on CI a tool skip fails the run
    pytest_collectreport,
    pytest_runtest_logreport,
    pytest_sessionfinish,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

# The suite never touches the user's real `~/.specweaver/`: its settings file, its database and its
# pipeline state. Measured 2026-09-27: without this, a test that did not isolate itself wrote a price
# into the real `settings.toml` and rebuilt a table of the real `specweaver.db`. Set at import time,
# before anything resolves the data root; a test that sets its own directory still overrides it.
os.environ["SPECWEAVER_DATA_DIR"] = tempfile.mkdtemp(prefix="specweaver-tests-")

os.environ["NO_COLOR"] = "1"  # Rich: the CLI's own output
os.environ["PY_COLORS"] = "0"  # pytest: its terminal writer, and anything parsing it
os.environ.pop("FORCE_COLOR", None)  # inherited from an agent shell; would beat both


@pytest.fixture(autouse=True)
def _baselines_are_read_only() -> Iterator[None]:
    """No test may rewrite a gate's ratchet baseline.

    `scripts/baselines/` is the standard this repo is measured against, and nothing compares a
    baseline against what it was — so a test that writes one relaxes or corrupts a gate inside a
    diff that reads as ordinary test work.

    Found for real on 2026-08-16: `test_mutation_seam.py` called `mutation.main()` without
    `--ledger`, and `record_run` appended to the **real** `mutation_findings.json` on every suite
    run, inventing a finding for a mutant that existed only inside a fixture. It was noticed by an
    unexplained modification in `git status`, which is not a detection mechanism.

    Fails the offending test rather than restoring the file: a fixture that silently rewrote
    version-controlled content would be doing the very thing it exists to catch. Nothing cascades —
    the next test's "before" is the polluted state, so only the writer fails.
    """
    before = snapshot(BASELINES)
    yield
    changed = rewrites(before, snapshot(BASELINES))
    if changed:
        pytest.fail(
            "this test wrote to scripts/baselines/, which is version-controlled gate state:\n  "
            + "\n  ".join(changed)
            + "\nPoint the tool at tmp_path instead — most take a --ledger/--baseline argument.",
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def _no_price_refresh_at_start(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command's start-up price refresh is off unless a test is marked `price_refresh`: every other
    test that builds a router would otherwise ask models.dev, and be slowed or warned by the refusal."""
    if not request.node.get_closest_marker("price_refresh"):
        from specweaver.infrastructure.llm import price_refresh

        monkeypatch.setattr(price_refresh, "refresh_at_start", lambda *_a, **_k: None)


#: Loopback ports a test may not reach: a real model server listens there (Ollama).
_MODEL_PORTS = frozenset({11434})
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_REAL_GETADDRINFO = socket.getaddrinfo


def _loopback(host: object) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


def _refuse(target: object) -> None:
    msg = f"a test tried to reach the network: {target} — use fake_httpx2 or respx, or mark it live"
    raise RuntimeError(msg)


def _guarded(address: Any) -> Any:
    """The address, if a test may connect to it: a Unix socket, or loopback off the model ports."""
    if isinstance(address, tuple) and not (
        _loopback(address[0]) and address[1] not in _MODEL_PORTS
    ):
        _refuse(address)
    return address


def _connect(sock: socket.socket, address: Any) -> None:
    _REAL_CONNECT(sock, _guarded(address))


def _connect_ex(sock: socket.socket, address: Any) -> int:
    return _REAL_CONNECT_EX(sock, _guarded(address))


def _getaddrinfo(host: object, *args: object, **kwargs: object) -> object:
    """A name lookup sends a query off the machine, so only loopback names and numbers resolve."""
    if host is not None and not _loopback(host):
        try:
            ipaddress.ip_address(str(host).split("%")[0])
        except ValueError:
            _refuse(host)
    return _REAL_GETADDRINFO(host, *args, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _no_real_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """A test not marked `live` opens no connection that leaves the machine, whatever library asks.

    Blocked at the socket, below every client: `httpx2` (openai, anthropic), `httpx` (google-genai,
    mistralai) and anything else. Fakes (`fake_httpx2`, `respx`) answer before a socket opens, and a
    test's own server on loopback still answers; loopback port 11434 (Ollama) does not. The canary
    is `tests/unit/test_no_test_reaches_a_server.py`.
    """
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setattr(socket.socket, "connect", _connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo)


@pytest.fixture(autouse=True)
def _lock_wait_restored() -> Iterator[None]:
    """Each test starts with the default lock wait; a door under test sets its own (TECH-090 AD-5)."""
    from specweaver.infrastructure.database import sqlite as opener

    wait = opener.lock_wait_seconds()
    yield
    opener.set_lock_wait(wait)


@pytest.fixture(autouse=True)
def _specweaver_logger_restored() -> Iterator[None]:
    """Each test gets back the `specweaver` logger it started with: level, handlers, project tag.

    `setup_logging` (any CLI test runs it) sets that logger's level, and `caplog.at_level` sets only
    the root's, so a later test's DEBUG records were dropped before caplog saw them. Which tests
    failed depended on how xdist spread the files (measured 2026-11-06).
    """
    import logging

    logger = logging.getLogger("specweaver")
    level, handlers = logger.level, list(logger.handlers)
    project = getattr(logger, "_sw_project", None)
    yield
    logger.setLevel(level)
    logger.handlers[:] = handlers
    if project is None:
        logger.__dict__.pop("_sw_project", None)
    else:
        logger._sw_project = project  # type: ignore[attr-defined]
