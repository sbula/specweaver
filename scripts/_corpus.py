#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The mutation campaign corpus — the durable record of what each requirement is measured by.

`_mutate.py` answers one question and `_mutate_campaign.py` asks a list of them, but both take
their input from a JSON file authored once and thrown away. Nothing survives a run, so the question
that matters — *was this requirement protected last month and is it still?* — cannot be asked at
all. This module is the persistent half: a per-feature corpus, version-controlled beside the design
it tests.

## Shape

One file per **feature**, named `<ID>_mutants.json`, holding one **campaign** per (N)FR, each
holding several **mutants** that try to break that one requirement. Per-requirement files were
rejected on arithmetic: 575 requirements exist today and ~1,400 will at full roadmap, against 55
feature files now and ~149 then.

## Two rules that are not obvious

**The mutant id is derived, never taken.** `<feature> <requirement> <id>` is the identity that
recurrence counts and override entries use to name the same mutant across runs, and a hand-typed
one drifts the moment somebody renames a campaign.

**`feature` must match the filename.** That is the whole reason the duplicate-id check can read one
file instead of the corpus: two files cannot claim the same feature, so a collision across files is
impossible by construction rather than by luck.

## What this module does NOT do

It runs nothing. No sandbox, no pytest, no verdicts — it produces validated objects and drift state
for the runner to execute and the evaluator to judge. Validation happens **before** any sandbox
exists, which is the order `load_campaign` established for a reason: building a worktree to
discover a typo is a minute wasted per mistake.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Corpus format version. Bumped only when a change would make an older file misread rather than
#: merely incomplete — a reader that guesses at an unknown shape is how a silent misparse starts.
SCHEMA = 1

_MUTANT_KEYS = ("id", "file", "symbol", "old", "new", "breaks")
_CAMPAIGN_KEYS = ("requirement", "scope", "mutants")
_SUFFIX = "_mutants.json"


class CorpusError(Exception):
    """A corpus file that cannot be trusted, with enough context to find the offending entry.

    Every message names the file, and where the fault is inside one, the campaign and the mutant
    too. A bare "missing key" costs the reader a search through a forty-mutant file, which is the
    kind of friction that stops a corpus being maintained.
    """


@dataclass(frozen=True)
class Mutant:
    """One deliberate edit that should break exactly one requirement."""

    id: str
    file: str
    symbol: str
    old: str
    new: str
    breaks: str
    derived_id: str
    symbol_sha: str | None = None


@dataclass(frozen=True)
class Campaign:
    """The mutants for one (N)FR, and the tests they are judged against."""

    requirement: str
    scope: list[str]
    mutants: list[Mutant]
    title: str = ""
    retired: dict[str, Any] | None = None


@dataclass(frozen=True)
class Corpus:
    """One feature's campaigns, as loaded from its `<ID>_mutants.json`."""

    feature: str
    campaigns: list[Campaign]
    path: Path = field(default_factory=Path)


def feature_of(path: Path) -> str:
    """The feature id a corpus file's name declares.

    The filename is the authority rather than the directory, so a fixture in a temporary directory
    is as loadable as the real thing — a validation rule that can only be exercised inside the real
    tree is a rule that goes untested.
    """
    name = path.name
    if not name.endswith(_SUFFIX):
        raise CorpusError(f"{name}: a corpus file must be named <FEATURE-ID>{_SUFFIX}")
    return name[: -len(_SUFFIX)]


def _require(where: str, data: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        if key not in data or data[key] in (None, "", [], {}):
            raise CorpusError(f"{where}: missing or empty {key!r}")


def _read(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusError(f"{path.name}: cannot read — {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorpusError(f"{path.name}: not valid JSON — {exc}") from exc
    if not isinstance(parsed, dict):
        raise CorpusError(f"{path.name}: expected an object at the top level")
    return parsed


def _mutant_from(raw: dict[str, Any], *, where: str, feature: str, requirement: str) -> Mutant:
    _require(where, raw, _MUTANT_KEYS)
    if raw["old"] == raw["new"]:
        raise CorpusError(
            f"{where}: 'old' and 'new' are identical — that mutates nothing, so the run would "
            "report a survival that means the opposite of what it says"
        )
    path_field = str(raw["file"])
    if path_field.startswith("/") or ".." in Path(path_field).parts:
        raise CorpusError(
            f"{where}: 'file' must be a repo-relative path inside the tree, got {path_field!r}. "
            "A mutant that reaches outside the tree it measures is not measuring that tree"
        )
    return Mutant(
        id=raw["id"],
        file=raw["file"],
        symbol=raw["symbol"],
        old=raw["old"],
        new=raw["new"],
        breaks=raw["breaks"],
        derived_id=f"{feature} {requirement} {raw['id']}",
        symbol_sha=raw.get("symbol_sha"),
    )


def _campaign_from(raw: dict[str, Any], *, path: Path, feature: str) -> Campaign:
    if not isinstance(raw, dict):
        raise CorpusError(f"{path.name}: every campaign must be an object")
    requirement = raw.get("requirement") or "<unnamed campaign>"
    where = f"{path.name} :: {requirement}"
    _require(where, raw, _CAMPAIGN_KEYS)

    mutants = []
    for entry in raw["mutants"]:
        if not isinstance(entry, dict):
            raise CorpusError(f"{where}: every mutant must be an object")
        local = entry.get("id") or "<unnamed mutant>"
        mutants.append(
            _mutant_from(
                entry,
                where=f"{where} :: {local}",
                feature=feature,
                requirement=raw["requirement"],
            )
        )

    return Campaign(
        requirement=raw["requirement"],
        scope=list(raw["scope"]),
        mutants=mutants,
        title=raw.get("title", ""),
        retired=raw.get("retired"),
    )


def load_corpus(path: Path) -> Corpus:
    """Parse and validate one corpus file, or refuse it with the offending entry named.

    Ordered cheapest-first on purpose: a malformed file never reaches the filesystem or the AST
    parser, so a typo costs a parse rather than a worktree.
    """
    feature = feature_of(path)
    data = _read(path)

    schema = data.get("schema")
    if schema != SCHEMA:
        raise CorpusError(
            f"{path.name}: unknown schema {schema!r} (this reader understands {SCHEMA})"
        )

    declared = data.get("feature")
    if declared != feature:
        raise CorpusError(
            f"{path.name}: declares feature {declared!r} but its name says {feature!r}. "
            "They must agree — it is what keeps mutant ids unique without reading every file"
        )

    campaigns_raw = data.get("campaigns")
    if not isinstance(campaigns_raw, list) or not campaigns_raw:
        raise CorpusError(f"{path.name}: 'campaigns' must be a non-empty list")

    campaigns = [_campaign_from(entry, path=path, feature=feature) for entry in campaigns_raw]

    seen: dict[str, str] = {}
    for campaign in campaigns:
        for mutant in campaign.mutants:
            if mutant.derived_id in seen:
                raise CorpusError(
                    f"{path.name}: duplicate mutant id {mutant.derived_id!r}. Two mutants "
                    "answering to one identity collapse into each other across runs, so one "
                    "silently inherits the other's history"
                )
            seen[mutant.derived_id] = campaign.requirement

    return Corpus(feature=feature, campaigns=campaigns, path=path)


# --- symbol resolution, hashing and drift -----------------------------------------------------

#: The node kinds a dotted `symbol` path may name. A mutant anchored outside one of these has no
#: enclosing scope to fingerprint, so it is refused rather than hashed against the whole module —
#: that would mark it stale on every unrelated edit in the file, which is worse than not supporting
#: it at all.
_NAMED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

#: Drift states. Reported here, judged in SF-03 — this module decides nothing.
OK = "OK"
STALE = "STALE"
UNHASHED = "UNHASHED"


def _parse(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise CorpusError(f"cannot parse the source: {exc}") from exc


def resolve_symbol(source: str, symbol: str) -> ast.AST:
    """The node a dotted path names — `f`, or `Class.method`.

    Resolved one segment at a time through each node's **direct body**, never by walking the whole
    tree. Measured across `src/`: 25 files carry duplicate symbol names and one holds `__init__`
    six times, so a tree-wide search would resolve a bare name to whichever it met first and the
    mutant would silently measure different code than its claim describes.
    """
    node: Any = _parse(source)
    for segment in symbol.split("."):
        if not segment:
            raise CorpusError(f"{symbol!r}: empty path segment")
        found = [
            child
            for child in getattr(node, "body", [])
            if isinstance(child, _NAMED) and child.name == segment
        ]
        if not found:
            raise CorpusError(f"{symbol!r}: no function or class named {segment!r} at that level")
        if len(found) > 1:
            raise CorpusError(
                f"{symbol!r}: {segment!r} is defined {len(found)} times at that level — "
                "qualify it, e.g. 'ClassName.method'"
            )
        node = found[0]
    return node


def _without_docstring(node: ast.AST) -> ast.AST:
    """A copy whose leading docstring is gone, so prose edits cannot read as drift.

    `ast.dump` includes docstrings because they are ordinary `Expr(Constant(str))` nodes. Left in,
    rewording a comment-shaped sentence would report the claim as moved when the behaviour did not
    change — and `STALE` has to mean something stronger than that to be worth reading.
    """
    body = list(getattr(node, "body", []))
    leads_with_docstring = (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )
    return ast.Module(body=body[1:] if leads_with_docstring else body, type_ignores=[])


def symbol_sha(source: str, symbol: str) -> str:
    """A fingerprint of what the symbol *does*, not of how it is laid out.

    `ast.dump` omits line numbers unless asked for them, so whitespace and wrapping are already
    invisible — a `ruff format` pass cannot mark a corpus stale. Renaming a local does change it,
    which is correct: that is a behaviour-adjacent edit worth re-reading the claim for.
    """
    node = resolve_symbol(source, symbol)
    digest = hashlib.sha256(ast.dump(_without_docstring(node)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def check_anchor(source: str, symbol: str, anchor: str) -> None:
    """The anchor must appear exactly once **inside** the symbol.

    Scoped to the symbol rather than the file on purpose. Measured over `src/`: `return None`
    occurs 191 times across 77 files and `return []` 59 times across 31 — file-uniqueness would
    reject every natural anchor and force unreadable ones.
    """
    node = resolve_symbol(source, symbol)
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", None) or len(source.splitlines())
    body = "\n".join(source.splitlines()[start:end])
    count = body.count(anchor)
    if count == 0:
        raise CorpusError(
            f"{symbol!r}: anchor {anchor!r} does not occur inside it. Either the code moved, or "
            "the mutant names a symbol it is not in"
        )
    if count > 1:
        raise CorpusError(
            f"{symbol!r}: anchor {anchor!r} occurs {count} times inside it — "
            "the runner could not say which line it changed. Make it unique"
        )


def drift_of(mutant: Mutant, root: Path) -> str:
    """Whether the code this mutant's claim rests on still looks the way it did.

    A vanished file or symbol is `STALE`, never an error: the code a claim rested on being gone is
    the most valuable thing the corpus can tell you, and raising here would turn it into a crash in
    the middle of a nightly run.
    """
    if mutant.symbol_sha is None:
        return UNHASHED
    try:
        source = (root / mutant.file).read_text(encoding="utf-8")
        return OK if symbol_sha(source, mutant.symbol) == mutant.symbol_sha else STALE
    except (OSError, CorpusError):
        return STALE


# --- maintenance: refresh and retire ----------------------------------------------------------


def _rewrite(path: Path, data: dict[str, Any]) -> None:
    """Write the corpus back in its canonical shape.

    `json.load` preserves key order, so re-dumping a canonical file changes only the value that was
    edited — the diff is one line, which is the whole point of keeping `symbol_sha` in the
    committed file. A tool that reformatted on every refresh would make each future diff
    unreviewable and the pin worthless as a record.

    A write failure surfaces as `CorpusError` like every other fault here. Letting a bare `OSError`
    escape would force every caller to know this module touches the filesystem, which is the seam
    leaking through the interface.
    """
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        raise CorpusError(f"{path.name}: cannot write — {exc}") from exc


def _find_mutant(data: dict[str, Any], feature: str, derived_id: str) -> dict[str, Any]:
    for campaign in data.get("campaigns", []):
        for mutant in campaign.get("mutants", []):
            if f"{feature} {campaign.get('requirement')} {mutant.get('id')}" == derived_id:
                return mutant
    raise CorpusError(f"no mutant with id {derived_id!r} in this corpus")


def refresh(path: Path, derived_id: str, root: Path) -> str:
    """Re-pin one mutant's `symbol_sha` after its claim has been re-verified.

    **One mutant at a time, and never automatic.** A bulk refresh is how drift detection gets
    defeated in a single command: every `STALE` disappears and nobody re-read a claim. The one-line
    diff this leaves in the corpus file is the review.

    Refuses when the symbol cannot be resolved. Pinning a hash for code that is gone would launder
    real drift into a green corpus, which is worse than the `STALE` it replaces.
    """
    load_corpus(path)  # refuse to maintain a corpus that could not be loaded
    data = _read(path)
    feature = feature_of(path)
    mutant = _find_mutant(data, feature, derived_id)

    source_path = root / mutant["file"]
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusError(f"{derived_id}: cannot read {mutant['file']} — {exc}") from exc

    sha = symbol_sha(source, mutant["symbol"])  # raises if the symbol is gone — deliberately
    mutant["symbol_sha"] = sha
    _rewrite(path, data)
    return sha


def retire(path: Path, requirement: str, *, reason: str, date: str) -> None:
    """Mark a campaign retired because its requirement was descoped.

    Marks, never deletes. The mutants stay exactly where they are: deleting them would destroy the
    only record that the requirement was ever measured, and a corpus that forgets is worth less
    than one that carries a tombstone.
    """
    load_corpus(path)  # refuse to maintain a corpus that could not be loaded
    data = _read(path)
    for campaign in data.get("campaigns", []):
        if campaign.get("requirement") == requirement:
            campaign["retired"] = {"reason": reason, "date": date}
            _rewrite(path, data)
            return
    raise CorpusError(f"no campaign for requirement {requirement!r} in {path.name}")


def main(argv: list[str] | None = None) -> int:
    """Maintenance only. This CLI never runs a mutant and never refreshes more than one.

    The absence of a bulk flag is the design: `--refresh-all` would clear every `STALE` in the
    corpus in one keystroke, with nobody having re-read a single claim, and drift detection would
    quietly become decoration.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True, help="path to a <FEATURE-ID>_mutants.json")
    ap.add_argument("--root", default=".", help="repo root the mutants' file paths resolve against")
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--refresh", metavar="DERIVED_ID", help="re-pin ONE mutant's symbol_sha")
    action.add_argument("--retire", metavar="REQUIREMENT", help="mark one campaign retired")
    ap.add_argument("--reason", help="why it was retired (required with --retire)")
    ap.add_argument("--date", default="", help="ISO date for the retirement record")
    args = ap.parse_args(argv)

    if args.retire and not args.reason:
        ap.error(
            "--retire needs --reason: a tombstone with no reason is a deletion with extra steps"
        )

    try:
        if args.refresh:
            sha = refresh(Path(args.corpus), args.refresh, Path(args.root))
            print(f"{args.refresh}: {sha}")
        else:
            retire(Path(args.corpus), args.retire, reason=args.reason, date=args.date)
            print(f"{args.retire}: retired — {args.reason}")
    except CorpusError as exc:
        print(f"could not do that: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
