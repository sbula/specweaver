# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A sub-feature identifier is spelled one way: `SF-` and exactly two zero-padded digits.

Padded was already the overwhelming norm — 166 document filenames against 16 — so this pins
existing practice rather than imposing a convention. The outliers predated any statement of the
rule, and a reader searching for `SF-03` simply did not find `SF-3`.

**Scope is deliberately the format half only.** The sibling rule — that a bare `SF-NN` outside its
owning story's folder must name that story — is not checked here. Detecting it lexically was
attempted and abandoned: three successive refinements each reported violations that turned out to
be correct in context, and the surviving candidates were almost all legitimate references whose
story is named in the same entry rather than the same clause. A rule that cannot be measured
without judgement cannot be enforced by a regex, and asserting it badly would be worse than not
asserting it. See `TECH-027`'s design.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

#: The skill trees are scanned too, and that is not thoroughness for its own sake: the design
#: skill's template used `### SF-1:` until 2026-08-12, so the document that teaches the convention
#: was teaching the form it forbids. Every design written from it inherited that. `.agents/` is kept
#: byte-identical to `.claude/` by `check_skill_sync`, so scanning both catches a drifted copy.
SCANNED = (DOCS, ROOT / ".claude" / "skills", ROOT / ".agents" / "skills")

#: `SF-` followed by exactly one digit. The lookarounds keep `SF-01` and `_sf01_` out of it.
SINGLE_DIGIT = re.compile(r"(?<![\w-])SF-\d(?![\d])")

#: A reference tied to the pre-registry feature numbering (`Feature 3.32 SF-4`). Those sub-features
#: belong to a scheme that no longer exists, so padding them would invent an identifier.
LEGACY_CONTEXT = re.compile(r"[Ff]eature\s+\d+\.\d+")

#: Wholly a historical record of the pre-registry scheme — its own filename says so.
LEGACY_DOCUMENTS = {"legacy_feature_map.md"}

#: The padded form, used to spot a line that is *demonstrating* the contrast rather than committing
#: it. A document stating the rule has to quote the form it forbids — "`SF-01`, never `SF-1`" — and
#: flagging that would make the contract unwritable, the same way R5 exempts citation tags from the
#: registry-id ban it enforces on names. Narrow on purpose: the padded form must be on the SAME
#: line, so a document cannot excuse a stray `SF-3` by mentioning `SF-03` somewhere else.
PADDED = re.compile(r"(?<![\w-])SF-\d\d(?![\d])")


def _offenders() -> list[str]:
    found: list[str] = []
    for root in SCANNED:
        for path in sorted(root.rglob("*.md")):
            if path.name in LEGACY_DOCUMENTS:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            # Judged per PARAGRAPH, reported per line. Both exemptions — legacy context and the
            # padded-form contrast — are properties of the surrounding sentence, and a sentence
            # spans several lines once prose is wrapped to the 200-char rule. Judging per line
            # made them depend on where the wrap happened to fall: re-wrapping
            # `special_patterns_and_adaptations.md` moved the word "feature" off `3.32c SF-2`'s
            # line and turned a legacy reference into a violation.
            for number, line in enumerate(lines, 1):
                if not (SINGLE_DIGIT.search(line) and not PADDED.search(line)):
                    continue
                start = number - 1
                while start > 0 and lines[start - 1].strip():
                    start -= 1
                end = number
                while end < len(lines) and lines[end].strip():
                    end += 1
                block = " ".join(lines[start:end])
                if LEGACY_CONTEXT.search(block) or PADDED.search(block):
                    continue
                rel = path.relative_to(ROOT).as_posix()
                found.append(f"{rel}:{number}: {line.strip()[:80]}")
    return found


def test_no_document_spells_a_sub_feature_with_one_digit() -> None:
    """`SF-3` and `SF-03` are the same sub-feature spelled two ways, and only one is searchable."""
    offenders = _offenders()

    assert offenders == [], "single-digit sub-feature ids:\n  " + "\n  ".join(offenders[:20])


def test_no_document_filename_spells_it_with_one_digit() -> None:
    """The filename half, which landed first — `_sf1_` became `_sf01_` across 16 files.

    Pinned separately because a filename is what inbound links resolve against: prose can be wrong
    and merely confusing, a filename can be wrong and break a reference.
    """
    unpadded = sorted(p.name for r in SCANNED for p in r.rglob("*_sf[0-9]_*"))

    assert unpadded == [], f"unpadded filenames: {unpadded}"


def test_the_legacy_scheme_is_left_alone() -> None:
    """The exclusion is real, not a loophole — it must actually be exercised.

    `legacy_feature_map.md` records a numbering scheme that predates the registry, where a
    sub-feature belonged to `Feature 3.14a` rather than to a story id. Padding those would invent
    identifiers for something that no longer exists. If this file ever stops containing them, the
    exclusion should be deleted rather than left as an unexplained special case.
    """
    legacy = DOCS / "architecture" / "02_bounded_contexts" / "legacy_feature_map.md"

    assert legacy.is_file(), "the excluded document has moved — revisit the exclusion"
    assert SINGLE_DIGIT.search(legacy.read_text(encoding="utf-8")), (
        "no single-digit ids remain in the legacy record, so the exclusion is now dead and should go"
    )


def test_the_demonstration_exemption_is_narrow() -> None:
    """A line may show the forbidden form only while showing the correct one beside it.

    Without this the exemption would be a hole: any document could carry a stray `SF-3` as long as
    some other line mentioned a padded id.
    """
    from tests.unit.test_sub_feature_identifiers import PADDED, SINGLE_DIGIT

    demonstrating = "the format is `SF-01`, never `SF-1`"
    committing = "see `SF-3` for the details"

    assert SINGLE_DIGIT.search(demonstrating) and PADDED.search(demonstrating)
    assert SINGLE_DIGIT.search(committing) and not PADDED.search(committing)
