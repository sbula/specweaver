# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Home of the `LLMAdapterError` re-export.

Adapters are built in one place only: `RoleResolver` (`resolve.py`), from the settings files. This
module used to build them from database profiles; it now only keeps the name below resolving.
"""

from __future__ import annotations

# Re-exported, not defined: it lives in `errors.py`, a leaf, so `_rate_limit` can raise it without
# importing `factory` back. Eleven files import it from here, so the name keeps resolving — new
# code should import from `errors`.
from specweaver.infrastructure.llm.errors import LLMAdapterError as LLMAdapterError
