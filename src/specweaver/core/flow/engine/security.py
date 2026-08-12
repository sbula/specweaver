# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pre-run safety checks that must fail the run rather than warn.

Split out of `runner_utils.py` by `TECH-015`. Today this is the vault-binding audit: a tracked
`vault.env` aborts execution rather than leaking credentials into a commit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.base import RunContext


def verify_vault_security(context: RunContext) -> None:
    """Feature 3.32c SF-1: Safe Vault Binding Audit (Option D)."""
    vault_path = context.project_path / ".specweaver" / "vault.env"
    if vault_path.exists():
        from specweaver.sandbox.git.core.atom import GitAtom

        git_atom = GitAtom(cwd=context.project_path)
        # Check if tracked
        result = git_atom.run({"intent": "is_tracked", "path": ".specweaver/vault.env"})
        if getattr(result, "exports", {}).get("is_tracked", False):
            raise RuntimeError(
                "FATAL: vault.env is currently tracked by Git! Aborting execution to prevent credential leakage."
            )
