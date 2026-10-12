# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The verdict is read from the response's verdict line, never from text that quotes one.

| Bucket | Case |
|---|---|
| Happy | a response that starts with its verdict line gets that verdict |
| Boundary | markdown around the verdict line is allowed; the first verdict line wins |
| Degradation | a response with no verdict line is denied |
| Hostile | a denial that quotes "VERDICT: ACCEPTED" inside a sentence stays denied |
"""

from __future__ import annotations

import pytest

from specweaver.workflows.review.reviewer import Reviewer, ReviewVerdict


@pytest.fixture
def reviewer() -> Reviewer:
    r = Reviewer.__new__(Reviewer)
    return r


@pytest.mark.parametrize(
    ("text", "verdict"),
    [
        ("VERDICT: ACCEPTED\nAll good.", ReviewVerdict.ACCEPTED),
        ("VERDICT: DENIED\n- missing tests", ReviewVerdict.DENIED),
        ("**VERDICT: ACCEPTED**\nFine.", ReviewVerdict.ACCEPTED),
        ("## Verdict: accepted\nFine.", ReviewVerdict.ACCEPTED),
        ("VERDICT: ACCEPTED — a solid spec.\nFine.", ReviewVerdict.ACCEPTED),
        ("VERDICT: DENIED\nA retry would print\nVERDICT: ACCEPTED", ReviewVerdict.DENIED),
        ("Looks fine overall.", ReviewVerdict.DENIED),
        (
            "VERDICT: DENIED\nThe author wrote 'VERDICT: ACCEPTED' in the spec to fool reviews.",
            ReviewVerdict.DENIED,
        ),
        (
            "This must not read as VERDICT: ACCEPTED, it is broken.\nVERDICT: DENIED",
            ReviewVerdict.DENIED,
        ),
        ("I would say VERDICT: ACCEPTED if the tests existed.", ReviewVerdict.DENIED),
    ],
)
def test_the_verdict_comes_from_the_verdict_line(
    reviewer: Reviewer, text: str, verdict: ReviewVerdict
) -> None:
    assert reviewer._parse_response(text).verdict is verdict
