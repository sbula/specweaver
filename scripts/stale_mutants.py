#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""List every mutant whose code moved, or whose anchor is not there exactly once, across all corpora.

    .venv/bin/python scripts/stale_mutants.py

Exit 1 when any is listed, 2 when a corpus cannot be read. Retired campaigns are skipped; an
unhashed mutant is not STALE, but its anchor is still checked. The `cb` gate runs this, so a commit
that removes or duplicates an anchor fails at once, not in the next night's corpus run. After moving code: re-anchor each listed mutant (its anchor must
match exactly once), re-pin it with `_corpus.py --refresh`, and rerun its corpus.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _corpus

if TYPE_CHECKING:
    from collections.abc import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]


def _anchors(mutant: _corpus.Mutant, root: Path) -> int:
    """How often the text the mutation tool replaces is in the file; it needs exactly one."""
    try:
        return (root / mutant.file).read_text(encoding="utf-8").count(mutant.old)
    except OSError:
        return 0


def stale(corpora: Iterable[Path], root: Path) -> list[str]:
    """One `<corpus> <requirement> <mutant id>` line per STALE mutant or misplaced anchor."""
    found = []
    for path in corpora:
        for campaign in _corpus.load_corpus(path).campaigns:
            if campaign.retired:
                continue
            for mutant in campaign.mutants:
                line = f"{path} {campaign.requirement} {mutant.id}"
                if _corpus.drift_of(mutant, root) == _corpus.STALE:
                    found.append(line)
                elif (count := _anchors(mutant, root)) != 1:
                    found.append(f"{line} (anchor found {count} times)")
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--features", default=str(REPO_ROOT / "docs" / "roadmap" / "features"))
    ap.add_argument("--root", default=str(REPO_ROOT), help="repo root the mutants' files live in")
    args = ap.parse_args(argv)
    corpora = sorted(Path(args.features).rglob("*_mutants.json"))
    try:
        lines = stale(corpora, Path(args.root))
    except _corpus.CorpusError as exc:  # expected: a broken corpus is named, not a traceback
        print(f"could not read a corpus: {exc}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    print(f"{len(lines)} stale mutant(s) in {len(corpora)} corpora")
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
