# Who maintains the model price table? Nobody. — 2026-08-16

Measured while asking where the dollar figure in `sw usage` comes from, at `INT-US-16` CB-2. Kept
here rather than in a design document because it is a **measurement**, and the capabilities it
argues for (`C-FLOW-13` Model Catalogue, `D-FLOW-05` Model Catalogue Adoption) are minted as topic
entries and not yet designed — `docs/analysis/` is where the layer map puts what outlives a ticket.

**Re-take the census before designing against it.** A table whose defect is silent staleness should
not be designed against a stale measurement of itself.

## Where the dollar figure comes from

Per **model**, per **1,000 tokens**, input and output priced separately:
`(prompt/1000) × in_rate + (completion/1000) × out_rate`, rounded to 8dp (`telemetry.py:61-90`).

Two sources, in order: the user's own overrides (`llm_cost_overrides`, written by
`sw costs set <model> <in> <out>`), then a built-in table merged from each adapter class's
`default_costs` attribute (`adapters/registry.py:77-89`).

## `E-FLOW-03` registered PROVIDERS. Nothing registers MODELS.

Its topic entry states the design it achieved: *"each adapter is self-describing (`provider_name`,
`api_key_env_var`, `default_costs`). Adding a new provider = one file, zero other changes."* That
holds — for providers. Everything known about an individual **model** is a dict inside one of five
adapter classes, and nothing else about a model is recorded anywhere.

So when Google ships a new Gemini, no new adapter is needed and yet the only way to teach
SpecWeaver about it is a source change in `adapters/gemini.py`, a release, and a user upgrade.

## The census

19 models across five adapter files. `qwen.py` last touched **2026-05-04**; the other four in a
single commit on 2026-08-13.

- Three entries are dated preview builds — `gemini-2.5-pro-preview-03-25`,
  `gemini-2.5-flash-preview-04-17`, `gemini-3-flash-preview` — exactly the names providers retire.
- `claude-3-7-sonnet-20250219` is pinned to a 2025 snapshot.
- `mistral-large-latest` and `qwen-max-latest` price a **moving target with a fixed number**: the
  model behind the alias changes underneath a rate that does not.

**All three decay modes are silent:**

| | What happens | What the user sees |
|---|---|---|
| a price drops | spend is over-reported | nothing |
| a new model appears | absent from the table → **`$0.00`** | a `logger.warning` nobody reads |
| a model is retired | the stale row lives forever | nothing |

`estimate_cost` returns `0.0` for an unknown model (`telemetry.py:84-86`), so the newest and most
expensive model reports as free. The failure mode is a plausible number rather than an error, which
is what makes this a capability rather than a periodic chore.

## The user-side escape hatch is thin

`sw costs` has three verbs: view, `set` one model, `reset` one model. No import, no export, no bulk,
no "which models did I pay for that have no rate". It lists **only what you have overridden**, so a
user cannot see the 19 built-in rates their runs are actually priced with — the command that exists
to answer *"what am I paying"* cannot show the default answer.

The schema does carry `updated_at` (`store.py:66`), so staleness is already *recordable*. Nothing
reads it.

## Why a catalogue rather than a bigger dict

*"What does this cost"* is one of several questions a caller needs to ask about a model, and today
only that one has an answer, in the wrong place. Routing wants to know which models can be
substituted; prompt assembly wants the context window; tool use wants to know whether the model
supports tools; the factory wants to know which adapter serves it. Each is currently absent,
hardcoded at the call site, or inferred from the model-name string.

## Options, in rough order of cost

1. **Report the gap instead of hiding it.** Flag `$0.00` rows from unknown models and show how old
   each override is. Cheap, and it converts silent decay into something visible. Worth doing first
   regardless of the rest.
2. **Move the table out of source into data** — a versioned file with a `verified_on` date per
   entry, shipped and user-overridable. Editing prices stops being a code release; one place
   instead of five, diffable and reviewable. Still manual.
3. **Fetch from the provider.** Only some publish machine-readable pricing, coverage is partial, and
   it puts a network dependency inside a cost report. An addition to 2, never a replacement.

The open decision is not only which of these, but **what a missing entry should do**: today it
silently prices at zero, and the honest alternatives are to refuse, to warn loudly in the report, or
to record the usage with the cost marked unknown rather than `0.00`.

## What must move when a catalogue exists (`D-FLOW-05`)

| Consumer | Reads today | Where |
|---|---|---|
| cost estimation | `get_merged_default_costs()` → adapter class attributes | `telemetry.py:32-37, 61-90` |
| `sw usage` | whatever `estimate_cost` produced, per row | `llm/interfaces/cli.py:127` |
| `sw costs` | the override table only | `llm/interfaces/cli.py:29-71` |
| adapter construction | `_get_adapter_class(settings.llm.provider)` — provider, never model | `factory.py:27-66` |
| `sw implement` / `sw review` | `build_adapter_for_project`, merging overrides at call time | `factory.py` (`INT-US-16` CB-2) |
