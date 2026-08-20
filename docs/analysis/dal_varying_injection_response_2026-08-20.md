# What DAL-Varying Response Costs — E-VAL-03 Security Analysis

> **Outcome (2026-08-20):** the DAL-varying approach this document analyses was **rejected** by the
> user the same day — and the capability it belonged to was later ruled nonsense outright under the
> benefit test (`benefit_chain_analysis_2026-08-20.md` §8). Kept as the record of why, and for the
> `isolation.py` defence-in-depth finding in "Out of scope, but found on the way".

*2026-08-20. Written during the `/grill-me E-VAL-03` round-1 answers, where the user chose a
DAL-varying response and asked what it exposes. The choice is sound. The obvious implementation of
it is not, and three of the six findings below are ways an attacker turns the escalation off.*

## How DAL actually resolves

Measured, not assumed:

| Fact | Where |
|---|---|
| DAL is read from `operational.dal_level` in a `context.yaml` | `core/config/dal_resolver.py:48-67` |
| Resolution walks **up** from the target, nearest declaration wins, halting at the project root | `core/config/_context_walk.py:44-60` |
| The root is the **project under analysis** — `context.project_path` | `core/flow/engine/isolation.py:166`, `core/flow/handlers/validation.py:32` |
| An unreadable or malformed `context.yaml` yields `None`, silently | `dal_resolver.py:53-55` — bare `except Exception: return None` |
| `None` is a normal outcome, not an error; callers pick their own default | `isolation.py:187` treats it as "no escalation" |

The one sentence that matters: **the DAL grading a file is declared inside the tree that file came
from.** For SpecWeaver's own repository that tree is the operator's. For the case this capability
exists to serve — `US-12` reverse-weaving an undocumented repository, `US-18` an external
proprietary system, `US-26` a fleet sweep — it is the third party's.

## Findings

### F1 · HIGH — the attacker grades their own payload

If the response tier is selected by the DAL resolved from the analysed tree, then whoever writes the
payload also writes the file that decides how gently it is treated. Nearest-declaration-wins makes
it precise rather than approximate: drop a `context.yaml` carrying `dal_level: DAL_E` in the same
directory as the payload and it outranks anything the repository root declares.

This is the circular-proof failure from `working_in_this_repo.md` §7 in a new place — the input being
judged supplies the criterion it is judged against. A control whose strength is chosen by the
attacker is not a control at every level except its weakest.

**Fix.** The tier's floor is operator-owned configuration. DAL read from the analysed tree may
**raise** the response and may never lower it: `tier = max(operator_floor, tree_tier)`. Escalating on
adversary-controlled data is safe because the adversary can only make it stricter; de-escalating on
it is the whole vulnerability.

### F2 · HIGH — the surfaces the trust model was widened for have no DAL at all

`Q1 = (c)` puts every non-template, non-user block in scope. `DALResolver.resolve()` takes a
**path**. The blocks that motivated (c) are strings:

| Block | Origin | Has a path? |
|---|---|---|
| `add_context(filtered_trace, "Failures")` — `arbiter.py:227` | LLM-authored | no |
| `add_context(json.dumps(findings), "reviewer_findings")` — `draft.py:166,357` | LLM-authored | no |
| `add_context(validation_findings, "validation_errors")` — `generator.py:110,169` | tool output | no |

Every one resolves to `None` and lands on whatever the default is. If the default is the weakest
tier, the LLM→LLM feedback loop — the most dangerous surface, and the reason the roadmap raised this
capability's urgency — receives the weakest response in the system. The escalation is not merely
absent there; it is inverted.

**Fix.** A block with no path inherits the **run's** DAL, not a default. `seed_dal_level()`
(`isolation.py:154`) already resolves and caches exactly that on `RunContext`.

### F3 · MEDIUM-HIGH — one prompt is one trust domain, so the weakest block sets the strength

A prompt is a single context window. The model does not partition its attention by the DAL of the
directory each block came from. Select the response per block and a prompt can hold an annotated
payload (text retained) beside redacted high-DAL work — and the retained payload's instructions
apply to the whole window, including the part that was protected.

Per-block escalation therefore does not produce per-block protection. It produces one prompt
protected at the level of its weakest member.

**Fix.** The tier is a property of the **run**, resolved once, applied to every block in the prompt.
Where several DALs are in play, the strictest wins.

### F4 · MEDIUM — "annotate" defends against injection using the channel under attack

Annotation leaves the payload in the prompt and wraps it in a note saying the content is untrusted
and must not be obeyed. That note is itself prompt text, asking the model to resist instructions —
a mitigation whose only enforcement point is the component being attacked. It fails exactly when it
matters, and it fails silently.

Redaction is mechanical: text that is not in the window cannot be obeyed, whatever the model decides.

So an `annotate → redact → block` ladder puts the only mechanically sound option in the *middle* and
gives the bottom tier a defence that amounts to a hope.

**Fix.** Redaction is the **floor**, at every DAL. Annotate is not a tier — it is an operator-selected
diagnostic mode for inspecting what the detector does, chosen deliberately and never reached by
escalation.

### F5 · MEDIUM — block hands the attacker an availability switch

At the top tier, block aborts the run. Any third party who can write text into the analysed
repository can then halt every high-DAL run at will, without needing the injection to succeed —
detection alone is the weapon.

False positives fire it with no attacker at all. A security `README` documenting the phrase
*"Ignore all previous instructions"*, a test fixture, this very document — all are ordinary content
that a detector must flag.

Refusing to proceed on tainted input is defensible at DAL-A; it is fail-closed, and this repo's
precedent is that a ceiling fails closed (`B-FLOW-05`: `0` means refuse everything). But it is a
decision with a real cost, and the cost lands on availability.

**Fix.** Block routes to a human rather than aborting — `C-FLOW-05` interactive gates already exist —
so a mission-critical run stops *and can be released* by someone who looked. An unattended abort is
the same control with no operator in it.

### F6 · MEDIUM — an unreadable `context.yaml` fails open

`_parse_dal_from_context` catches **every** exception and returns `None`: unreadable file, bad YAML,
wrong types. `None` then means "nothing declared". An attacker does not need a valid low declaration —
corrupting the file produces the same downgrade, and nothing logs that a declaration was expected and
failed to parse.

Note the asymmetry already in the code: a *malformed* `dal_level` value raises `ValueError`
(`dal_resolver.py:66`), but a malformed *file* returns `None`. The stricter path is the narrower one.

**Fix.** Unknown DAL resolves to the operator floor, never below it — which F1's `max()` already
delivers. Separately, a `context.yaml` that exists and cannot be parsed should say so at warning
level rather than passing as "not declared".

## What makes the choice safe

Three corrections, and DAL-varying response survives all six findings:

1. **Run-scoped, not block-scoped.** One tier per prompt, strictest applicable, resolved once.
2. **Operator-owned floor.** `tier = max(operator_floor, tree_tier)` — adversary-controlled data may
   only escalate. This is the load-bearing one; without it F1 and F6 both stand.
3. **Redaction is the floor and detection is unconditional.** Every tier scans, every tier records the
   finding, every tier removes the payload. Only what happens *around* the redaction escalates:
   reporting at the low end, a human gate at the top.

Under those, the ladder is not `off → weak → strong`. It is `always redact → also report → also stop
and ask`, which is an escalation of **operator involvement**, not of protection.

## Proof obligations this creates

- A mutant that pins the tier to the weakest value must fail a test, or the escalation is decoration
  (`working_in_this_repo.md` §6).
- A mutant that replaces `max(operator_floor, tree_tier)` with `tree_tier` must fail a test — that is
  F1, stated as something a change can break.
- A path-less block must be proven to receive the run's tier, not the default.

## Out of scope, but found on the way

`_dal_requires_isolation` (`isolation.py:170-190`) reads its **threshold** from operator settings but
its **observed DAL** from the analysed tree, and returns `False` when the DAL is absent or below the
threshold. An analysed repository that declares `DAL_E`, or declares nothing, therefore suppresses
automatic worktree isolation — F1's shape, one capability over, on the auto path. The explicit
`enforce_session_isolation` route still fails closed, so this is a defence-in-depth gap rather than
an open door.

It belongs to `C-EXEC-06`/`C-EXEC-07`, not here, and it is a security threshold — the user's call
whether it becomes a ticket.
