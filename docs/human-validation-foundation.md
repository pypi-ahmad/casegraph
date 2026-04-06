# Human Validation Foundation

CaseGraph now provides a human-in-the-loop validation layer that sits between machine-generated outputs and operational consumption. This layer allows operators to review, accept, correct, reject, or flag machine-produced extraction fields and requirement/checklist assessments — without ever deleting or silently overwriting the original machine outputs.

## Three Core Subsystems

### 1. Field Validation

Each extracted field from a case's extraction runs can receive a human validation status:

- **accepted** — The machine-extracted value is correct as-is.
- **corrected** — The operator provides a replacement value; the original is preserved as `original.value`.
- **rejected** — The extracted value is wrong and no correction is provided.
- **needs_followup** — The field requires additional investigation before a determination can be made.

Every validation records:
- The extraction ID and field ID being validated.
- The status and (optionally) a corrected value.
- A snapshot of the original machine-extracted value and grounding references.
- Reviewer metadata (reviewer ID, timestamp).
- An optional free-text note.

Upsert semantics: calling validate again for the same extraction + field overwrites the previous validation (the audit trail preserves the history).

### 2. Requirement Review

Each checklist item from a case's readiness checklist can receive a human review:

- **confirmed_supported** — The requirement is met based on human judgment.
- **confirmed_missing** — The requirement is definitively not met.
- **requires_more_information** — Cannot determine status without additional data.
- **manually_overridden** — The operator overrides the machine assessment with a justification.

Every review records:
- The case ID, checklist ID, and item ID.
- The review status and the original machine-assessed status.
- Reviewer metadata and an optional note.

Upsert semantics apply as with field validation.

### 3. Reviewed Case State Projection

A single operation (`GET /cases/{case_id}/review-state`) computes the full reviewed state of a case by:

1. Loading all extraction runs and their fields for the case.
2. Loading all field validations for those extractions.
3. Loading the requirement checklist and all requirement reviews.
4. Merging machine outputs with human overlays to produce:
   - **Field validation summary**: counts of total, reviewed, accepted, corrected, rejected, and needs_followup fields.
   - **Requirement review summary**: counts of total, reviewed, confirmed_supported, confirmed_missing, requires_more_information, and manually_overridden items.
   - **Unresolved items list**: any field or requirement that is not in a terminal reviewed state.

This projection is read-only and computed fresh on every call. It does not cache or persist its output.

## Persistence

Two tables:

- `field_validations` — one row per extraction_id + field_id pair, with foreign key to `cases`.
- `requirement_reviews` — one row per case_id + checklist_id + item_id triple, with foreign key to `cases`.

Both store structured JSON columns for original value snapshots, grounding references, and reviewer metadata.

## Audit Integration

- New audit event category: `human_validation`.
- New audit event types: `field_validation_recorded`, `requirement_review_recorded`.
- New decision types: `field_validated`, `requirement_reviewed`.
- Each validation or review action emits an audit event and a linked decision ledger entry, following the same pattern as other CaseGraph audit hooks.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/cases/{case_id}/review-state` | Computed reviewed case state projection |
| `GET` | `/cases/{case_id}/extraction-validations` | List all field validations for a case |
| `POST` | `/extractions/{extraction_id}/fields/{field_id}/validate` | Record or update a field validation |
| `GET` | `/cases/{case_id}/requirement-reviews` | List all requirement reviews for a case |
| `POST` | `/cases/{case_id}/checklist/items/{item_id}/review` | Record or update a requirement review |

## Packet & Workflow Integration

- Assembled packets include a `human_review_state` section containing the field validation and requirement review summaries.
- Workflow pack orchestration includes a `human_review_check` stage that runs the reviewed state projection and reports summary counts.

## Frontend

- Validation workspace at `/cases/{caseId}/validation` inside the authenticated dashboard.
- Shows extracted fields with validation controls (accept, correct, reject, follow-up).
- Shows checklist requirements with review controls (confirmed, missing, need info).
- Displays summary counts and unresolved items.
- Navigation links added to case detail, audit timeline, packets, operator review, and automation runs pages.

## Shared Contracts

Full Python + TypeScript type parity in the agent-sdk:
- `FieldValidationStatus`, `RequirementReviewStatus` status literals.
- `FieldValidationRecord`, `RequirementReviewRecord` data records.
- `OriginalValueReference`, `ReviewerMetadata` supporting types.
- `ReviewedCaseState`, `FieldValidationSummary`, `RequirementReviewSummary`, `UnresolvedReviewItem` projection types.
- `ValidateFieldRequest`, `ReviewRequirementRequest` request types.
- Six response wrapper types for API endpoints.
- `HumanReviewCheckSummary` for workflow pack stage output.
- New literals in `AuditEventCategory`, `AuditEventType`, `DecisionType`, `PacketSectionType`, `WorkflowPackStageId`.

## Honest Scope

- This is a local-first validation overlay, not a certified adjudication system.
- No role-based access control gates who can validate — all authenticated dashboard users can perform validations.
- No collaborative annotation, multi-reviewer consensus, or conflict resolution is implemented.
- No autonomous or AI-assisted validation is performed — all validation actions are explicit human operator decisions.
- The reviewed state projection is computed on-demand, not cached or materialized.
- The audit trail records each validation action but not detailed field-level change diffs.
- Human validation itself does not auto-promote case state into downstream release readiness; the reviewed handoff layer adds a separate immutable snapshot, explicit sign-off, and descriptive handoff gate.

## Likely Next Steps

- Role-based validation permissions once the auth model supports roles.
- Validation summary dashboards and cross-case analytics.
- Expanded role and policy controls around who can create, sign off, and select reviewed snapshots.
- Batch validation workflows for high-volume extraction review.
- Formal change tracking with versioned validation history beyond audit events.
