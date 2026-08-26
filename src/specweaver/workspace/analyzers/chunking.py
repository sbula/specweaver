# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Splits source into units a developer would recognise, for retrieval over a large estate.

A fixed-size window cuts a function in half. Whichever half is retrieved is missing its signature
or its return, so the model reasons about a fragment that never existed as code. Splitting on AST
boundaries means every unit is a whole thing.

Each chunk carries where it came from, because a retrieved fragment that cannot name its file and
symbol cannot be cited, and an agent that cannot cite cannot be checked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: Big enough to hold most real symbols whole, small enough that a chunk stays a useful retrieval
#: unit. Symbols above it are split rather than truncated.
_DEFAULT_MAX_CHARS = 4000

#: What the head of a file is called: its docstring, its imports and its top-level constants.
#:
#: Angle brackets are not a legal identifier in any of the eight target languages, so no parser can
#: report a symbol by this name and the two can never be confused. It names the run **before the
#: first symbol** and nothing else -- text between two symbols is not the module's description.
_MODULE_CHUNK = "<module>"


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit, and enough provenance to cite it.

    `part`/`parts` are `1`/`1` for anything that fitted. They are not decoration: a reader given
    part 2 of 3 needs to know the unit continues, or they will read a mid-symbol fragment as the
    whole definition.
    """

    text: str
    path: str
    symbol: str
    language: str
    part: int = 1
    parts: int = 1
    #: Every symbol inside this chunk, in source order. One name for a chunk that holds one
    #: symbol, several for a merged chunk, none for a gap or a line window.
    #:
    #: A merged chunk cannot be named by `symbol` — it holds more than one — and a merged chunk
    #: with no names at all is an anonymous chunk, which is the defect this capability exists to
    #: remove. So `FR-9` could not be delivered without this field, and it is here rather than in
    #: SF-06 for that reason. The rest of `FR-13` — content hash, package, unit — is still SF-06's.
    symbols: tuple[str, ...] = ()
    #: True when this chunk was cut by lines rather than at a boundary the code has — because the
    #: parser could not read the file at all, or because a symbol had no nested symbols left and
    #: was still over budget.
    #:
    #: Without it a binary blob and a module preamble are the same thing: both carry no symbol, and
    #: a consumer cannot rank one below the other. A symbol sliced at line 400 is no more a whole
    #: unit than the blob is, which is why `FR-10`'s last resort sets it too.
    is_line_window: bool = False
    #: The access level of what this chunk holds: one of `VISIBILITY`. `unknown` for a gap, the
    #: preamble, a line window, and whenever the parser could not answer.
    visibility: str = "unknown"
    #: The narrow radius — the directory this file sits in. Java's package-private is literally
    #: this, and a helper shared inside one package is legitimately internal to it.
    package: str = ""
    #: The wide radius — the nearest ancestor the caller identified as a build unit: a crate, a
    #: service, a module. `""` means **not known**, never *the same as `package`*: a chunk claiming
    #: a boundary the caller never established would answer "is this outside my service?" from a
    #: guess.
    unit: str = ""


def _directory_of(path: str) -> str:
    """The directory part of a path, on either platform's separator.

    Not `pathlib`: it resolves against the platform running the scan, so a Windows path handed to a
    Linux worker would come back whole and the chunk would claim the entire path as its package.
    A scan reads paths as data, so they are split as data.
    """
    cut = max(path.rfind("/"), path.rfind("\\"))
    return path[:cut] if cut > 0 else ""


def _unit_of(path: str, markers: frozenset[str]) -> str:
    """The nearest ancestor directory the caller marked as a build unit, or `""`.

    **Nearest, not first.** A repository root and a nested package both hold a manifest, and the
    file belongs to the inner one — taking any match would put every file in the repo root.

    Matching is on a path **boundary**, so `src/apple` is not a unit of `src/app/mod`.
    """
    best = ""
    # `sorted`, not the set's own order. A frozenset iterates by hash, which is stable within one
    # process and not across runs -- so two candidates of equal length would tie differently on
    # different days, and `NFR-4` says the same input gives the same chunks. Added when two mutants
    # came back SILENT: an order-dependent implementation cannot be pinned by a deterministic test.
    #
    # Sorting is on the MARKER PATHS, so `src/app/build.gradle` precedes `src/app/mod/go.mod` while
    # `src/app/pyproject.toml` follows it. Length is what decides; the sort only makes which
    # candidate is seen first a fact rather than a coin toss.
    for marker in sorted(markers):
        directory = _directory_of(marker)
        if not directory:
            continue
        # On a path BOUNDARY: a bare prefix would make `src/app` a unit of `src/application`.
        if any(path.startswith(directory + sep) for sep in ("/", "\\")) and len(directory) > len(
            best
        ):
            best = directory
    return best


def _parent_of(name: str, texts: dict[str, str]) -> str | None:
    """The symbol this one is nested in, or None when it stands on its own.

    **Containment decides.** A symbol is nested when its text lies inside another symbol's, and the
    parent is the smallest such symbol — which is what "nested" means in a tree.

    A dot decides nothing, and cannot. `FR-7` made `public.orders` a top-level SQL object whose
    name contains one; the rule this replaces — *drop every name with a dot* — dropped every
    qualified table and function in an estate from the index. And scoped names go only one level
    deep: Python reports a nested class's method as `Inner.deep_0`, never
    `Outer.Inner.deep_0`, so at depth two the name has no prefix that is a symbol at all. The
    dotted prefix is kept only as a **fast path** for the common single-level case; containment is
    the rule behind it and answers both.
    """
    body = texts.get(name, "")
    if not body:
        return None

    prefix, dot, _ = name.rpartition(".")
    if dot and prefix in texts and body in texts[prefix]:
        return prefix

    smallest: str | None = None
    for other, other_body in texts.items():
        if other == name or len(other_body) <= len(body) or body not in other_body:
            continue
        if smallest is None or len(other_body) < len(texts[smallest]):
            smallest = other
    return smallest


def _children_of(parent: str, order: list[str], parents: dict[str, str | None]) -> list[str]:
    """The symbols nested directly in `parent`, in source order."""
    return [name for name in order if parents.get(name) == parent]


def _weight(text: str) -> int:
    """How much of `text` counts towards the budget: its non-whitespace characters.

    Counting every character let **indentation decide where code was cut**. Deeply nested Java and
    flat Python were judged by different standards for the same amount of code, and reformatting a
    file moved its chunk boundaries without a line of it changing — which, once anything is
    embedded, costs a re-index of the whole repository.

    cAST measures the same way, and for the same reason: consistency across coding styles and
    languages. The trade is that *raw* length is then unbounded; `NFR-3` states it rather than
    leaving it to be discovered.
    """
    return len("".join(text.split()))


def _slice_long_line(line: str, max_chars: int) -> list[str]:
    """A single line, cut only if it alone exceeds the budget.

    Cutting mid-line produces a fragment that is not lexically whole, which is what this module
    exists to avoid — so it is the last resort **after** the last resort, and the ordinary path
    returns the line untouched.

    It is needed because a line boundary is not guaranteed to exist. A minified bundle or a
    single-line JSON has none, and before this a 800,000-character file came back as **one** chunk
    against a budget of 4,000. Whatever embeds that either fails or silently truncates. Found by a
    retrospective red/blue on 2026-08-26.
    """
    if _weight(line) <= max_chars:
        return [line]
    return [line[at : at + max_chars] for at in range(0, len(line), max_chars)] or [line]


def _split(text: str, max_chars: int) -> list[str]:
    """Break oversized text on line boundaries, keeping every line.

    Splitting mid-line would produce a fragment that is not even lexically whole, which is the
    failure this module exists to avoid — just at a smaller scale.
    """
    parts: list[str] = []
    current = ""
    weight = 0
    for line in text.splitlines(keepends=True):
        for piece in _slice_long_line(line, max_chars):
            piece_weight = _weight(piece)
            if current and weight + piece_weight > max_chars:
                parts.append(current)
                current = ""
                weight = 0
            current += piece
            weight += piece_weight
    if current:
        parts.append(current)
    return parts or [text]


def _emit(
    text: str,
    path: str,
    symbol: str,
    language: str,
    max_chars: int,
    symbols: tuple[str, ...] | None = None,
    *,
    line_window: bool = False,
    visibility: str = "unknown",
    package: str = "",
    unit: str = "",
) -> list[Chunk]:
    if not text.strip():
        return []
    inside = symbols if symbols is not None else ((symbol,) if symbol else ())
    pieces = _split(text, max_chars)
    # More than one piece means this text was cut by lines: `_split` knows no other boundary. So
    # the flag is set either because the caller already knows the file is unreadable, or because
    # the cut happened here.
    windowed = line_window or len(pieces) > 1
    return [
        Chunk(
            text=piece,
            path=path,
            symbol=symbol,
            language=language,
            part=index,
            parts=len(pieces),
            symbols=inside,
            is_line_window=windowed,
            visibility=visibility,
            package=package,
            unit=unit,
        )
        for index, piece in enumerate(pieces, start=1)
    ]


@dataclass(frozen=True)
class _Cut:
    """Everything a cut needs to know about the file it is cutting.

    Bundled because `_walk` and `_emit_unit` are mutually recursive and would otherwise pass six
    arguments back and forth at every level, which is how the two loops came to be written out
    twice in the first place.
    """

    path: str
    language: str
    max_chars: int
    #: The two radii, resolved once from what the caller supplied. Every chunk of a file carries
    #: the same pair, because they are properties of the file rather than of the cut.
    package: str
    unit: str
    #: True when the parser could not read this file at all. Distinct from *a file with no
    #: symbols*, which is readable and simply declares nothing — a comment-only file is a whole
    #: unit, and a file no grammar handles is not.
    unreadable: bool
    texts: dict[str, str]
    order: list[str]
    parents: dict[str, str | None]
    #: Each symbol's access level, or **None when the parser could not answer**. Merging may not
    #: cross a level, so `None` disables merging entirely rather than treating every symbol as
    #: alike — not knowing is not the same as knowing they match.
    levels: dict[str, str] | None


def _level_of(cut: _Cut, name: str) -> str:
    """One symbol's level, or `unknown` when the parser could not answer for the file."""
    return "unknown" if cut.levels is None else cut.levels.get(name, "unknown")


def _walk(text: str, names: list[str], cut: _Cut) -> list[Chunk]:
    """Cut `text` at each of `names`, in source order, losing nothing between them.

    The file and a class are the same problem at two scales — a run of symbols with text around
    them — so this is written once and used by both.

    Two passes, in cAST's order: **split, then merge.** The first produces one piece per symbol
    plus whatever sits between them; the second combines the small ones. Reversing the two would
    not converge.
    """
    pieces: list[tuple[str, str, list[Chunk] | None]] = []
    remainder = text
    for name in names:
        body = cut.texts.get(name, "")
        if not body.strip() or body not in remainder:
            continue
        head, _, remainder = remainder.partition(body)
        if head:
            # Kept even when it is only whitespace. Before merging, blank runs between symbols
            # belonged to no chunk and nothing noticed. Now a merged chunk concatenates the pieces
            # it covers, so dropping the run between two methods produced `... + 1clas` -- text
            # that never existed in the file. `_emit` still discards a blank piece that ends up
            # standing alone.
            pieces.append((head, "", None))
        if _weight(body) <= cut.max_chars:
            pieces.append((body, name, None))
        else:
            # Already too big to merge with anything. It goes through `_emit_unit`, which splits
            # it on structure, and the finished chunks pass through the merge untouched.
            pieces.append((body, name, _emit_unit(body, name, cut)))
    if remainder.strip():
        pieces.append((remainder, "", None))
    return _merge(pieces, cut)


class _Run:
    """A run of neighbours being combined, and the rules for what may join it.

    A class rather than three locals threaded through a loop: `check_complexity` put `_merge` at 19
    against a ceiling of 15, and the branches it was counting were all *"may this piece join?"* —
    one question, asked of one piece of state.
    """

    def __init__(self, cut: _Cut) -> None:
        self._cut = cut
        self._text = ""
        self._inside: list[str] = []
        self._level: str | None = None

    def _fits(self, text: str) -> bool:
        return _weight(self._text + text) <= self._cut.max_chars

    def flush(self) -> list[Chunk]:
        """Emit whatever has accumulated, and start again."""
        chunks = _emit(
            self._text,
            self._cut.path,
            self._inside[0] if len(self._inside) == 1 else "",
            self._cut.language,
            self._cut.max_chars,
            tuple(self._inside),
            line_window=self._cut.unreadable,
            # The level its members SHARE. `absorb` never lets two levels into one run, so there
            # is exactly one -- but taking a member's level after the fact would be a different
            # claim, and `FR-9`'s guard test passes either way.
            visibility=self._level or "unknown",
            package=self._cut.package,
            unit=self._cut.unit,
        )
        self._text, self._inside, self._level = "", [], None
        return chunks

    def absorb_gap(self, text: str) -> list[Chunk]:
        """Text belonging to no symbol: it travels with the run, or stands alone.

        Carried **even when it is only whitespace**. Before merging, a blank run between two
        methods belonged to no chunk and nothing noticed; now a merged chunk concatenates what it
        covers, so dropping it produced `... + 1clas` — text that never existed in the file.
        """
        if self._inside and self._fits(text):
            self._text += text
            return []
        return self.flush() + _emit(
            text,
            self._cut.path,
            "",
            self._cut.language,
            self._cut.max_chars,
            (),
            line_window=self._cut.unreadable,
            package=self._cut.package,
            unit=self._cut.unit,
        )

    def absorb(self, name: str, text: str) -> list[Chunk]:
        """A symbol: it joins the run, or ends it and starts the next.

        **It may not join across a visibility level.** A public getter combined with a private
        helper puts the private one into every result that asks for the public interface —
        `FR-2`'s filter undone one layer up, where no filter can see it.
        """
        if self._cut.levels is None:
            # Visibility unavailable: nothing may join anything. Failing closed costs a few more
            # chunks; failing open puts a private symbol into a public one.
            return self.flush() + _emit(
                text,
                self._cut.path,
                name,
                self._cut.language,
                self._cut.max_chars,
                (name,),
                line_window=self._cut.unreadable,
                package=self._cut.package,
                unit=self._cut.unit,
            )

        level = _level_of(self._cut, name)
        flushed: list[Chunk] = []
        if self._inside and (level != self._level or not self._fits(text)):
            flushed = self.flush()
        self._text += text
        self._inside.append(name)
        self._level = level
        return flushed


def _merge(pieces: list[tuple[str, str, list[Chunk] | None]], cut: _Cut) -> list[Chunk]:
    """Greedily combine consecutive small pieces that share one visibility level.

    *Adjacent* means consecutive with nothing unmergeable between: two public methods on either
    side of a private one are not neighbours, and combining them would reorder the file.
    """
    out: list[Chunk] = []
    run = _Run(cut)
    for text, name, finished in pieces:
        if finished is not None:
            out.extend(run.flush())
            out.extend(finished)
        elif name:
            out.extend(run.absorb(name, text))
        else:
            out.extend(run.absorb_gap(text))
    out.extend(run.flush())
    return out


def _emit_unit(text: str, name: str, cut: _Cut) -> list[Chunk]:
    """One symbol, cut on structure while it can be and on lines only when it cannot.

    The recursion terminates by construction: each child's text is strictly shorter than its
    parent's, and a symbol with no children falls through to the line split.
    """
    if _weight(text) <= cut.max_chars:
        return _emit(
            text,
            cut.path,
            name,
            cut.language,
            cut.max_chars,
            visibility=_level_of(cut, name),
            package=cut.package,
            unit=cut.unit,
        )

    children = _children_of(name, cut.order, cut.parents)
    if not children:
        # FR-10: no nested symbols left, so lines are all that remain. `_emit` sets the flag
        # when it has to cut; passing it here covers the case where the whole symbol still fits
        # in one piece but was reached by giving up on structure.
        return _emit(
            text,
            cut.path,
            name,
            cut.language,
            cut.max_chars,
            line_window=cut.unreadable,
            visibility=_level_of(cut, name),
            package=cut.package,
            unit=cut.unit,
        )

    return _walk(text, children, cut)


def _levels(code: str, parser: Any, order: list[str]) -> dict[str, str] | None:
    """Each symbol's access level, or **None when the parser could not answer**.

    `extract_symbol_visibility` re-parses the file every time it is asked, so asking per symbol is
    one parse per symbol — a thousand of them for a thousand-symbol file. `list_symbols` answers a
    whole level at once, and `VISIBILITY` is closed, so the cost is a constant.

    A symbol whose language cannot say arrives in the `public` bucket and is recorded as public.
    That is `AD-5` — `unknown` counts as visible — applied to merging rather than restated.

    **`None` rather than a dict of `unknown`, and the difference is the whole point.** Every symbol
    reading `unknown` means every symbol matches every other, so a private one merges into a public
    chunk — `FR-2`'s filter undone one layer up, failing in the same direction the original defect
    failed. Not knowing is not the same as knowing they are alike. Found by a retrospective
    red/blue on 2026-08-26, on a path no mutant could reach because no line was written for it.
    """
    levels: dict[str, str] = {}
    for level in ("public", "protected", "internal", "private"):
        try:
            for name in parser.list_symbols(code, visibility=[level]):
                levels.setdefault(name, level)
        except Exception:
            logger.debug("Chunking: visibility unavailable at %r; merging disabled", level)
            return None
    return {name: levels.get(name, "unknown") for name in order}


def chunk_source(
    code: str,
    *,
    path: str,
    parser: Any,
    language: str,
    max_chars: int = _DEFAULT_MAX_CHARS,
    markers: frozenset[str] = frozenset(),
) -> list[Chunk]:
    """Split `code` into semantic chunks, falling back to line windows when it will not parse.

    A brownfield estate contains files no parser handles. Returning nothing for those would drop
    them from the index silently, which a reader cannot distinguish from *this code does not
    exist* — so unparseable content is still chunked, under an empty symbol name.

    Whatever belongs to no symbol — the module docstring, imports, top-level statements — is kept
    as a preamble chunk. It is usually the part that says what the file depends on.
    """
    unreadable = False
    try:
        order = parser.list_symbols(code)
    except Exception:
        logger.debug("Chunking %s: symbol listing failed, falling back to line windows", path)
        order, unreadable = [], True

    texts: dict[str, str] = {}
    for name in order:
        try:
            texts[name] = parser.extract_symbol(code, name)
        except Exception:
            logger.debug("Chunking %s: could not extract %r, skipping", path, name)

    parents = {name: _parent_of(name, texts) for name in order}
    cut = _Cut(
        path,
        language,
        max_chars,
        _directory_of(path),
        _unit_of(path, markers),
        unreadable,
        texts,
        order,
        parents,
        _levels(code, parser, order),
    )
    tops = [n for n in order if parents[n] is None]

    first = next((texts[n] for n in tops if texts.get(n, "").strip() and texts[n] in code), None)
    if first is None:
        return _walk(code, tops, cut)  # nothing parsed: there is no "before the first symbol"

    head, _, rest = code.partition(first)
    if not head.strip():
        return _walk(code, tops, cut)
    return _emit(
        head, path, _MODULE_CHUNK, language, max_chars, (), package=cut.package, unit=cut.unit
    ) + _walk(first + rest, tops, cut)
