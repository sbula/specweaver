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
            old_term = signal.getsignal(signal.SIGTERM)
            old_int = signal.getsignal(signal.SIGINT)

            def sig_handler(signum: int, frame: object) -> None:
                _cleanup_active_processes()

                old_handler = old_term if signum == signal.SIGTERM else old_int
                if callable(old_handler):
                    old_handler(signum, frame)
                else:
                    sys.exit(128 + signum)

            signal.signal(signal.SIGTERM, sig_handler)
            signal.signal(signal.SIGINT, sig_handler)
        except (ValueError, OSError):
            pass

_register_signals_once()
