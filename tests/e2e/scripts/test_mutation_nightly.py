# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The journey a timer performs at 03:00, run as a command.

Proves: TECH-049 FR-10

The seam between the timer and the session is a **command line**, so this runs that exact line as a
subprocess: discover corpora beneath a directory, build a sandbox, judge, write a report, exit.
Nothing here mocks anything — if the corpus, the runner, the verdicts or the report disagree, this
is where it shows.

**Scoped to one feature directory, measured 2026-08-16.** Pointed at the whole of
`docs/roadmap/features` this test ran all 24 mutants and took **117.3s of a 178s suite** — it was
the critical path of every full run, at every commit boundary, and it grew with every campaign
anybody wrote. The claim it makes does not need that: the command line either works or it does not,
and three mutants prove it as well as twenty-four. The real nightly still runs the whole tree, which
is what the timer's `ExecStart` says and what `test_mutation_timer_units.py` asserts.

What narrowing the directory *would* have cost is covered instead by `TestCorpusDiscovery` below —
a filesystem walk over the real tree, in milliseconds, asserting every corpus is found. That is a
stronger claim than the old one, which only checked that `TECH-049` appeared among the results.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

#: One feature's corpus, not the whole tree. `TECH-049`'s three mutants are scoped to a unit file,
#: so the session finishes in seconds and its cost stays flat as the corpus grows. The directory —
#: rather than the file — is deliberate: `--corpus-dir` is what the timer's `ExecStart` passes, so
#: the discovery walk stays on the path this test exercises.
CHEAP_CORPUS_DIR = "docs/roadmap/features/topic_07_technical_debt/TECH-049"


@pytest.mark.e2e
class TestNightlySession:
    """What the machine does while nobody is watching."""

    def test_the_timers_command_line_runs_the_real_corpus(self, tmp_path: Path) -> None:
        import sys

        store = tmp_path / "sessions"
        done = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "mutation.py"),
                "--corpus-dir",
                CHEAP_CORPUS_DIR,
                "--out",
                str(store),
                "--no-baseline",
                # `TECH-055`: `main` folds its report into a ledger, and the default is the real
                # `scripts/baselines/mutation_findings.json`. Without an override, every suite run
                # rewrites the file the morning gate reads.
                "--ledger",
                str(tmp_path / "ledger.json"),
            ],
            cwd=REPO_ROOT,
            env={"PY_COLORS": "0", "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode in {0, 1}, done.stderr
        records = list(store.glob("*.json"))
        assert len(records) == 1, "the nightly run must leave a report behind"
        assert "_full" in records[0].name, "and it must say it swept the whole corpus"

        record = json.loads(records[0].read_text(encoding="utf-8"))
        features = {str(m["id"]).split(" ")[0] for m in record["mutants"]}
        assert "TECH-049" in features, "the corpus discovered its own first campaign"
        # Accounting used to compare two stored totals. Both were derived from the results, so
        # they could only disagree if something wrote them wrong — a check on the writer, not on
        # the run. What matters is that every mutant judged carries a verdict.
        assert record["mutants"], "a session that judged nothing is not a session that passed"
        assert all(m.get("verdict") for m in record["mutants"]), (
            "accounting: every mutant that returned carries a verdict"
        )
        # `NFR-3` says no **sandbox** path may survive, and `/tmp/sw-` is what a sandbox is.
        # This asserted `"/tmp/"` outright, which is a stricter claim than the requirement and
        # held only while no mutant's captured output happened to mention another `/tmp` path.
        # One now does: pytest rewrites `assert latest_covering_record(store) is None` into a
        # message containing the store's own `tmp_path`, and that is neither a sandbox path nor
        # something the sanitiser should rewrite. Assert the requirement, not a proxy for it.
        written = records[0].read_text(encoding="utf-8")
        assert "/tmp/sw-" not in written, "the sandbox is gone; nothing may point into it"


@pytest.mark.e2e
class TestCorpusDiscovery:
    """What the session finds before it runs anything — the half the scoping above gave up."""

    def test_every_corpus_in_the_repository_is_discovered(self) -> None:
        """The nightly's `--corpus-dir docs/roadmap/features` must see all of them.

        A filesystem walk, so it costs milliseconds and can assert the whole tree rather than the
        one corpus a session had time to reach. `discover_corpora` had **no test at all** before
        this: the only thing exercising it was the 117s session above, which asserted merely that
        `TECH-049` appeared — a corpus that went missing would not have failed anything.

        Verified by mutation rather than pinned in a corpus, and the reason is a trap worth naming:
        a campaign scoped to **this file** would recurse without bound. The session above runs
        `TECH-049`'s corpus, so a mutant living there would run this file inside a sandbox, where
        this test spawns another session over the same corpus, and so on. `glob` for `rglob` and a
        `[:1]` truncation were both confirmed KILLED by hand instead.
        """
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "mutation", REPO_ROOT / "scripts" / "mutation.py"
        )
        assert spec is not None and spec.loader is not None
        mutation = importlib.util.module_from_spec(spec)
        sys.modules["mutation"] = mutation
        spec.loader.exec_module(mutation)

        features = REPO_ROOT / "docs" / "roadmap" / "features"
        found = {path.parent.name for path in mutation.discover_corpora(features)}

        # Derived from the NAMING CONTRACT — `<ID>/<ID>_mutants.json`, which `_corpus.py` enforces
        # — and not from the same `rglob` the implementation uses. Recomputing the glob here would
        # restate `discover_corpora` and could never disagree with it.
        expected = {
            directory.name
            for topic in features.iterdir()
            if topic.is_dir()
            for directory in topic.iterdir()
            if directory.is_dir() and (directory / f"{directory.name}_mutants.json").is_file()
        }

        assert found == expected, "a corpus exists that the nightly session would never open"
        assert len(found) >= 4, f"expected the repository's corpora, found {sorted(found)}"
