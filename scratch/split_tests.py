import os

# SPLIT test_prompt_builder.py
pb_path = "tests/unit/infrastructure/llm/test_prompt_builder.py"
lines = open(pb_path, "r", encoding="utf-8").readlines()

# find TestDictatorOverrides
idx = 0
for i, line in enumerate(lines):
    if line.startswith("class TestDictatorOverrides:"):
        idx = i
        break

# The section starts with a header at idx - 5
start_idx = idx - 5
content_to_keep = lines[:start_idx]
content_to_move = lines[start_idx:]

open(pb_path, "w", encoding="utf-8").writelines(content_to_keep)

out_pb_path = "tests/unit/infrastructure/llm/test_prompt_builder_overrides.py"
header = [
    "# Copyright (c) 2026 sbula. All rights reserved.\n",
    "# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.\n",
    "from __future__ import annotations\n",
    "from specweaver.infrastructure.llm.prompt_builder import PromptBuilder\n\n"
]
open(out_pb_path, "w", encoding="utf-8").writelines(header + content_to_move)

# SPLIT test_handlers.py
th_path = "tests/unit/core/flow/test_handlers.py"
lines_th = open(th_path, "r", encoding="utf-8").readlines()

# find TestRunIdPropagation
idx_th = 0
for i, line in enumerate(lines_th):
    if line.startswith("class TestRunIdPropagation:"):
        idx_th = i
        break

start_idx_th = idx_th - 5
content_to_keep_th = lines_th[:start_idx_th]
content_to_move_th = lines_th[start_idx_th:]

open(th_path, "w", encoding="utf-8").writelines(content_to_keep_th)

out_th_path = "tests/unit/core/flow/test_handlers_ext.py"
header_th = [
    "# Copyright (c) 2026 sbula. All rights reserved.\n",
    "# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.\n",
    "from __future__ import annotations\n",
    "from pathlib import Path\n",
    "import pytest\n",
    "from unittest.mock import AsyncMock, MagicMock, patch\n",
    "from specweaver.core.flow.handlers import RunContext\n",
    "from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget\n",
    "from specweaver.core.flow.handlers import ReviewCodeHandler\n\n"
]
open(out_th_path, "w", encoding="utf-8").writelines(header_th + content_to_move_th)

print("Split completed.")
