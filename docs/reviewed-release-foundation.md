# Reviewed Release Foundation

CaseGraph now provides a reviewed release layer that turns signed-off reviewed snapshots into explicit release bundles containing frozen downstream artifacts. This layer generates reviewed-source packets, submission drafts, communication drafts, and automation plan metadata from a single reviewed snapshot, persists the release bundle with full provenance, and records audit events and lineage edges.

This foundation does not claim final approval, regulatory certification, compliance clearance, or authoritative deployment. It creates explicit release artifacts so downstream work can consume reviewed state honestly and traceably.

## Core Capabilities

### 1. Release Bundle Generation

`POST /cases/{case_id}/releases` creates a release bundle from a signed-off reviewed snapshot.

Each bundle includes:

- source metadata capturing the snapshot id, sign-off id, operator, timestamp, and snapshot content summary
- artifact entries for each downstream artifact generated (or skipped/failed)
- summary counts for total, generated, skipped, blocked, and failed artifacts
- operator note and creation timestamp

The request supports flags controlling which downstream artifacts to generate:

- `generate_packet` — generate a reviewed-source packet from the snapshot
- `generate_submission_draft` — generate a submission draft from the reviewed packet
- `generate_communication_draft` — generate a communication draft (packet cover note) from the reviewed packet
- `include_automation_plan_metadata` — record an automation plan metadata marker

### 2. Frozen Downstream Artifacts

Each release bundle generates downstream artifacts using the reviewed snapshot as the sole source of truth:

- **Reviewed packet**: calls `PacketAssemblyService.generate_packet(source_mode="reviewed_snapshot")` to create an immutable packet from reviewed fields
- **Reviewed submission draft**: calls `SubmissionDraftService.create_draft()` using the reviewed packet as input
- **Reviewed communication draft**: calls `CommunicationDraftService.generate_draft()` using the `packet_cover_note` template with deterministic-only strategy
- **Reviewed automation plan metadata**: records a provenance marker for automation plan derivation

If a downstream artifact cannot be generated (e.g., no packet exists for a submission draft), it is recorded as `skipped_missing_data` rather than failing the entire bundle.

### 3. Release Eligibility

`GET /cases/{case_id}/release-eligibility` evaluates whether a case is eligible for release bundle creation.

Release eligibility reuses the reviewed handoff eligibility checks:

- a signed-off reviewed snapshot must exist
- the snapshot must have no unresolved review items
- required checklist requirements must have explicit reviews

The response reports all blocking reasons, not just the first.

### 4. Reviewed Snapshot Provenance

Every artifact in a release bundle records:

- `source_mode: "reviewed_snapshot"` — declares the artifact was generated from a reviewed snapshot, not live state
- `source_snapshot_id` — links directly to the reviewed snapshot
- Source metadata on the bundle captures the sign-off operator, timestamp, and snapshot content summary

### 5. Audit and Lineage Integration

Release bundle creation emits:

- `release_bundle_created` audit event (category: `reviewed_release`)
- `release_bundle_created` decision record
- Lineage record with edges to: case context, reviewed snapshot source, and each generated downstream artifact via `release_bundle_source` relationship

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/cases/{case_id}/releases` | List release bundles for a case |
| POST | `/cases/{case_id}/releases` | Create a release bundle |
| GET | `/releases/{release_id}` | Get a single release bundle |
| GET | `/releases/{release_id}/artifacts` | Get artifacts for a release bundle |
| GET | `/cases/{case_id}/release-eligibility` | Check release eligibility |

## Frontend

The release workspace is available at `/cases/{caseId}/releases` and provides:

- Release eligibility display with blocking reason details
- Release bundle creation form with operator id and note
- Release list showing status, artifact counts, and creation dates
- Release detail view with full artifact inspection
- Navigation links from case workspace and reviewed handoff pages

## What Is Real vs Deferred

### Real (implemented now)

- Release bundle persistence with full source metadata
- Reviewed-source packet generation
- Reviewed-source submission draft generation
- Basic communication draft generation (packet cover note, deterministic template)
- Automation plan metadata marker
- Release eligibility checks (reusing handoff eligibility)
- Audit events and lineage records
- API endpoints for all CRUD operations
- Frontend release workspace with eligibility, creation, and inspection

### Deferred (for later)

- **Custom communication templates**: only `packet_cover_note` is used; configurable template selection is deferred
- **Automation plan execution**: only metadata is recorded; actual plan generation and execution from release context is deferred
- **Release status transitions**: `superseded_placeholder` and `archived_placeholder` statuses exist in contracts but are not used yet
- **Release comparison**: comparing artifacts across release bundles is deferred
- **Release export/download**: bundling release artifacts into a downloadable archive is deferred
- **External system integration**: pushing release artifacts to external systems is deferred
- **Release approval workflow**: multi-step approval chains are explicitly out of scope

## Limitations

- Communication draft generation requires the `packet_cover_note` template to exist in the communications module
- Automation plan metadata is a provenance marker, not a generated plan — actual plan generation requires capabilities loader integration
- Release eligibility is descriptive, not authoritative — it does not encode external compliance requirements
- No release versioning or diff — each bundle is independent
