# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for `specweaver.sandbox.execution._signals` graceful-shutdown registration.

On Windows, `Popen.send_signal()` cannot deliver SIGINT to a child process without also
signalling the caller, unless the child runs in its own process group — and Windows disables
Ctrl+C handling for a new process group by default. Ctrl+Break (`SIGBREAK`) is the only signal
that CAN be targeted at just the child. Before this fix, `_register_signals_once()` only wired
SIGTERM/SIGINT, so a child receiving Ctrl+Break on Windows fell through to Python's default
SIGBREAK disposition (abrupt termination) instead of the same graceful cleanup path — meaning
`tests/e2e/capabilities/infrastructure/test_cqrs_e2e.py::test_story_9_sigint_survival` had no
way to exercise graceful shutdown on Windows at all (found via TECH-001's precondition gate,
2026-08-01; tracked as part of TECH-017's "SIGINT e2e skips on Windows" finding).
"""

from __future__ import annotations

import signal
import sys

import pytest

from specweaver.sandbox.execution import _signals


@pytest.fixture(autouse=True)
def _reset_signal_registration() -> None:
    """Save/restore real handlers around each test — this module's state is process-global."""
    signals_to_snapshot = [signal.SIGTERM, signal.SIGINT]
    if sys.platform == "win32":
        signals_to_snapshot.append(signal.SIGBREAK)  # type: ignore[attr-defined]

    original = {sig: signal.getsignal(sig) for sig in signals_to_snapshot}
    original_registered = _signals.__dict__["_signals_registered"]
    _signals.__dict__["_signals_registered"] = False

    yield

    _signals.__dict__["_signals_registered"] = original_registered
    for sig, handler in original.items():
        signal.signal(sig, handler)


def test_register_signals_wires_sigterm_and_sigint() -> None:
    _signals._register_signals_once()

    assert signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL
    assert signal.getsignal(signal.SIGINT) is not signal.SIG_DFL


def test_register_signals_is_idempotent() -> None:
    _signals._register_signals_once()
    first = signal.getsignal(signal.SIGINT)

    _signals._register_signals_once()  # second call must be a no-op (guarded by the module flag)

    assert signal.getsignal(signal.SIGINT) is first


@pytest.mark.skipif(sys.platform != "win32", reason="SIGBREAK only exists on Windows")
def test_register_signals_wires_sigbreak_on_windows() -> None:
    """The signal a test (or a real user's Ctrl+Break) can actually target at a child process."""
    _signals._register_signals_once()

    sigbreak_handler = signal.getsignal(signal.SIGBREAK)  # type: ignore[attr-defined]
    sigint_handler = signal.getsignal(signal.SIGINT)

    assert sigbreak_handler is not signal.SIG_DFL
    # Both must route through the same graceful-cleanup handler, not two different code paths.
    assert sigbreak_handler is sigint_handler


@pytest.mark.skipif(sys.platform == "win32", reason="SIGBREAK does not exist off Windows")
def test_register_signals_does_not_touch_sigbreak_off_windows() -> None:
    """Guards against referencing signal.SIGBREAK unconditionally on non-Windows platforms."""
    _signals._register_signals_once()  # must not raise AttributeError for a missing SIGBREAK

    assert signal.getsignal(signal.SIGINT) is not signal.SIG_DFL
