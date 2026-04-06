# Reviewed Handoff Foundation

CaseGraph now provides a reviewed handoff layer between human validation and downstream packet, submission, and automation consumption. This layer turns the current reviewed state of a case into an immutable reviewed snapshot, records explicit operator sign-off, computes descriptive handoff eligibility, and propagates reviewed-source provenance into downstream artifacts.

This foundation does not claim final approval, regulatory certification, compliance clearance, or authoritative release management. It creates explicit reviewed handoff artifacts so downstream work can consume reviewed state honestly and traceably.

## Four Core Capabilities

### 1. Immutable Reviewed Snapshots

`POST /cases/{case_id}/reviewed-snapshots` materializes the current human-reviewed state of a case into a persisted snapshot record.

Each snapshot includes:

- reviewed field entries, preserving the original machine value, reviewed overlay, and final snapshot value when included
- reviewed requirement entries, preserving the original machine-assessed checklist status and the human review outcome
- unresolved review item summaries copied from the current reviewed-state projection
- source metadata listing linked documents, extraction runs, validation record ids, checklist id, and requirement review ids
- summary counts for included fields, corrected fields, reviewed requirements, and unresolved items

The snapshot is immutable once created. Creating another snapshot produces a new record rather than rewriting the previous one.

### 2. Explicit Operator Sign-Off

`POST /reviewed-snapshots/{snapshot_id}/signoff` records a separate sign-off record for a reviewed snapshot.

Sign-off stores:

- operator id and optional display name
- optional sign-off note
- explicit timestamp

Sign-off is intentionally separate from snapshot creation so CaseGraph never implies that a created reviewed snapshot was automatically approved.

### 3. Descriptive Handoff Eligibility

`GET /cases/{case_id}/handoff-eligibility` evaluates the currently selected reviewed snapshot, or the latest snapshot when nothing is selected, against the current reviewed handoff rules.

Current rules block handoff when:

- no reviewed snapshot exists
- the candidate snapshot has not been explicitly signed off
- unresolved review items remain in the snapshot
- required checklist items are still missing explicit human review

The response is descriptive, not authoritative. It tells the operator which current handoff rules pass or fail without pretending to encode external compliance or final release governance.

### 4. Downstream Source-Mode Propagation

Packets can now be generated from either:

- `live_case_state`
- `reviewed_snapshot`

When `reviewed_snapshot` is selected:

- packet generation resolves a signed-off, handoff-eligible snapshot before proceeding
- packet manifests and packet summaries record source mode and reviewed snapshot id
- packet exports render reviewed snapshot provenance and snapshot content summaries
- submission draft mapping uses reviewed snapshot field values instead of silently reading current live extraction values
- submission drafts, automation plans, and automation runs persist source mode and reviewed snapshot id for later inspection

This keeps downstream artifacts honest about whether they came from current live state or from a reviewed handoff checkpoint.

## Persistence

New tables:

- `reviewed_snapshots`
- `reviewed_snapshot_signoffs`

New downstream provenance columns:

- `case_packets.source_mode`, `case_packets.source_reviewed_snapshot_id`
- `submission_drafts.source_mode`, `submission_drafts.source_reviewed_snapshot_id`
- `submission_automation_plans.source_mode`, `submission_automation_plans.source_reviewed_snapshot_id`
- `automation_runs.source_mode`, `automation_runs.source_reviewed_snapshot_id`

SQLite compatibility upgrades add these columns for existing local databases.

## Audit And Lineage

Reviewed handoff extends the existing audit and lineage model with:

- audit category: `reviewed_handoff`
- events: `reviewed_snapshot_created`, `reviewed_snapshot_signed_off`, `reviewed_snapshot_selected_for_handoff`
- decision type: `reviewed_snapshot_signed_off`
- lineage artifact type: `reviewed_snapshot`
- lineage relationship: `snapshot_source`

Reviewed snapshots record lineage to the case, linked documents, checklist reference, and extraction runs used when the snapshot was created. Downstream packets, submission drafts, and automation plans/runs add snapshot lineage when their source mode is `reviewed_snapshot`.

## Frontend

Protected dashboard route:

- `/cases/{caseId}/handoff`

The reviewed handoff workspace supports:

- snapshot creation
- explicit sign-off
- handoff eligibility inspection
- selection of the currently eligible reviewed snapshot to use for downstream handoff

The packet workspace now allows packet generation from a reviewed snapshot, and submission / automation workspaces surface reviewed-source provenance in summaries and detail panels.

## Honest Scope

- No multi-party approval chain, revocation workflow, or role-based authorization model is implemented yet.
- No external release policy engine, compliance checklist, payer rule pack, or regulatory readiness certification is encoded.
- Selection for handoff only applies to a currently eligible reviewed snapshot and marks the reviewed artifact CaseGraph should prefer for downstream reviewed-source work; it is not a legal or compliance sign-off.
- Reviewed snapshots preserve reviewed state at a point in time, but they do not freeze the rest of the case record or prevent operators from continuing later validation work.
- Downstream reviewed-source propagation currently covers packets, submission drafts, automation plans, and automation runs. It does not yet gate every possible future artifact type.

## Likely Next Steps

- Role-aware permissions for snapshot creation, sign-off, and selection.
- Snapshot comparison and diff views across successive reviewed handoff records.
- Revocation or supersession semantics for sign-off records.
- Expanded downstream reviewed-source handling for additional artifact types and export flows.