# E-INTL-01 — LLM Adapter

**Status**: Built; `🔧` until the user signs off. · **Phase**: 1 · **Feature ID**: E-INTL-01

## What it does

The `LLMAdapter` base every provider implements, the first provider (`GeminiAdapter`), and the
masking of known secrets before anything is sent. The other providers are `E-FLOW-03`; which
server a role uses is `C-FLOW-13`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | LLM Provider Interface | Engine | Request completion | One call, `generate(messages, config)`, for every provider: a command reaches a provider the settings name, without naming it. |
| FR-2 | Gemini Integration | Engine | Request completion | The Gemini adapter sends the messages and the system prompt, and returns the answer. |
| FR-3 | Security Redaction | Engine | Send prompt | Credential and secret redaction applied before transmission: every known secret — the API keys in `~/.specweaver/keys.env` and the values in `.specweaver/vault.env` — is masked in messages and tool results `[agreed 2026-10-08]`. |

## Live demo

`sw review` of a spec holding a value from `.specweaver/vault.env`, against real Gemini: the review
comes back, and every request the SDK sent holds `***RESTRICTED***`, never the value. The nightly
live run (`scripts/live.py`) checks exactly this.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | LLM Adapter & Rules | — | ✅ | ✅ | ✅ | ✅ | ✅ |
