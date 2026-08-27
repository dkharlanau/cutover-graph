# Portfolio evidence chain

Cutover Graph is one step in a wider executable portfolio. The strongest integration is evidence flow, not duplicated schemas or hand-maintained cross-links.

The first live chain is:

```text
Mapping as Code lookup artifact
  -> Reconciliation as Code field_match
  -> passed evidence v1 JSON
  -> Cutover Graph local evidence registry
  -> verified reconciliation checkpoint
  -> dependent cutover task becomes executable
```

## What the contract proves

The dedicated `Cross-repo evidence contract` workflow checks out the current public `reconciliation-as-code` main branch and executes its Mapping as Code bridge example. No passed reconciliation document is copied into this repository for the contract test.

The workflow verifies four boundaries:

1. **Mapping provenance** — the reconciliation evidence contains the exact Mapping as Code `mapping.id`, referenced field IDs and mapping artifact SHA-256.
2. **Reconciliation identity** — the evidence has a real RAC run ID and configuration fingerprint produced by the deterministic reconciliation engine.
3. **Evidence binding** — Cutover Graph builds its registry from the exact generated evidence file and retains that document SHA-256 plus the RAC configuration SHA-256.
4. **Operational release** — the completed reconciliation task passes its external checkpoint and the dependent `open-interfaces` task appears in `verified_executable_now`.

## What it deliberately does not prove

- Cutover Graph does not execute Mapping as Code logic itself.
- Cutover Graph does not decide whether a reconciliation control is correct; it verifies the status and identity of the evidence document produced by RAC.
- Reconciliation as Code does not approve cutover progression.
- A passing synthetic reference chain is interoperability evidence, not proof that a customer migration is ready for go-live.

## Why this is separate from ordinary CI

Normal Cutover Graph tests remain local and deterministic. The cross-repo workflow is an explicit interoperability contract because it depends on the current public upstream repository. It runs when the contract changes, on manual demand, and weekly after merge so upstream contract drift becomes visible without making every ordinary code change dependent on another repository.

## Next useful extension

The next portfolio proof should preserve the same rule: add a real evidence boundary rather than copying data models. A strong candidate is to connect the verified cutover/evidence output into Project Evidence Graph so a requirement/change/test path can point to the exact verified reconciliation/cutover artifacts.