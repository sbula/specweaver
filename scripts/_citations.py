# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One citation grammar, shared by the FR and NFR sweeps. `TECH-017` finding 6.

A citation used to be two independent greps over a whole file — "does it name the story" and "does
`FR-N` appear" — and anything satisfying both counted. Three failure modes came out of that on
2026-08-13, every one observed rather than imagined:

1. **False credit.** A docstring saying *"FR-1, FR-6 and FR-7 are deliberately NOT proven here"*
   marked all three covered. The sweep fell by 3 because a test wrote down that it had a gap.
2. **Misplacement.** A citation written to "the first `\"\"\"` in the file" lands in a fixture's
   docstring when the module has none — counted, and filed under the wrong thing.
3. **Invisible proof.** `\"\"\"FR-7: Transition to ARCHIVED...\"\"\"` in a file that never names its
   capability is a real attribution the ledger cannot see.

**The strict grammar fixes 1 and 2 by construction, and cannot fix 3.** Only
``Proves: <ID> FR-N[, FR-M]`` inside the **module** docstring is authoritative, so prose, fixture
strings and disclaimers can never credit anything, and there is exactly one place to write it.
A tag carries its own id, so a tagged file was never invisible — 3 is a *discovery* problem, and
:func:`unattributed_requirements` is the detector for it, not a stricter regex.

> [!IMPORTANT]
> **Legacy loose mentions still count, deliberately.** Measured 2026-08-13: 26 of 719 test files
> carry a tag at all. Making the strict form mandatory that day would have dropped hundreds of
> credits and spiked both ratchets — pain, with not one test improved. So the strict form is
> mandatory for NEW closures and the legacy form keeps its credit, with the split reported so it can
> be drained requirement by requirement.

None of this measures whether a cited test *proves* anything. That is strength, and only mutation
testing (`A-VAL-03`) answers it. See `.claude/skills/specweaver-ticket/references/closure-contract.md`.
"""

from __future__ import annotations

import ast
import re

#: The authoritative citation. ``Proves:`` (colon optional — one delivered file predates it), a
#: registry id, then the requirements it claims, to the end of the line.
_TAG = re.compile(
    r"Proves:?\s+(?P<story>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+(?:-SF\d+)?)\s*(?P<reqs>[^\n]*)"
)

#: A requirement id. Both families, because NFRs joined the ledger with `TECH-017`.
_REQ = re.compile(r"\b((?:N?FR)-\d+)\b")

#: A requirement id that is an *input* to the code under test rather than a claim about it. Keeping
#: these out is why `unattributed_requirements` reads only comments and docstrings: writing
#: ``spec.write_text("Hello FR-1")`` is fixture data, and `test_c09_traceability.py` does exactly
#: that twelve times.
_STRING_LITERAL = re.compile(r"""['"]""")


def strict_citations(text: str) -> dict[str, set[str]]:
    """``story -> requirements`` claimed by ``Proves:`` tags in the module docstring.

    Returns ``{}`` for an unparseable file rather than raising: one bad file must not be able to
    hide the state of the whole tree, the same rule the sweeps apply to undecodable ones.
    """
    try:
        module = ast.parse(text)
    except (SyntaxError, ValueError):
        return {}
    doc = ast.get_docstring(module)
    if not doc:
        return {}
    found: dict[str, set[str]] = {}
    for match in _TAG.finditer(doc):
        reqs = set(_REQ.findall(match.group("reqs")))
        if reqs:
            found.setdefault(match.group("story"), set()).update(reqs)
    return found


def loose_mentions(text: str, story: str) -> set[str]:
    """Legacy credit: every requirement id in a file that names the story.

    Preserved exactly as it behaved before the strict grammar existed, so that introducing one
    could not silently revoke a credit. It is the permissive half and it is meant to shrink.
    """
    if story not in text:
        return set()
    return set(_REQ.findall(text))


def credited_requirements(text: str, story: str) -> set[str]:
    """What this file may credit to ``story`` — the single rule both sweeps should use.

    **A `Proves:` tag is exhaustive for the story it names.** If the file tags that story, the tag is
    the whole claim and prose adds nothing; otherwise the legacy loose credit applies unchanged.

    This is not a refinement, it is a defect fix. The same mistake was made three times in one day,
    twice after the rule against it was written down: a docstring saying *"NFR-2 is deliberately NOT
    claimed here"* credits NFR-2, because the legacy rule reads every id in a file that names the
    story. The third time it concealed a real defect — `E-EXEC-01` NFR-2 requires ``< 5ms`` overhead
    and its only test asserts ``< 200ms``, so a 40x-looser test made the requirement read as proven.

    Prose is not evidence once an author has shown they know the syntax. Untagged files are
    untouched, so nothing already credited is revoked except where a tag deliberately excluded it.
    """
    tags = strict_citations(text)
    if story in tags:
        return set(tags[story])
    return loose_mentions(text, story)


def _prose_lines(text: str) -> list[str]:
    """Comment and docstring lines only — never string literals used as test data."""
    out: list[str] = []
    try:
        module = ast.parse(text)
    except (SyntaxError, ValueError):
        return out
    for node in ast.walk(module):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            out.extend(node.value.value.splitlines())
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not _STRING_LITERAL.search(stripped):
            out.append(stripped)
    return out


def unattributed_requirements(text: str, known_stories: frozenset[str]) -> set[str]:
    """Requirements a file claims in prose while naming no story at all — invisible proof.

    This is `TECH-017` finding 6's actual detector. Strictness cannot supply it: a tagged file
    carries its id and was never invisible, and the file this was built for —
    ``test_memory_repository_core.py``, whose ``\"\"\"FR-7: Transition to ARCHIVED...\"\"\"`` is a
    deliberate attribution — names no capability anywhere, so no citation rule can recover the owner.
    A human decides which story it belongs to; this only finds the candidates.

    ``known_stories`` is the real registry — every id with a design directory. Shape is deliberately
    not trusted: an earlier version matched any ``XX-N`` token and so treated this file's own
    ``RT-3``/``RT-8`` round-trip case numbers as an owner, silently excusing it.

    Reads comments and docstrings, never string literals, so requirement ids fed to the code under
    test are not mistaken for claims about it.
    """
    if strict_citations(text):
        return set()
    prose = _prose_lines(text)
    if not prose:
        return set()
    joined = "\n".join(prose)
    mentioned = set(_REQ.findall(joined))
    if not mentioned:
        return set()
    if any(story in joined for story in known_stories):
        return set()
    return mentioned
