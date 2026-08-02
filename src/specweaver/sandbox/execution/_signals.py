# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Signal and cleanup handlers for subprocess execution (FR-7)."""

import atexit
import signal
import subprocess
import sys
import threading
import weakref

_active_processes: weakref.WeakSet[subprocess.Popen[str]] = weakref.WeakSet()
_signals_registered = False


def track_process(proc: subprocess.Popen[str]) -> None:
    """Register a process for cleanup on interpreter shutdown."""
    _active_processes.add(proc)


def _cleanup_active_processes() -> None:
    """Terminate all tracked subprocesses during interpreter shutdown."""
    for proc in list(_active_processes):
        try:
            if proc.poll() is None:
                if sys.platform == "win32":
                    proc.terminate()
                else:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        proc.kill()
        except Exception:
            pass


def _register_signals_once() -> None:
    global _signals_registered
    if _signals_registered:
        return
    _signals_registered = True

    atexit.register(_cleanup_active_processes)

    if threading.current_thread() is threading.main_thread():
        try:
            handled = [signal.SIGTERM, signal.SIGINT]
            if sys.platform == "win32":
                # Ctrl+C (SIGINT) cannot be delivered to a Windows child process without also
                # signalling the caller, unless the child runs in its own process group — and
                # Windows disables Ctrl+C handling for a new process group by default. Ctrl+Break
                # (SIGBREAK) is the only signal that CAN be targeted at just the child, so it must
                # trigger the same graceful-cleanup path or Windows children have no working
                # interrupt signal at all.
                handled.append(signal.SIGBREAK)

            old_handlers = {sig: signal.getsignal(sig) for sig in handled}

            def sig_handler(signum: int, frame: object) -> None:
                _cleanup_active_processes()

                old_handler = old_handlers.get(signum)
                if callable(old_handler):
                    old_handler(signum, frame)
                else:
                    sys.exit(128 + signum)

            for sig in handled:
                signal.signal(sig, sig_handler)
        except (ValueError, OSError):
            pass


_register_signals_once()
