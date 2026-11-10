# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One answer to "does this object meet the protocol?" on every Python version.

`isinstance` against a runtime protocol uses `hasattr` on Python 3.11, so a `MagicMock` passes it
there; 3.12 and later look each member up with `getattr_static`. `conforms` does that on every
version.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any

_MISSING = object()


@functools.cache
def _members(protocol: type) -> dict[str, bool]:
    """Each member's name, and whether it is a method (which must then be callable)."""
    members: dict[str, bool] = {}
    for base in reversed(protocol.__mro__):
        if not getattr(base, "_is_protocol", False) or base.__module__ == "typing":
            continue
        for name in inspect.get_annotations(base):
            members.setdefault(name, False)
        for name, value in vars(base).items():
            if not name.startswith("_"):
                members[name] = inspect.isfunction(value)
    return members


def conforms(obj: object, protocol: type) -> bool:
    """True when every member of the protocol is on the object or the class it claims.

    The claimed class is `__class__`, as `isinstance` reads it: a `MagicMock(spec=X)` claims `X`,
    a bare one claims `MagicMock`.
    """
    claimed = obj.__class__
    for name, is_method in _members(protocol).items():
        found: Any = inspect.getattr_static(obj, name, _MISSING)
        if found is _MISSING:
            found = inspect.getattr_static(claimed, name, _MISSING)
        if found is _MISSING or (is_method and not callable(found)):
            return False
    return True
