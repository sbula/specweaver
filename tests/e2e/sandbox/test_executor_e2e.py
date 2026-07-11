# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""End-to-end tests for SubprocessExecutor adversarial payloads."""

import os
import sys
from pathlib import Path

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import ResourceLimits


class TestSubprocessExecutorE2E:

    def test_adversarial_payload_lifecycle(self, tmp_path: Path) -> None:
        """Verify executor handles a hostile payload trying to breach sandbox.

        This E2E test verifies:
        1. Memory limits (tries to allocate too much memory)
        2. Credential stealing (tries to read AZURE_CLIENT_SECRET)
        3. Timeout (tries to hang forever if memory allocation doesn't kill it)
        """
        limit_bytes = 30 * 1024 * 1024
        executor = SubprocessExecutor(
            cwd=tmp_path,
            timeout_seconds=2,
            resource_limits=ResourceLimits(max_memory_bytes=limit_bytes),
            env_allowlist=frozenset({"PATH", "PYTHONPATH"})
        )

        # Inject secret that should be stripped
        os.environ["AZURE_CLIENT_SECRET"] = "very_secret"

        py = "python" if sys.platform == "win32" else "python3"

        hostile_script = (
            "import os, sys, time\n"
            "secret = os.environ.get('AZURE_CLIENT_SECRET')\n"
            "if secret:\n"
            "    sys.stdout.write('BREACH_SUCCESS')\n"
            "    sys.exit(0)\n"
            "try:\n"
            "    x = b'A' * (100 * 1024 * 1024)\n"  # Memory allocation attempt
            "except MemoryError:\n"
            "    pass\n"
            "while True:\n"  # Hang attempt
            "    time.sleep(1)\n"
        )

        try:
            result = executor.execute([py, "-c", hostile_script])

            # Script must NOT have printed BREACH_SUCCESS
            assert "BREACH_SUCCESS" not in result.stdout

            # The script should have failed either due to Memory limit (exit_code != 0)
            # or Timeout (timed_out=True).
            # In either case, exit_code should not be 0.
            assert result.exit_code != 0

            # If it hit the memory limit, it will just exit. If it timed out, timed_out=True.
            # In Windows, memory limit often causes immediate termination.
            # In Linux, it might trigger MemoryError, which we caught, and then it hangs and times out.

        finally:
            os.environ.pop("AZURE_CLIENT_SECRET", None)
