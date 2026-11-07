# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one way SpecWeaver opens its SQLite files, and the steps that keep their schema current."""

from specweaver.infrastructure.database.engine import create_sqlite_engine
from specweaver.infrastructure.database.handle import Database, session_scope
from specweaver.infrastructure.database.legacy import rename_legacy_tables
from specweaver.infrastructure.database.sqlite import lock_wait_seconds, open_sqlite, set_lock_wait
from specweaver.infrastructure.database.steps import (
    SchemaStepError,
    SchemaTooNewError,
    Step,
    upgrade,
)
from specweaver.infrastructure.database.types import StrictISODateTime

__all__ = [
    "Database",
    "SchemaStepError",
    "SchemaTooNewError",
    "Step",
    "StrictISODateTime",
    "create_sqlite_engine",
    "lock_wait_seconds",
    "open_sqlite",
    "rename_legacy_tables",
    "session_scope",
    "set_lock_wait",
    "upgrade",
]
