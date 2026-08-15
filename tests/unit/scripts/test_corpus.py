# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The mutation campaign corpus — load it, or refuse it loudly.

Proves: TECH-049 FR-1, FR-1a

A campaign targets one (N)FR and holds several mutants that each try to break it. The corpus is
version-controlled beside the design it tests, so a malformed file must fail at parse time rather
than after a sandbox has been built — `_mutate_campaign.load_campaign` established that order and
this keeps it.

Two rules here are not obvious and are the reason most of these stories exist:

* **The derived id is the mutant's identity across runs.** `FR-11a` recurrence counts and `FR-12`
  override entries have to name the same mutant tonight and next month, and a hand-typed id drifts.
  It is composed, never accepted.
* **`feature` must match the filename**, which is what lets rule 6 be a single-file check: two
  corpus files cannot claim the same feature, so a cross-file id collision is impossible by
  construction rather than by luck.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_corpus.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_corpus", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_corpus"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def corpus() -> ModuleType:
    return _load()


def _mutant(**over: Any) -> dict[str, Any]:
    base = {
        "id": "isolation-off",
        "file": "src/specweaver/x.py",
        "symbol": "apply_session_policy",
        "old": "return policy.enabled",
        "new": "return False",
        "breaks": "no worktree is created",
    }
    return {**base, **over}


def _campaign(**over: Any) -> dict[str, Any]:
    base = {
        "requirement": "FR-98",
        "title": "Worktree-bounded multi-step e2e",
        "scope": ["tests/e2e/sandbox/test_session_worktree_isolation_e2e.py"],
        "mutants": [_mutant()],
    }
    return {**base, **over}


def _write(tmp_path: Path, feature: str = "C-EXEC-06", **over: Any) -> Path:
    """A corpus file named the way the loader expects: `<ID>_mutants.json`."""
    body: dict[str, Any] = {"schema": 1, "feature": feature, "campaigns": [_campaign()]}
    body.update(over)
    path = tmp_path / f"{feature}_mutants.json"
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


class TestLoadCorpus:
    """A well-formed corpus loads, and its mutants carry a composed identity."""

    def test_a_valid_corpus_loads_its_campaigns(self, corpus: ModuleType, tmp_path: Path) -> None:
        loaded = corpus.load_corpus(_write(tmp_path))
        assert loaded.feature == "C-EXEC-06"
        assert [c.requirement for c in loaded.campaigns] == ["FR-98"]
        assert [m.id for m in loaded.campaigns[0].mutants] == ["isolation-off"]

    def test_the_mutant_id_is_derived_not_taken(self, corpus: ModuleType, tmp_path: Path) -> None:
        """`FR-1a` — identity is composed from feature + requirement + local id.

        Asserted against a literal rather than by re-composing it from the loaded object, which
        would only prove the loader agrees with itself.
        """
        loaded = corpus.load_corpus(_write(tmp_path))
        assert loaded.campaigns[0].mutants[0].derived_id == "C-EXEC-06 FR-98 isolation-off"

    def test_two_campaigns_both_load(self, corpus: ModuleType, tmp_path: Path) -> None:
        second = _campaign(requirement="FR-99", mutants=[_mutant(id="policy-null")])
        path = _write(tmp_path, campaigns=[_campaign(), second])
        loaded = corpus.load_corpus(path)
        assert [c.requirement for c in loaded.campaigns] == ["FR-98", "FR-99"]


class TestLoadCorpusBoundaries:
    """Empty collections, and the states that are legal but easy to mistake for errors."""

    def test_an_empty_mutant_list_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, campaigns=[_campaign(mutants=[])])
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_an_empty_scope_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """A campaign with no scope would run its mutants against nothing and read as a survival."""
        path = _write(tmp_path, campaigns=[_campaign(scope=[])])
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_a_retired_campaign_loads_and_is_marked(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        """Retire marks, never deletes — the record that it was measured has to survive."""
        retired = _campaign(retired={"reason": "requirement descoped", "date": "2026-08-15"})
        loaded = corpus.load_corpus(_write(tmp_path, campaigns=[retired]))
        assert loaded.campaigns[0].retired is not None
        assert loaded.campaigns[0].retired["reason"] == "requirement descoped"

    def test_a_missing_symbol_sha_is_legal(self, corpus: ModuleType, tmp_path: Path) -> None:
        """The normal authoring flow: a human writes a mutant without knowing the hash.

        Absent is `UNHASHED`, not `STALE`, and never an error — otherwise every newly authored
        mutant would be born invalid and the corpus could not grow.
        """
        loaded = corpus.load_corpus(_write(tmp_path))
        assert loaded.campaigns[0].mutants[0].symbol_sha is None

    def test_a_recorded_symbol_sha_is_kept(self, corpus: ModuleType, tmp_path: Path) -> None:
        pinned = _campaign(mutants=[_mutant(symbol_sha="sha256:abc")])
        loaded = corpus.load_corpus(_write(tmp_path, campaigns=[pinned]))
        assert loaded.campaigns[0].mutants[0].symbol_sha == "sha256:abc"


class TestLoadCorpusDegradation:
    """Unreadable or unknown input fails at parse time, before any sandbox work."""

    def test_an_unknown_schema_is_refused_naming_the_version(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, schema=99)
        with pytest.raises(corpus.CorpusError, match="99"):
            corpus.load_corpus(path)

    def test_malformed_json_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "C-EXEC-06_mutants.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_a_missing_file_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(tmp_path / "C-EXEC-06_mutants.json")

    @pytest.mark.parametrize("key", ["requirement", "scope", "mutants"])
    def test_a_campaign_missing_a_key_is_refused(
        self, corpus: ModuleType, tmp_path: Path, key: str
    ) -> None:
        broken = {k: v for k, v in _campaign().items() if k != key}
        path = _write(tmp_path, campaigns=[broken])
        with pytest.raises(corpus.CorpusError, match=key):
            corpus.load_corpus(path)

    @pytest.mark.parametrize("key", ["id", "file", "symbol", "old", "new", "breaks"])
    def test_a_mutant_missing_a_key_is_refused(
        self, corpus: ModuleType, tmp_path: Path, key: str
    ) -> None:
        broken = {k: v for k, v in _mutant().items() if k != key}
        path = _write(tmp_path, campaigns=[_campaign(mutants=[broken])])
        with pytest.raises(corpus.CorpusError, match=key):
            corpus.load_corpus(path)


class TestLoadCorpusHostileInput:
    """The three ways a corpus can be well-formed JSON and still be a lie."""

    def test_an_identical_replacement_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """`old == new` mutates nothing, so the run would report a false survival."""
        same = _campaign(mutants=[_mutant(new="return policy.enabled")])
        path = _write(tmp_path, campaigns=[same])
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_a_duplicate_derived_id_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """Two mutants resolving to one identity would collapse into each other across runs.

        Recurrence counts and override entries address a mutant by this string; if two answer to
        it, one silently inherits the other's history.
        """
        twin = _campaign(mutants=[_mutant(), _mutant(new="return None")])
        path = _write(tmp_path, campaigns=[twin])
        with pytest.raises(corpus.CorpusError, match="isolation-off"):
            corpus.load_corpus(path)

    def test_a_feature_disagreeing_with_the_filename_is_refused(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        """This is what makes the uniqueness check a single-file check.

        If a file may declare any feature, two files can claim the same one and a duplicate id
        across them becomes invisible without loading the whole corpus.
        """
        path = tmp_path / "C-EXEC-06_mutants.json"
        body = {"schema": 1, "feature": "B-INTL-09", "campaigns": [_campaign()]}
        path.write_text(json.dumps(body), encoding="utf-8")
        with pytest.raises(corpus.CorpusError, match="B-INTL-09"):
            corpus.load_corpus(path)


class TestLoadCorpusErrorMessages:
    """A message that says only 'missing key' costs the reader a search (R-2)."""

    def test_a_failure_names_the_file_the_campaign_and_the_mutant(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        broken = {k: v for k, v in _mutant().items() if k != "old"}
        path = _write(tmp_path, campaigns=[_campaign(mutants=[broken])])
        with pytest.raises(corpus.CorpusError) as caught:
            corpus.load_corpus(path)
        message = str(caught.value)
        assert "C-EXEC-06_mutants.json" in message
        assert "FR-98" in message
        assert "isolation-off" in message


# --- CB-2: symbol resolution, hashing, drift -------------------------------------------------

_SOURCE = '''\
"""Module docstring."""


def apply_session_policy(policy):
    """Decide whether the run is isolated."""
    if policy is None:
        return False
    return policy.enabled


class SessionPolicy:
    def run(self, ctx):
        """Class A's run."""
        return ctx.enabled


class OtherPolicy:
    def run(self, ctx):
        """Class B's run — same bare name."""
        return ctx.disabled


def redefined(x):
    return 1


def redefined(x):  # noqa: F811 — deliberate: two definitions at ONE level
    return 2
'''


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "isolation.py"
    path.write_text(_SOURCE, encoding="utf-8")
    return path


class TestSymbolSha:
    """`symbol_sha` — a fingerprint of behaviour, not of formatting."""

    def test_it_resolves_a_module_level_function(self, corpus: ModuleType, source: Path) -> None:
        assert corpus.symbol_sha(source.read_text(), "apply_session_policy").startswith("sha256:")

    def test_a_dotted_path_reaches_a_method(self, corpus: ModuleType, source: Path) -> None:
        assert corpus.symbol_sha(source.read_text(), "SessionPolicy.run").startswith("sha256:")

    def test_a_dotted_path_disambiguates_a_repeated_bare_name(
        self, corpus: ModuleType, source: Path
    ) -> None:
        """Why the path is dotted at all.

        Measured across `src/`: 25 files carry duplicate symbol names, one holding `__init__` six
        times. A bare `run` here is two different methods, and resolving it to "the first one" is
        how a mutant silently measures the wrong code.
        """
        text = source.read_text()
        assert corpus.symbol_sha(text, "SessionPolicy.run") != corpus.symbol_sha(
            text, "OtherPolicy.run"
        )

    def test_a_name_defined_twice_at_one_level_is_refused(
        self, corpus: ModuleType, source: Path
    ) -> None:
        """The ambiguity branch — and it took a mutant to notice nothing reached it.

        The first version of this test asked for a bare `run`, which is a *method*: at module level
        it is simply absent, so the assertion passed through the "no symbol named" branch and the
        duplicate check went unexercised. Neutralising `if len(found) > 1:` left the suite green.
        A redefinition is the only shape that reaches it.
        """
        with pytest.raises(corpus.CorpusError, match="2 times"):
            corpus.symbol_sha(source.read_text(), "redefined")

    def test_a_method_name_is_not_visible_at_module_level(
        self, corpus: ModuleType, source: Path
    ) -> None:
        """`run` exists twice in the file but at neither module level — resolution is per level."""
        with pytest.raises(corpus.CorpusError, match="no function or class named"):
            corpus.symbol_sha(source.read_text(), "run")

    def test_an_absent_symbol_is_refused_naming_the_segment(
        self, corpus: ModuleType, source: Path
    ) -> None:
        with pytest.raises(corpus.CorpusError, match="Missing"):
            corpus.symbol_sha(source.read_text(), "SessionPolicy.Missing")

    def test_reformatting_does_not_change_the_hash(self, corpus: ModuleType, source: Path) -> None:
        """A `ruff format` pass must not mark every mutant stale."""
        spaced = _SOURCE.replace("    return policy.enabled", "\n    return  policy.enabled")
        assert corpus.symbol_sha(spaced, "apply_session_policy") == corpus.symbol_sha(
            _SOURCE, "apply_session_policy"
        )

    def test_renaming_a_local_does_change_the_hash(self, corpus: ModuleType) -> None:
        renamed = _SOURCE.replace("policy.enabled", "policy.active")
        assert corpus.symbol_sha(renamed, "apply_session_policy") != corpus.symbol_sha(
            _SOURCE, "apply_session_policy"
        )

    def test_rewording_the_docstring_does_not_change_the_hash(self, corpus: ModuleType) -> None:
        """Q1 — the only guard on it, and the reason the strip step exists.

        `ast.dump` includes docstrings because they are real nodes, so without stripping, editing
        prose would report the claim as moved when nothing moved.
        """
        reworded = _SOURCE.replace(
            '"""Decide whether the run is isolated."""', '"""Reworded entirely."""'
        )
        assert corpus.symbol_sha(reworded, "apply_session_policy") == corpus.symbol_sha(
            _SOURCE, "apply_session_policy"
        )

    def test_unparseable_source_is_refused(self, corpus: ModuleType) -> None:
        with pytest.raises(corpus.CorpusError):
            corpus.symbol_sha("def broken(:\n", "broken")


class TestCheckAnchor:
    """Rule 9 — the anchor must be unique *within the symbol*, not the file."""

    def test_an_anchor_present_once_is_accepted(self, corpus: ModuleType) -> None:
        corpus.check_anchor(_SOURCE, "apply_session_policy", "return policy.enabled")

    def test_an_anchor_outside_the_symbol_is_refused(self, corpus: ModuleType) -> None:
        """The mutant claims a symbol it is not inside — it would mutate someone else's code."""
        with pytest.raises(corpus.CorpusError):
            corpus.check_anchor(_SOURCE, "apply_session_policy", "return ctx.disabled")

    def test_an_anchor_repeated_inside_the_symbol_is_refused(self, corpus: ModuleType) -> None:
        twice = _SOURCE.replace(
            "    return policy.enabled", "    if policy.enabled:\n        return policy.enabled"
        )
        with pytest.raises(corpus.CorpusError, match="2 times"):
            corpus.check_anchor(twice, "apply_session_policy", "policy.enabled")

    def test_a_file_scoped_duplicate_is_still_accepted_inside_one_symbol(
        self, corpus: ModuleType
    ) -> None:
        """The point of scoping to the symbol: `return False` is not file-unique and need not be."""
        corpus.check_anchor(_SOURCE, "apply_session_policy", "return False")


class TestDriftOf:
    """`drift_of` — reports, never acts. Verdicts belong to SF-03."""

    def _pinned(self, corpus: ModuleType, source: Path, sha: str | None) -> Any:
        return corpus.Mutant(
            id="isolation-off",
            file=source.name,
            symbol="apply_session_policy",
            old="return policy.enabled",
            new="return False",
            breaks="isolation never engages",
            derived_id="X FR-97 isolation-off",
            symbol_sha=sha,
        )

    def test_a_matching_hash_is_ok(self, corpus: ModuleType, source: Path) -> None:
        sha = corpus.symbol_sha(source.read_text(), "apply_session_policy")
        assert corpus.drift_of(self._pinned(corpus, source, sha), source.parent) == "OK"

    def test_an_absent_hash_is_unhashed_not_stale(self, corpus: ModuleType, source: Path) -> None:
        """A newly authored mutant is legal and must not read as drift."""
        assert corpus.drift_of(self._pinned(corpus, source, None), source.parent) == "UNHASHED"

    def test_a_changed_symbol_is_stale(self, corpus: ModuleType, source: Path) -> None:
        stale = self._pinned(corpus, source, "sha256:deadbeef")
        assert corpus.drift_of(stale, source.parent) == "STALE"

    def test_a_vanished_symbol_is_stale_not_an_error(
        self, corpus: ModuleType, source: Path
    ) -> None:
        """The code a claim rested on was removed — the most valuable signal in the corpus."""
        source.write_text('"""Emptied."""\n', encoding="utf-8")
        stale = self._pinned(corpus, source, "sha256:whatever")
        assert corpus.drift_of(stale, source.parent) == "STALE"

    def test_a_vanished_file_is_stale_not_an_error(self, corpus: ModuleType, source: Path) -> None:
        stale = self._pinned(corpus, source, "sha256:whatever")
        source.unlink()
        assert corpus.drift_of(stale, source.parent) == "STALE"


# --- CB-3: refresh and retire ------------------------------------------------------------------


@pytest.fixture
def corpus_with_source(tmp_path: Path) -> tuple[Path, Path]:
    """A corpus whose one mutant points at a real source file in the same directory."""
    src = tmp_path / "isolation.py"
    src.write_text(_SOURCE, encoding="utf-8")
    body = {
        "schema": 1,
        "feature": "C-EXEC-06",
        "campaigns": [
            {
                "requirement": "FR-98",
                "title": "Worktree-bounded",
                "scope": ["tests/e2e/x.py"],
                "mutants": [
                    {
                        "id": "isolation-off",
                        "file": "isolation.py",
                        "symbol": "apply_session_policy",
                        "old": "return policy.enabled",
                        "new": "return False",
                        "breaks": "isolation never engages",
                    }
                ],
            }
        ],
    }
    path = tmp_path / "C-EXEC-06_mutants.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path, tmp_path


class TestRefresh:
    """`refresh` — pin one mutant's hash, deliberately and one at a time."""

    def test_it_pins_an_unhashed_mutant(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, root = corpus_with_source
        sha = corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)
        assert sha.startswith("sha256:")
        reloaded = corpus.load_corpus(path)
        assert reloaded.campaigns[0].mutants[0].symbol_sha == sha
        assert corpus.drift_of(reloaded.campaigns[0].mutants[0], root) == "OK"

    def test_it_updates_a_stale_mutant(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, root = corpus_with_source
        corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)
        (root / "isolation.py").write_text(
            _SOURCE.replace("policy.enabled", "policy.active"), encoding="utf-8"
        )
        assert corpus.drift_of(corpus.load_corpus(path).campaigns[0].mutants[0], root) == "STALE"

        corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)
        assert corpus.drift_of(corpus.load_corpus(path).campaigns[0].mutants[0], root) == "OK"

    def test_it_leaves_every_unrelated_line_untouched(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        """Q7 — the diff IS the review. A refresh that reformats the file destroys that.

        Compared with trailing commas normalised away, because JSON cannot do better: inserting a
        key necessarily puts a comma on the line above it. The first version of this test asserted
        literal byte preservation and failed on exactly that comma — the belief was wrong, not the
        code. What must hold is that no *content* line disappears and only the pin is added.
        """
        path, root = corpus_with_source
        strip = lambda lines: [line.rstrip(",") for line in lines]  # noqa: E731
        before = strip(path.read_text(encoding="utf-8").splitlines())
        corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)
        after = strip(path.read_text(encoding="utf-8").splitlines())

        assert [line for line in before if line not in after] == []
        added = [line for line in after if line not in before]
        assert len(added) == 1
        assert "symbol_sha" in added[0]

    def test_refreshing_a_vanished_symbol_fails(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        """Pinning a hash for a symbol that is gone would launder drift into a green corpus."""
        path, root = corpus_with_source
        (root / "isolation.py").write_text('"""Emptied."""\n', encoding="utf-8")
        with pytest.raises(corpus.CorpusError):
            corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)

    def test_refreshing_a_vanished_file_fails(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, root = corpus_with_source
        (root / "isolation.py").unlink()
        with pytest.raises(corpus.CorpusError):
            corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)

    def test_an_unknown_derived_id_fails(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, root = corpus_with_source
        with pytest.raises(corpus.CorpusError, match="nope"):
            corpus.refresh(path, "C-EXEC-06 FR-98 nope", root)


class TestRetire:
    """`retire` — mark, never delete."""

    def test_it_marks_the_campaign_and_keeps_its_mutants(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, _ = corpus_with_source
        corpus.retire(path, "FR-98", reason="requirement descoped", date="2026-08-15")
        reloaded = corpus.load_corpus(path)
        assert reloaded.campaigns[0].retired == {
            "reason": "requirement descoped",
            "date": "2026-08-15",
        }
        assert len(reloaded.campaigns[0].mutants) == 1

    def test_retiring_an_unknown_requirement_fails(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, _ = corpus_with_source
        with pytest.raises(corpus.CorpusError, match="FR-99"):
            corpus.retire(path, "FR-99", reason="x", date="2026-08-15")

    def test_it_leaves_every_unrelated_line_untouched(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, _ = corpus_with_source
        strip = lambda lines: [line.rstrip(",") for line in lines]  # noqa: E731
        before = strip(path.read_text(encoding="utf-8").splitlines())
        corpus.retire(path, "FR-98", reason="descoped", date="2026-08-15")
        after = strip(path.read_text(encoding="utf-8").splitlines())
        assert [line for line in before if line not in after] == []


class TestMain:
    """The CLI — one mutant, one command. There is no bulk flag, and that is the design."""

    def test_refresh_pins_and_reports(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path], capsys: Any
    ) -> None:
        path, root = corpus_with_source
        code = corpus.main(
            [
                "--corpus",
                str(path),
                "--root",
                str(root),
                "--refresh",
                "C-EXEC-06 FR-98 isolation-off",
            ]
        )
        assert code == 0
        assert "sha256:" in capsys.readouterr().out
        assert corpus.load_corpus(path).campaigns[0].mutants[0].symbol_sha is not None

    def test_retire_requires_a_reason(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        """A tombstone with no reason is a deletion with extra steps."""
        path, _ = corpus_with_source
        with pytest.raises(SystemExit):
            corpus.main(["--corpus", str(path), "--retire", "FR-98"])

    def test_a_failure_exits_nonzero_and_says_why(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path], capsys: Any
    ) -> None:
        path, root = corpus_with_source
        code = corpus.main(
            ["--corpus", str(path), "--root", str(root), "--refresh", "C-EXEC-06 FR-98 nope"]
        )
        assert code == 2
        assert "nope" in capsys.readouterr().err

    def test_it_refuses_to_do_nothing(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, _ = corpus_with_source
        with pytest.raises(SystemExit):
            corpus.main(["--corpus", str(path)])


class TestMaintenanceGaps:
    """Branches the CB-3 gate found unexercised — including a whole CLI path.

    `main()`'s retire branch had zero coverage: four CLI tests existed and every one exited at
    `ap.error` or in the refresh branch, so the argument-to-call wiring and its success message
    shipped unrun. The function underneath was tested; the path to it was not.
    """

    def test_retire_through_the_cli_marks_and_reports(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path], capsys: Any
    ) -> None:
        """[Happy Path] Story 1 — the branch that had no test at all."""
        path, _ = corpus_with_source
        code = corpus.main(
            [
                "--corpus",
                str(path),
                "--retire",
                "FR-98",
                "--reason",
                "descoped",
                "--date",
                "2026-08-15",
            ]
        )
        assert code == 0
        assert "retired" in capsys.readouterr().out
        assert corpus.load_corpus(path).campaigns[0].retired["reason"] == "descoped"

    def test_retiring_twice_updates_the_reason(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        """[Boundary] Story 2 — silently overwriting was undefined by any test."""
        path, _ = corpus_with_source
        corpus.retire(path, "FR-98", reason="first", date="2026-08-15")
        corpus.retire(path, "FR-98", reason="corrected", date="2026-08-16")
        retired = corpus.load_corpus(path).campaigns[0].retired
        assert retired == {"reason": "corrected", "date": "2026-08-16"}

    def test_retire_without_a_date_still_reads(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        """[Boundary] Story 3 — `--date` defaults to empty; the tombstone must still say why."""
        path, _ = corpus_with_source
        assert (
            corpus.main(["--corpus", str(path), "--retire", "FR-98", "--reason", "descoped"]) == 0
        )
        retired = corpus.load_corpus(path).campaigns[0].retired
        assert retired["reason"] == "descoped"
        assert retired["date"] == ""

    def test_an_unwritable_corpus_raises_corpus_error(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path], monkeypatch: Any
    ) -> None:
        """[Degradation] Story 4 — every other path in this module raises CorpusError; so must this.

        A bare OSError escaping the module means the caller has to know about the filesystem to
        catch what this module does, which is the seam leaking.
        """
        path, root = corpus_with_source

        def _no_write(*_a: object, **_k: object) -> None:
            raise OSError("read-only file system")

        monkeypatch.setattr(Path, "write_text", _no_write)
        with pytest.raises(corpus.CorpusError):
            corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)

    def test_retiring_an_unknown_requirement_exits_two(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path], capsys: Any
    ) -> None:
        """[Degradation] Story 5 — the error path through the CLI, not just the function."""
        path, _ = corpus_with_source
        code = corpus.main(["--corpus", str(path), "--retire", "FR-99", "--reason", "x"])
        assert code == 2
        assert "FR-99" in capsys.readouterr().err

    def test_a_badly_named_corpus_is_refused_by_refresh(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] Story 6 — the filename is the feature id, so a wrong name is a wrong claim."""
        stray = tmp_path / "notes.json"
        stray.write_text("{}", encoding="utf-8")
        with pytest.raises(corpus.CorpusError):
            corpus.refresh(stray, "X FR-1 y", tmp_path)

    def test_refresh_and_retire_together_are_rejected(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        """[Hostile] Story 7 — two actions in one invocation is ambiguous, not convenient."""
        path, root = corpus_with_source
        with pytest.raises(SystemExit):
            corpus.main(
                [
                    "--corpus",
                    str(path),
                    "--root",
                    str(root),
                    "--refresh",
                    "C-EXEC-06 FR-98 isolation-off",
                    "--retire",
                    "FR-98",
                    "--reason",
                    "x",
                ]
            )


class TestMaintenanceValidatesFirst:
    """Red/Blue (Phase 7.5): `refresh` and `retire` wrote without validating the corpus first.

    Both read the raw JSON and edited it. A corpus that `load_corpus` would refuse — an unknown
    schema, a duplicate derived id, `old == new` — could therefore be rewritten, producing a file
    that is still unloadable but now *looks* maintained, with a fresh hash pinned inside it.
    """

    def test_refresh_refuses_an_invalid_corpus(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, root = corpus_with_source
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema"] = 99
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        with pytest.raises(corpus.CorpusError, match="99"):
            corpus.refresh(path, "C-EXEC-06 FR-98 isolation-off", root)

    def test_retire_refuses_an_invalid_corpus(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        path, _ = corpus_with_source
        data = json.loads(path.read_text(encoding="utf-8"))
        data["campaigns"][0]["mutants"][0]["new"] = data["campaigns"][0]["mutants"][0]["old"]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        with pytest.raises(corpus.CorpusError):
            corpus.retire(path, "FR-98", reason="x", date="2026-08-15")

    def test_a_traversing_file_path_is_refused(
        self, corpus: ModuleType, corpus_with_source: tuple[Path, Path]
    ) -> None:
        """[Hostile] A mutant must not reach outside the tree it is measuring."""
        path, _root = corpus_with_source
        data = json.loads(path.read_text(encoding="utf-8"))
        data["campaigns"][0]["mutants"][0]["file"] = "../../../etc/passwd"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)
