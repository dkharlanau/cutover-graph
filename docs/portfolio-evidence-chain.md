# Portfolio evidence chain

Cutover Graph is one step in a wider executable portfolio. The strongest integration is evidence flow, not duplicated schemas or hand-maintained cross-links.

The first live chain is:

```text
Mapping as Code lookup artifact
  -> Reconciliation as Code field_match
  -> passed evidence v1 JSON
  -> Cutover Graph local evidence registry
  -> verified reconciliation checkpoint
  -> verified Cutover artifact index
  -> dependent cutover task becomes executable
```

## What the contract proves

The dedicated `Cross-repo evidence contract` workflow checks out the current public `reconciliation-as-code` main branch and executes its Mapping as Code bridge example. No passed reconciliation document is copied into this repository for the contract test.

The workflow verifies five boundaries:

1. **Mapping provenance** — the reconciliation evidence contains the exact Mapping as Code `mapping.id`, referenced field IDs and mapping artifact SHA-256.
2. **Reconciliation identity** — the evidence has a real RAC run ID and configuration fingerprint produced by the deterministic reconciliation engine.
3. **Evidence binding** — Cutover Graph builds its registry from the exact generated evidence file and retains that document SHA-256 plus the RAC configuration SHA-256.
4. **Operational release** — the completed reconciliation task passes its external checkpoint and the dependent `open-interfaces` task appears in `verified_executable_now`.
5. **Assurance export** — the Cutover artifact index refuses to export an external-evidence checkpoint as passed unless a verification registry is supplied. With the registry, the exported checkpoint carries its verification mode and exact document/configuration hashes for downstream consumers.

## Presence is not verification

A checkpoint can be locally complete while still having an unverified external evidence reference. Those are deliberately separate states.

`checkpoint_status()` answers the local question: are required approvals and evidence references present?

`external_evidence.py` answers the stronger question: does each `eac://` reference resolve to a trusted local evidence document whose status is acceptable?

`cutover_artifacts.py` therefore behaves fail-closed for assurance export:

```bash
# External refs are preserved, but the checkpoint is exported as unverified/passed=false.
python cutover_artifacts.py cutover.json -o artifacts.json

# External refs may become passed only after registry verification.
python cutover_artifacts.py cutover.json \
  --registry evidence-registry.json \
  -o verified-artifacts.json
```

For externally backed checkpoints, a downstream evidence graph should consume the verified artifact index, not infer assurance from URI presence.

Local-only checkpoints keep their existing native semantics because there is no external evidence document to resolve.

## What it deliberately does not prove

- Cutover Graph does not execute Mapping as Code logic itself.
- Cutover Graph does not decide whether a reconciliation control is correct; it verifies the status and identity of the evidence document produced by RAC.
- Reconciliation as Code does not approve cutover progression.
- A passing synthetic reference chain is interoperability evidence, not proof that a customer migration is ready for go-live.
- A syntactically valid `eac://` URI is not evidence of a successful run until it is bound and verified.

## Why this is separate from ordinary CI

Normal Cutover Graph tests remain local and deterministic. The cross-repo workflow is an explicit interoperability contract because it depends on the current public upstream repository. It runs when the contract changes, on manual demand, and weekly after merge so upstream contract drift becomes visible without making every ordinary code change dependent on another repository.

## Next useful extension

The next portfolio proof should consume the **verified** Cutover artifact index in Project Evidence Graph. That extension should assert that a verified checkpoint becomes evidence, while a structurally identical Cutover export without its evidence registry cannot be promoted to positive assurance.
