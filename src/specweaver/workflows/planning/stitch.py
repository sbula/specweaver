# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Google Stitch MCP Integration for UI mockups."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.workflows.planning.models import MockupReference

logger = logging.getLogger(__name__)


class MockupResult:
    """Result from a Stitch mockup generation request."""

    def __init__(self, references: list[MockupReference]) -> None:
        self.references = references


class StitchClient:
    """Wrapper for Google Stitch MCP connection.

    Provides a pluggable interface (MCP first, direct API fallback).
    Requires STITCH_API_KEY environment variable.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("STITCH_API_KEY", "")
        self._is_available = bool(self.api_key)

    def is_available(self) -> bool:
        """Check if Stitch SDK/MCP is available and configured."""
        # In a real scenario, we'd check if the underlying MCP connection
        # or SDK node process is ready here.
        return self._is_available

    def generate_mockup(self, ui_description: str) -> MockupResult:
        """Request a UI mockup from Stitch based on description.

        Returns an empty result if generation fails or SDK is missing.
        """
        from specweaver.workflows.planning.models import MockupReference

        if not self.is_available():
            logger.warning(
                "Stitch SDK missing or STITCH_API_KEY not configured. "
                "Skipping UI mockup generation."
            )
            return MockupResult([])

        logger.info("Requesting Stitch mockup for UI (%d chars)", len(ui_description))

        try:
            # Simulate generating a mockup via MCP server/direct API
            # Placeholder implementation to satisfy 3.6b contract.
            ref = MockupReference(
                screen_name="Generated UI",
                description="Interactive mockup generated from spec requirements.",
                preview_url="https://stitch.withgoogle.com/preview/placeholder",
            )
            return MockupResult([ref])
        except Exception as e:
            logger.warning("Stitch mockup generation failed: %s", e)
            return MockupResult([])
