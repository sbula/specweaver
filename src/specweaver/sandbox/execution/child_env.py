# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a child process may see of the parent's environment: an allowlist, never a credential."""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Default environment allowlist (H-3: includes GIT_* vars)
# ---------------------------------------------------------------------------

_DEFAULT_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USERPROFILE",
        "LANG",
        "LC_ALL",
        "TERM",
        "PYTHONPATH",
        "PYTHONHASHSEED",
        "NODE_PATH",
        "CARGO_HOME",
        "JAVA_HOME",
        "GRADLE_HOME",
        "GOPATH",
        "GOROOT",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "TMPDIR",
        "TEMP",
        "TMP",
        "SystemRoot",
        "COMSPEC",
        "GIT_EXEC_PATH",
        "GIT_DIR",
    }
)

# Credential env vars to ALWAYS strip — even from extra_env (red team cycle 1)
_CREDENTIAL_VARS: frozenset[str] = frozenset(
    {
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MISTRAL_API_KEY",
        "QWEN_API_KEY",
        "DASHSCOPE_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
    }
)

# Prefix-based credential stripping
_CREDENTIAL_PREFIXES: tuple[str, ...] = ("AZURE_",)


def _is_credential(key: str) -> bool:
    """Whether an environment variable name names a credential.

    Checked by exact name AND by prefix, because the prefix list is what catches the variants a
    fixed list cannot enumerate (`AWS_*`, `*_TOKEN` families).
    """
    return key in _CREDENTIAL_VARS or any(key.startswith(p) for p in _CREDENTIAL_PREFIXES)


def build_child_env(
    extra_env: dict[str, str] | None,
    *,
    allowlist: frozenset[str] | None = None,
    strip_credentials: bool = True,
) -> dict[str, str]:
    """A clean child environment: allowlist from the parent, then extras, then strip credentials.

    1. Start from an empty dict — never from `os.environ`
    2. Copy allowed vars from the parent environment
    3. Merge `extra_env`
    4. Strip credential vars, ALWAYS, even ones injected via `extra_env`

    Module-level so a caller that cannot use `SubprocessExecutor.execute()` can still share its
    environment discipline. `MCPExecutor` is the case: it keeps a long-lived bidirectional process
    alive across many calls, which `execute()` cannot host — it is one-shot and `communicate()` waits
    for exit. What the two genuinely share is what the child is allowed to see, and passing `None`
    to `Popen(env=...)` hands it the whole parent environment instead.
    """
    env: dict[str, str] = {}

    for key in allowlist if allowlist is not None else _DEFAULT_ENV_ALLOWLIST:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val

    if extra_env:
        env.update(extra_env)

    if strip_credentials:
        env = {k: v for k, v in env.items() if not _is_credential(k)}

    return env
