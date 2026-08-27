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

import hashlib
import logging
from dataclasses import dataclass, fields, replace
from typing import Any

from specweaver.workspace.analyzers._scope import directory_of, levels_of, unit_of
from specweaver.workspace.analyzers._sizing import emit_split, weight

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
    #: Which view this chunk belongs to: `body` is the code, `skeleton` is the description and the
    #: signature with the body elided.
    #:
    #: They are separate because the questions are: *what does this offer* is asked before *how
    #: does it work*, and a consumer ranks one above the other. `FR-17` binds the **body** layer --
    #: both halves -- because a skeleton is a description and a signature CONCATENATED, so it is
    #: not a slice of the file and never could be.
    layer: str = "body"
    #: sha256 over the text **and every other label**, so a re-index can ask *did this change*
    #: rather than wiping the store and embedding everything again.
    #:
    #: Every label, because a chunk whose text is unchanged and whose `visibility` was corrected
    #: from `public` to `private` is a **different row** — a consumer filtering by visibility would
    #: otherwise keep serving the old answer while the row looked current.
    content_hash: str = ""


def content_hash(chunk: Chunk) -> str:
    """A chunk's identity: sha256 over its text and every label except this one.

    **Excluding itself is what makes it recomputable.** A hash that fed on its own field would
    depend on whatever the field happened to hold, so checking a stored chunk for freshness would
    give a different answer than computing it fresh — and every row would read as stale.

    The fields are taken in declaration order and separated by a byte that cannot appear in a
    field's own rendering, so `("a", "bc")` and `("ab", "c")` cannot collide.
    """
    parts = [
        repr(getattr(chunk, field.name)) for field in fields(chunk) if field.name != "content_hash"
    ]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


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
    layer: str = "body",
) -> list[Chunk]:
    if not text.strip():
        return []
    inside = symbols if symbols is not None else ((symbol,) if symbol else ())
    pieces = emit_split(text, max_chars)
    # More than one piece means this text was cut by lines: `_split` knows no other boundary. So
    # the flag is set either because the caller already knows the file is unreadable, or because
    # the cut happened here.
    windowed = line_window or len(pieces) > 1
    return [
        _sealed(
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
            layer=layer,
        )
        for index, piece in enumerate(pieces, start=1)
    ]


def _sealed(**labels: Any) -> Chunk:
    """A chunk with its identity stamped on, which is the only way one is ever built here."""
    chunk = Chunk(**labels)
    return replace(chunk, content_hash=content_hash(chunk))


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
        if weight(body) <= cut.max_chars:
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
        return weight(self._text + text) <= self._cut.max_chars

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
    if weight(text) <= cut.max_chars:
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


def _skeletons(code: str, parser: Any, cut: _Cut, preamble: str) -> list[Chunk]:
    """One chunk per reported symbol: its description and its signature, with the body gone.

    **Per symbol, not per body chunk.** A class that fits is one body chunk and its methods are
    none, but the skeleton layer still holds every method — that independence is what having two
    layers is for, and `FR-12` says the two split and merge separately.

    **Never merged.** Measured across 921 symbols: 99 non-whitespace characters at the median, so a
    4,000 budget would hold about forty. Forty signatures in one chunk matches everything, which is
    the low-discrimination problem that made `FR-6` per-symbol rather than per-file.

    **Never split in practice** — the largest measured is 1,563 — but `_emit` still does the
    cutting, so a pathological one loses nothing.

    The preamble is here too `[agreed 2026-08-26]`: it has no body to elide, so its skeleton is the
    same text. Duplicated deliberately, because skeletons are ranked first and *what is this file
    for* would otherwise live only in the layer read second.
    """
    chunks: list[Chunk] = []
    if preamble.strip():
        chunks += _emit(
            preamble,
            cut.path,
            _MODULE_CHUNK,
            cut.language,
            cut.max_chars,
            (),
            package=cut.package,
            unit=cut.unit,
            layer="skeleton",
        )
    for name in cut.order:
        try:
            signature = parser.extract_symbol_signature(code, name)
        except Exception:
            logger.debug("Chunking %s: no signature for %r, skipping", cut.path, name)
            continue
        chunks += _emit(
            signature,
            cut.path,
            name,
            cut.language,
            cut.max_chars,
            (name,),
            visibility=_level_of(cut, name),
            package=cut.package,
            unit=cut.unit,
            layer="skeleton",
        )
    return chunks


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
        directory_of(path),
        unit_of(path, markers),
        unreadable,
        texts,
        order,
        parents,
        levels_of(code, parser, order),
    )
    tops = [n for n in order if parents[n] is None]

    first = next((texts[n] for n in tops if texts.get(n, "").strip() and texts[n] in code), None)
    if first is None:
        # Nothing parsed: there is no "before the first symbol", and no symbol to skeletonise.
        return _walk(code, tops, cut)

    head, _, rest = code.partition(first)
    preamble = head if head.strip() else ""
    body = (
        _emit(
            head, path, _MODULE_CHUNK, language, max_chars, (), package=cut.package, unit=cut.unit
        )
        + _walk(first + rest, tops, cut)
        if preamble
        else _walk(code, tops, cut)
    )
    return body + _skeletons(code, parser, cut, preamble)
