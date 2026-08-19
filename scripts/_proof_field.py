#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Read a `**Verifiable Proof:**` field to its own end. `TECH-017`.

Both gates that read this field used a **character window** standing in for a field:
`check_story_preconditions.py` took `(.{0,600})` and `check_proof_tier.py` `(.{0,900})`. The
consequence is backwards — a longer, more thorough declaration is verified LESS than a short one,
and both gates print PASS either way.

Measured, not theorised: `INT-US-25`'s proof line is 1886 characters, so the preconditions gate saw
**3 of the 9 declared test files and ran 29 of the 75 tests**, then reported 8 passed / 0 failures.

Widening the window was rejected as the fix. A window is wrong at every size — at 200 characters
per line it still truncates a three-line proof, and a bigger number only moves the cliff. The field
has a real end, so the parser reads to it.

Unbounded was rejected too: without a stop the read swallows the following fields and the rest of
the document, which would credit a contract with test paths belonging to its neighbours.
"""

from __future__ import annotations

import re

#: Where a field ends: the next `* **Field:**` bullet, a markdown heading, a thematic break, a new
#: unindented paragraph, or end of text.
#:
#: A blank line alone is NOT a boundary — a proof written as a list is separated from its own bullets
#: by newlines, and stopping there would truncate exactly the multi-line form this parser enables.
#: A blank line followed by text at column 0 **is** one: in markdown that starts a new block, so it
#: cannot be part of this bullet. Without it the last entry in a document reads to end of text and
#: borrows every `.py` path in the prose below it — measured live on `US-05`, whose final add-on
#: cited only a directory and read as proven for as long as the file ended in prose.
_FIELD = re.compile(
    r"\*\*Verifiable Proof[^:]*:\*\*(.*?)"
    r"(?=\n\s*[*-]\s+\*\*[A-Z]|\n#{1,6}\s|\n\s*-{3,}\s*$|\n\n\S|\Z)",
    re.S | re.M,
)


def proof_segment(text: str) -> str | None:
    """Return the Verifiable Proof field's full text, or None if the field is absent."""
    match = _FIELD.search(text)
    return match.group(1) if match else None
