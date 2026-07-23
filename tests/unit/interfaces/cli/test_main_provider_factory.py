# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-02 SF-02 T2: the delivery-layer interaction-channel factory.

The TTY decision lives HERE (next to the Rich console), not in core: the factory returns
an HITLProvider only on an interactive stdin, else None (headless park contract, FR-5).
"""

from __future__ import annotations

from unittest.mock import patch

from specweaver.interfaces.cli import main as main_mod
from specweaver.interfaces.cli.hitl_provider import HITLProvider


def test_factory_returns_hitl_provider_on_tty() -> None:
    """[Happy] interactive stdin -> a real HITLProvider instance."""
    with patch.object(main_mod, "_stdin_isatty", return_value=True):
        provider = main_mod._interactive_context_provider()
    assert isinstance(provider, HITLProvider)

def test_factory_returns_none_when_headless() -> None:
    """[Boundary/FR-5] no TTY -> None (parking stays the headless contract)."""
    with patch.object(main_mod, "_stdin_isatty", return_value=False):
        assert main_mod._interactive_context_provider() is None

def test_factory_registered_with_the_seam_at_import() -> None:
    """[Happy/R4] importing main registers the factory on the core seam."""
    from specweaver.core.flow.interfaces import cli as flow_cli_mod

    assert flow_cli_mod._context_provider_factory is main_mod._interactive_context_provider
