# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Design Assurance Level (DAL) configurations.

Defines DO-178C compliant Design Assurance Levels representing risk profiles
for varying criticality boundaries across software components.
"""

from __future__ import annotations

import enum


class DALLevel(enum.StrEnum):
    """DO-178C Design Assurance Levels for system risk categorization."""

    DAL_A = "DAL_A"  # Aerospace-grade / Critical failure
    DAL_B = "DAL_B"  # Severe failure
    DAL_C = "DAL_C"  # Major failure
    DAL_D = "DAL_D"  # Minor failure
    DAL_E = "DAL_E"  # No safety effect

    @property
    def is_strict(self) -> bool:
        """Return True if this DAL requires strict enforcement (warnings treated as failures)."""
        return self in (DALLevel.DAL_A, DALLevel.DAL_B)

    @property
    def confidence_threshold(self) -> float:
        """Return the minimum required confidence for auto-discovered standards."""
        return {
            DALLevel.DAL_A: 0.95,
            DALLevel.DAL_B: 0.90,
            DALLevel.DAL_C: 0.80,
            DALLevel.DAL_D: 0.70,
            DALLevel.DAL_E: 0.50,
        }[self]
