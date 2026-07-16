# US-09 Integration - Integration Contracts

## Base Story Contract (`INT-US-09`)
* **Status:** ⬜ Pending
* **Integration Description:** The QA Runner (`US-3 Core`) must be forcefully injected into the Podman/Docker Integration (`D-EXEC-01`), with host filesystem mounts set strictly to read-only for source files, and write-only for designated temporary test artifacts.
* **Verifiable Proof:** `[Pending e2e sandbox test]`

> [!NOTE]
> **Relationship to `B-EXEC-01` (Ephemeral Podman Sub-Containers):** the underlying
> *capability* this contract depends on — `ContainerSubprocessExecutor` plus the opt-in
> QA-runner wiring, RO source mount / RW scratch mount, `--network none`, non-root `--user`,
> and guaranteed container cleanup — is **built and complete** under
> [`B-EXEC-01`](../../features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md). `INT-US-09`
> itself remains ⬜ **Pending**: it is the *integration contract* that would make containerized
> execution the enforced US-9 default (wiring `US-5 Core` + `E-EXEC-01` + `C-EXEC-02` together),
> not the from-scratch capability build. `B-EXEC-01` ships opt-in (`execution_mode` defaults to
> `"host"`); this contract is what flips it on by default and proves it end-to-end. Designing
> `INT-US-09` is separate, not-yet-started work.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
