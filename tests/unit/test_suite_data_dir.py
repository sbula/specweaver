# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The suite runs against a throw-away data directory, never the user's `~/.specweaver/`."""

from __future__ import annotations

from pathlib import Path

from specweaver.core.config.paths import specweaver_root


def test_the_data_root_is_not_the_users_home() -> None:
    root = specweaver_root().resolve()

    assert root != (Path.home() / ".specweaver").resolve()
    assert root.name.startswith("specweaver-tests-") or "pytest" in str(root)
