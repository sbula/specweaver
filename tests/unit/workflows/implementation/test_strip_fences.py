# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A model's answer loses the fence it was wrapped in, whatever the language.

Proves: D-INTL-08 FR-4

| Bucket | Case |
|---|---|
| Happy | ```` ```java ````, ```` ```kotlin ````, ```` ```ts ````, ```` ```rust ````, ```` ```python ```` fences are removed |
| Boundary | a fence with no info string; no fence at all; surrounding blank lines |
| Degradation | an opening fence with no closing one still loses the opening line |
| Hostile | a fence line inside the code (a Kotlin raw string, a doc comment) stays |
"""

from __future__ import annotations

import pytest

from specweaver.workflows.implementation.generator import strip_fences

_JAVA = "package com.example;\n\npublic class A {}"


@pytest.mark.parametrize("info", ["java", "kotlin", "ts", "typescript", "rust", "python", ""])
def test_the_fence_goes(info: str) -> None:
    assert strip_fences(f"```{info}\n{_JAVA}\n```") == _JAVA + "\n"


def test_unfenced_code_is_kept() -> None:
    assert strip_fences(f"\n\n{_JAVA}\n\n") == _JAVA + "\n"


def test_an_unclosed_fence_loses_its_opening_line() -> None:
    assert strip_fences(f"```java\n{_JAVA}") == _JAVA + "\n"


def test_a_fence_inside_the_code_stays() -> None:
    code = 'val doc = """\n```\nexample\n```\n"""\nfun f() = doc'

    assert strip_fences(f"```kotlin\n{code}\n```") == code + "\n"
