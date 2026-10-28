# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The drafters a run's draft steps use; the run's builder hands them over."""

from __future__ import annotations

from typing import Any


class WorkflowDrafters:
    """`Drafters` backed by the drafting workflow."""

    def spec(self, **kw: Any) -> Any:
        from specweaver.workflows.drafting.drafter import Drafter

        return Drafter(**kw)

    def feature(self, **kw: Any) -> Any:
        from specweaver.workflows.drafting.feature_drafter import FeatureDrafter

        return FeatureDrafter(**kw)
