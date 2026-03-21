# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests verifying that legacy runner functions were removed in Feature 3.5b.

Sub-Phase B removed get_spec_rules(), get_code_rules(), and _THRESHOLD_PARAMS
from runner.py.  These negative tests confirm that importing those names
raises ImportError, ensuring the cleanup is permanent (scenario 65).
"""

from __future__ import annotations

import pytest


class TestLegacyRunnerFunctionsRemoved:
    """Removed legacy runner APIs must not be importable (scenario 65)."""

    def test_get_spec_rules_not_importable(self) -> None:
        """get_spec_rules was removed from runner in Feature 3.5b."""
        with pytest.raises((ImportError, AttributeError)):
            from specweaver.validation import runner
            _ = runner.get_spec_rules  # type: ignore[attr-defined]

    def test_get_code_rules_not_importable(self) -> None:
        """get_code_rules was removed from runner in Feature 3.5b."""
        with pytest.raises((ImportError, AttributeError)):
            from specweaver.validation import runner
            _ = runner.get_code_rules  # type: ignore[attr-defined]

    def test_threshold_params_not_importable(self) -> None:
        """_THRESHOLD_PARAMS was removed from runner in Feature 3.5b."""
        with pytest.raises((ImportError, AttributeError)):
            from specweaver.validation import runner
            _ = runner._THRESHOLD_PARAMS  # type: ignore[attr-defined]

    def test_run_rules_still_works(self) -> None:
        """run_rules is still present in runner (was NOT removed)."""
        from specweaver.validation.runner import run_rules
        assert callable(run_rules)
