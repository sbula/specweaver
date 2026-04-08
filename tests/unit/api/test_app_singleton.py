# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for EventBridge singleton management in app.py."""

from __future__ import annotations

import specweaver.api.app as app_module
from specweaver.api.event_bridge import EventBridge


class TestEventBridgeSingleton:
    """Tests for get_event_bridge / set_event_bridge (#48-50)."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        app_module._event_bridge = None

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        app_module._event_bridge = None

    # --- Gap #48: lazy init creates singleton ---

    def test_get_event_bridge_creates_instance(self) -> None:
        """get_event_bridge lazy-creates an EventBridge on first call."""
        assert app_module._event_bridge is None
        bridge = app_module.get_event_bridge()
        assert isinstance(bridge, EventBridge)
        assert app_module._event_bridge is bridge

    # --- Gap #49: returns same instance ---

    def test_get_event_bridge_returns_same_instance(self) -> None:
        """get_event_bridge returns the same singleton on repeated calls."""
        b1 = app_module.get_event_bridge()
        b2 = app_module.get_event_bridge()
        assert b1 is b2

    # --- Gap #50: set_event_bridge overrides ---

    def test_set_event_bridge_overrides_singleton(self) -> None:
        """set_event_bridge replaces the global singleton."""
        original = app_module.get_event_bridge()
        replacement = EventBridge(max_concurrent=1)
        app_module.set_event_bridge(replacement)

        assert app_module.get_event_bridge() is replacement
        assert app_module.get_event_bridge() is not original
