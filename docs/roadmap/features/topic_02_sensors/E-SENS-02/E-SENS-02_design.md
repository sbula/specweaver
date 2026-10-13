# E-SENS-02 — Agentic Research Tools

**Status**: 🔧 Built, waiting for sign-off. · **Phase**: 3 (Feature 3.10)

| | |
|---|---|
| Touches | `sandbox/web/` · `core/config/llm_settings.py` (`[search]`) · `infrastructure/llm/resolve.py`, `router.py` · `core/flow/handlers/review.py` · `sandbox/dispatcher.py`, `registry.py` |
| Plan | [as built, 2026-03](E-SENS-02_implementation_plan.md); its web part is replaced by this page |

## What it does

A model that reviews or writes code can look things up itself. It gets six tools through one
provider-agnostic call (`generate_with_tools`): the four file tools of `E-SENS-01` and two web tools.

- `web_search` asks **Tavily** `[agreed 2026-10-13]`. One search costs one credit; the free plan
  has 1,000 a month.
- `read_url` reads a public page as text. It refuses every address that is not on the public
  internet `[agreed 2026-10-13]`.

The review steps (`review_spec`, `review_code`) and the code generation step get the web tools only
when the machine `settings.toml` names a search key:

```toml
[search]
api_key_env = "TAVILY_API_KEY"   # the variable in keys.env, never the key
```

The key lives in `~/.specweaver/keys.env` with the other keys. It is masked in everything sent to a
model, as every key in that file is (`E-INTL-01`).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Search | `web_search` | SHALL send the query to Tavily with the key in the `Authorization` header only, ask for 1 to 20 results, and return `{title, snippet, url}` for each | a model finds pages without the key in a URL, a log or its own context |
| FR-2 | Read a page | `read_url` | SHALL return the page as text, at most `max_chars` characters, read at most 2 MB, and follow at most 5 redirects | a model reads documentation; a huge page or a redirect loop cannot hang the run |
| FR-3 | Public addresses only | `read_url` | SHALL read only `http` and `https`, and refuse a host that resolves to any loopback, private, link-local, reserved or multicast address — checked again at every redirect | a model cannot reach the machine, the local network or a cloud metadata service |
| FR-4 | Key from the settings | Resolver | SHALL take the key from `keys.env` through the variable `[search] api_key_env` names, and refuse before any model call when `keys.env` does not set it | one place for keys; a broken search setting stops the command at once, naming its line |
| FR-5 | Web tools when set | Review and generation steps | SHALL offer the two web tools when a search key is set, and only then | no key, no web tools; an old `SEARCH_API_KEY` variable switches nothing on |

## Accepted risk

`read_url` checks the address, then httpx resolves the name again to connect. A name that changes
its answer in between (DNS rebinding) can pass the check. Connecting to the checked address would
close this, but breaks TLS name checks; not worth it for a read-only tool.

## Live demo

`tests/e2e/capabilities/sandbox/test_web_search_live_e2e.py`, nightly through `scripts/live.py`: the
settings files give the reviewer `web_search`; real Tavily returns public `https` results; real
`https://example.com/` reads; `169.254.169.254` is refused. It needs `TAVILY_API_KEY` in
`~/.specweaver/keys.env` and fails without it.
