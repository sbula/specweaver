# Working in this repo — the traps that cost real time

Read this before your first change. Everything here is an incident, not advice: each item names what
went wrong, what it cost, and the one line that prevents it. Nothing generic — if it did not actually
burn a session, it is not in this file.

`.agents/AGENTS.md` holds the **design** standards (DDD, hexagonal, KISS). This holds the
**operational** ones. They do not overlap.

---

## 1. Your shell is lying to you about success

**`$?` after a pipe is the last command's status, not the one you care about.**

```bash
python scripts/quality.py cb | tail -3    # $? is tail's. tail always succeeds.
```

Two commits landed on a **red gate** this way, because the gate's output was piped for readability and
the exit code checked afterwards belonged to `tail`.

```bash
python scripts/quality.py cb 2>&1 | tail -3; s=${PIPESTATUS[0]}   # the gate's own status
[ "$s" = "0" ] || echo "NOT GREEN"
```

The same trap applies to `&&`/`;` chains where a later command masks an earlier failure. If a command
decides whether you commit, capture its status explicitly.

## 2. Put an **absolute** `.venv/bin` on PATH

`export PATH=".venv/bin:$PATH"` looks right and breaks the moment anything `chdir`s. Several tests
create temp worktrees and run subprocesses inside them; a relative entry then resolves against the
wrong directory.

Cost: **45 phantom test failures** chased as real ones.

```bash
export PATH="$PWD/.venv/bin:$PATH"
```

`tests/unit/test_architecture.py` shells out to a bare `tach`, which `.venv/bin/python -m pytest`
cannot see on its own — that is the specific test that fails first when you get this wrong.

## 3. When a number surprises you, verify the instrument before believing it

A survey script reported that one story held **28 delivered capabilities**. It held 2. The section
splitter had no boundary for the next heading, so it ran past the story and swallowed a table listing
every capability in the project.

The report was one command away from being handed over as a finding. **A surprising measurement is
first evidence that the measurement is wrong.** Print the input size, the section length, the row
count — something that would look absurd if the parse were broken.

## 4. A surviving mutant is not automatically a gap

Mutation is the standard here: a citation counts when removing the behaviour makes a test fail. But
some mutants change nothing observable, and reporting those as missing coverage is a false finding.

Two real examples:

- Removing `await session.flush()` from an upsert — the session commits anyway. **Equivalent mutant.**
  The one that landed stored `json.dumps({})` instead: the row still writes, still counts, and holds
  nothing.
- Disabling a `del doc["modules"]` before a rebuild — the following assignment replaces the key
  regardless. It only matters when there is nothing to assign.

Before filing "no test covers X", ask whether the mutant actually changed behaviour.

## 5. Bulk edits destroy things you never read

A helper that rewrote module docstrings across many test files silently dropped an `NFR` citation that
lived in the docstring it replaced — caught only because the NFR sweep regressed by exactly one. The
same helper, in an earlier form, pushed `from __future__` off the first line (SyntaxError in two
files) and dropped `# mypy: ignore-errors` and licence headers from five more.

If you are editing many files at once:

- **Read what you are about to replace**, not just what you are inserting.
- Assert the diff's shape afterwards — "comments and docstrings only", "no line removed above the
  licence header".
- Run the gate that would notice. `check_fr_sweep` / `check_nfr_sweep` catch lost citations; nothing
  else will.

## 6. A guard that cannot fail is not a guard

This is the single most common defect in this codebase, and you will write one yourself if you are not
deliberate. Real examples found and fixed:

| Guard | Why it never fired |
|---|---|
| `assert fail_count <= 95` on architecture violations | The debt was cleared months earlier; the slack absorbed any new violation |
| A soft-deprecation check looping over `interfaces` blocks | It matched `src.specweaver.…`; the config spells it `specweaver.…`, so the loop body never ran |
| `assert res.status == "success"` on a tool call | The intent could be swapped for a cheaper one and still succeed |
| A page-renders assertion | Passed against a page with no data behind it |

**Write the test, then break the thing it guards and watch it fail.** If it does not, the test is
decoration. For a test that must fail until something ships, use `xfail(strict=True)` and name the
blocker — a non-strict xfail hides the day it starts passing, and `check_xfail_blockers.py` will
refuse a reason with no blocker in it.

## 7. Check the thing exists before you test it

A journey test was written for a chain whose middle step does not exist. Worse, it was **circular**: it
planted a violating import, then ran the analysis that derives the rules *from the source including
that import*. A dependency cannot violate a description derived from that same dependency.

Before writing a cross-feature test, walk the chain in a scratch directory by hand and confirm each
link does what you think. Ten minutes of `sw` in a temp dir would have saved that test entirely.

## 8. Registry IDs: prove free with **both** commands, and distrust your own pattern

```bash
ls docs/roadmap/features/topic_07_technical_debt/          # authoritative for TECH
grep -rhoE "TECH-[0-9]{3}" --include=*.md --include=*.py . | sort -u | tail -5
```

A survey of capability IDs missed two taken numbers because they carried a `🔮` status marker the
regex did not include. The collision check caught it; the survey would not have. Full procedure and
the failures behind it: the `specweaver-ticket` skill.

Note that repo-wide greps surface fixture IDs (`TECH-901`, `TECH-999`) that are not real tickets. The
directory listing is authoritative for TECH; the matrix and topic docs for capabilities.

## 9. Know which documents are records and which are live

Getting this backwards either falsifies history or leaves instructions wrong.

| Live — keep current | Record — do not rewrite |
|---|---|
| `CLAUDE.md`, `tests/CLAUDE.md` | implementation plans |
| the roadmap, capability matrix, topic docs | `docs/analysis/*` |
| integration contracts and their path inventories | walkthroughs, handovers |
| skills | delivered designs, except to correct a statement that has become **false** |

A design that describes a mechanism the code no longer has is the exception: correct it and say why,
because a delivered design asserting something untrue is the defect class most of this repo's audits
keep finding.

## 10. Integration stories have a rule that is easy to get backwards

An `INT-US` entry belongs to a (sub)story **that already holds a finished feature**, and nowhere else.

- **Never mint or reference one for unbuilt work.** An unbuilt capability owns its own integration and
  e2e proof, as its own FRs, written red before the code.
- **Never delete an open one.** It is the record that a shipped feature was never integration-tested.
  Removing it hides the debt rather than retiring it.

Getting this wrong is how the session that produced this file started. Full rules: `ADR-004`, and the
`specweaver-design` skill's opening caution.

---

## The shortest version

Measure, do not infer. Break your own guard and watch it fail. Read what you are about to overwrite.
And when a result looks surprising, suspect your instrument before you suspect the codebase.
