# Design: Nothing Bounds a Document's Size

- **Feature ID**: TECH-045
- **Epic**: Topic 07 (Technical Debt)
- **Status**: 🟢 **CLOSED 2026-08-13 — approach 4, decided against.** A close, not a deferral: the
  question was asked, measured and answered no.
- **Origin**: 2026-08-13, raised by the user while reviewing `TECH-044`'s first redistribution:
  *"what prevents it to grow indefinitely?"* Recorded there as a known gap and split out here so it
  is scheduled rather than remembered.

## Problem Statement

`R-DEPTH` caps a markdown **line** at 200 characters. `R-ENTRY` caps a topic **entry** at four
lines. Nothing caps a **file**.

`check_file_sizes.py` runs on `src tests scripts` with a 450-line YELLOW and 600-line RED
threshold — and `docs/` is not in its scope. So a design document, an implementation plan or a
delivery record can grow without limit, and two of them already exceed 45 KB.

Measured 2026-08-13:

| Kind | n | median | p90 | max |
|---|---|---|---|---|
| implementation plan | 168 | 5.9 KB | 24.0 | **50.5** |
| design | 104 | 7.1 KB | 23.9 | **45.2** |
| dev guide | 23 | 5.1 KB | 14.7 | 45.8 |
| analysis | 14 | 10.8 KB | 21.6 | 38.5 |
| topic doc | 35 | 0.3 KB | 9.8 | 22.6 |
| delivery record | 33 | 5.6 KB | 9.9 | 20.9 |

The distributions are the interesting part: every kind has a median under 11 KB and a p90 under
24 KB, with a long thin tail. This is not a systemic problem — it is a handful of documents, which
is what makes it tractable.

## Why this is not simply "apply the 600-line rule to docs/"

**A single number will not fit, and this ticket must not repeat the mistake that killed the
entry-size cap.** During `TECH-044` an entry-size budget was proposed at 1500 characters and
rejected on measurement: within `master_story_roadmap.md` alone a `US-N` block runs 18 lines while
capability, sub-story and `TECH` lines are one line each, so no single number could fit four kinds
in one file.

The same trap is here in a different shape. A design document and a one-paragraph stub are both
`*_design.md`; an implementation plan that covers eight commit boundaries is legitimately longer
than one covering two. Any threshold has to survive that, or it will be argued with and then
suppressed.

**`R-DEPTH` works because it is kind-agnostic** — a line is a line whatever the document. A file
size is not.

## Candidate Approaches (not yet designed)

1. **Per-kind thresholds from each kind's own distribution**, as `R-LENGTH` originally derived 200
   from the roadmap's own p90. The table above is the input. More faithful; more numbers to defend.
2. **One generous threshold** — say 40 KB — that only catches the tail. Cheap and hard to argue
   with; would flag roughly five documents today. Ratifies nothing about the middle of the range.
3. **Structural rather than numeric**, the shape `TECH-044` settled on for entries: flag a document
   whose *sections* indicate mixed layers — a design carrying dated delivery narrative, for example,
   which is what made `TECH-035_design.md` 28.6 KB before its build record was split out. Targets
   the cause rather than the symptom, and needs no number.
4. **Nothing.** State that document size is unbounded by design and delete the gap from the
   backlog. Defensible: prose is not code, and the redistribution work already removed the worst
   cases without a size rule existing.

Approach 3 is the most promising and the least obvious, because it is the one that generalises the
lesson `TECH-044` actually learned: **length is a symptom, misplaced content is the defect.**

## Non-Goals (proposed, pending design)

- Changing `R-DEPTH` or `R-ENTRY`. Both are at zero and zero-tolerance.
- Splitting documents merely to satisfy a number. `TECH-035`'s split was justified by the content
  being at the wrong layer, not by its byte count.
- `check_file_sizes.py`'s existing `src tests scripts` thresholds.

## Decision, 2026-08-13 — approach 4: no size rule

**Decided against, by the user, on the measurement.** Every kind has a median under 11 KB and a
p90 under 24 KB with a long thin tail — four documents over 45 KB. A thin tail is not a systemic
problem, and each candidate rule costs more than it buys:

- **per-kind thresholds** — a design stub and an eight-boundary implementation plan are the same
  "kind", so the numbers would be arbitrary and argued with;
- **one generous threshold** — catches about five documents and ratifies nothing about the middle;
- **structural, flagging mixed layers** — the most interesting, and still another mechanical proxy
  for a judgement a reader makes better.

**The evidence for "no" is that the problem already went away without this rule.** `TECH-044`'s
redistribution removed the worst cases — `TECH-035_design.md` fell 28.6 KB → 8.4 KB — driven by
content being at the wrong *layer*, never by its byte count. `R-DEPTH` and `R-ENTRY` cover
readability and depth; a third numeric rule for prose would buy the appearance of rigour, which is
worse than none.

Recorded rather than deleted so the question is not re-opened as if it were new.
