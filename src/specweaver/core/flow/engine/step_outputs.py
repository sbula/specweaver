# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The `StepResult.output` keys the engine reads: each named once, for its writers and readers.

The values are the wire format of stored runs, so a rename here is a data migration.
"""

from __future__ import annotations

from typing import Final

#: `decompose+feature`'s DecompositionPlan, dumped to a dict; hydrated into the plan context.
PLAN: Final = "plan"
#: `plan+spec`'s plan artifact on disk (`str`); its text is hydrated into the plan context.
PLAN_PATH: Final = "plan_path"
#: A validate step's rule results (`list[dict]`); persisted to the state DB.
RESULTS: Final = "results"
#: A review or arbiter verdict (`str`); the `accepted` gate condition reads it.
VERDICT: Final = "verdict"
#: The files a step wrote (`list[str]`, relative to its project); saved in the run's handover.
FILES_TOUCHED: Final = "files_touched"
