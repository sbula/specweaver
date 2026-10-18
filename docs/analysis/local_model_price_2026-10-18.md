# The indirect price of a local model (2026-10-18)

Agreed with the user 2026-10-18, while planning `TECH-074` SF-02.

A model on a local server costs no money, but it takes a share of the machine while it runs. The GB10
fits about three small models at once, or two medium ones, so a medium model costs about one and a
half small ones per unit of time. That share × time is the local model's **indirect price**.

It is not money and never enters the cost ledger, whose figures are dollars.

Where it is meant to be used:

- **Choosing a model (`A-FLOW-01`)**: rank local models by it, so the smallest model that does the
  job leaves room for parallel work.
- **The local brake** (open): a run on a private server counts plain tokens today; it could count
  tokens weighted by the model's share.

Open: how a model's share is measured (its memory at load, or its size on disk) and where it is kept.
