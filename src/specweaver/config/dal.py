# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

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
