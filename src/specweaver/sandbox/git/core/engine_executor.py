# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""EngineGitExecutor — unrestricted git executor for the Flow Engine.

Subclass of GitExecutor that lifts the permanently-blocked commands
(push, pull, fetch, merge, rebase, tag). The Engine is trusted and
needs these for flow-level operations like publish, integrate, and sync.

Agents NEVER get access to this executor — only the Engine and the
engine-controlled conflict_resolver interface.
"""

from __future__ import annotations

from specweaver.sandbox.git.core.executor import GitExecutor


class EngineGitExecutor(GitExecutor):
    """Git executor without blocked commands — for Engine use only.

    The Engine is a trusted component that needs push/pull/merge etc.
    Whitelist enforcement still applies: only commands explicitly
    whitelisted for the atom's intents are allowed.
    """

    _BLOCKED_ALWAYS: frozenset[str] = frozenset()
