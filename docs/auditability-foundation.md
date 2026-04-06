# Auditability Foundation

CaseGraph now records local-first operational traceability for a focused set of real case mutations. The goal is to show what changed, which decisions were recorded, and which persisted artifacts were used to derive downstream outputs.

## Implemented

- Append-oriented audit event storage for case, checklist, review, extraction, packet, submission, automation, communication, and workflow-pack activity.
- Decision ledger entries linked to the originating audit event when the platform records a readiness evaluation, stage transition, review note, approval update, checkpoint decision, packet generation, communication draft generation or review update, automation plan, or workflow-pack result.
- Artifact lineage records and edges for derived artifacts such as checklists, extraction runs, packets, submission drafts, automation plans, automation runs, and communication drafts.
- Protected case audit UI at `/cases/{caseId}/audit` inside the authenticated dashboard, backed entirely by persisted backend records.
- Case-scoped audit APIs:
- `GET /cases/{case_id}/audit`
- `GET /cases/{case_id}/decisions`
- `GET /cases/{case_id}/lineage`
- `GET /artifacts/{artifact_type}/{artifact_id}/lineage`

## Current Mutation Coverage

- Case creation, case updates, and case-document linking.
- Checklist generation and checklist evaluation.
- Manual case stage transitions and review note creation.
- Packet generation.
- Submission draft creation, approval updates, and dry-run automation plan generation.
- Automation run creation plus checkpoint approve, skip, and block decisions.
- Communication draft generation and review updates.
- Extraction result persistence for case-scoped runs.
- Workflow-pack run completion.

## Honest Scope

- This is not a compliance archive, WORM store, tamper-proof ledger, or notarized evidence system.
- No cryptographic sealing, external anchoring, or immutable object storage is implemented in this step.
- No synthetic backfill is created for activity that happened before these hooks existed.
- Lineage is recorded only at the granularity the current services actually know at the time of mutation.
- The audit API endpoints currently follow the same local backend trust model as the rest of this foundation; the protected surface in this step is the dashboard UI.

## Likely Next Steps

- Add exportable audit bundles and tamper-evident packaging if the product needs stronger chain-of-custody guarantees.
- Add actor identity integration beyond local operator identifiers.
- Add broader audit search and retention controls once cross-case operational usage is defined.