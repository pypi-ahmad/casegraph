# Target Pack Foundation

## Scope

The target-pack foundation adds a versioned metadata layer for downstream submission destinations without claiming official support for any payer, insurer, agency, form, or portal.

Target packs describe:

- target organization/category metadata
- explicit compatibility with domain packs, case types, workflow packs, and submission targets
- target field schema sections for deterministic mapping previews
- requirement overrides or additive requirement metadata
- extraction and communication template bindings
- automation-planning compatibility metadata

This is metadata for review, routing, and planning. It is not a rules engine, filing system, adjudication engine, tax engine, or compliance certification layer.

## Registry and Versioning

Target packs are first-class registry objects defined in code and loaded into the API at startup. Each pack has:

- a stable `pack_id`
- a semantic `version`
- a lifecycle status (`draft_metadata`, `active_metadata`, `superseded`)
- descriptive notes and explicit limitations

The current starter registry contains six generic packs:

- `generic_prior_auth_packet_v1`
- `generic_preclaim_packet_v1`
- `generic_insurance_claim_packet_v1`
- `generic_coverage_correspondence_packet_v1`
- `generic_tax_notice_packet_v1`
- `generic_tax_intake_packet_v1`

These starter packs are intentionally generic. They do not imply support for named payers, insurers, agencies, portals, or official forms.

## Field Schemas and Requirement Overrides

Each target pack can define a target field schema made of named sections and field definitions. Fields include:

- a stable field identifier
- display metadata
- field type (`text`, `identifier`, `date`, `document_list`, and similar)
- required/optional status
- candidate source paths grounded in existing case, packet, and extraction state
- notes describing the quality or intent of the mapping

Requirement overrides are also metadata-only. They can:

- refine the display or grouping of an existing base requirement
- add a new requirement placeholder for target-specific review

Overrides do not mutate or replace the underlying case-type registry requirements. They are applied as additive downstream context.

## Case Selection and Downstream Use

Cases can select a compatible target pack through a dedicated case-level API and protected dashboard UI. The selected pack reference is stored in case metadata as a typed selection record.

Only the selection reference is persisted, not a frozen copy of the registry entry. That selection currently flows into:

- submission draft source metadata
- dry-run automation plan responses reconstructed from persisted draft metadata
- reviewed release source provenance

When a submission draft is created, target-pack field definitions are merged into the selected submission target field set so the mapping preview can expose destination-specific fields. Automation plan responses reconstruct target-pack automation compatibility metadata only when the stored selection still matches a currently registered pack id and version.

## Honest Non-Claims

The target-pack foundation does not provide:

- real portal automation selectors or flows
- live filing or submission capability
- official payer/insurer/agency integrations
- authoritative form-completion guarantees
- regulatory or legal correctness guarantees
- destination-specific validation rules beyond explicit registry metadata

## Current Limitations

- Packs are registry-defined starter metadata only. There is no admin UI for authoring or publishing target packs yet.
- Case selection stores a typed reference in case metadata; there is no separate target-pack database table yet.
- Compatibility is explicit and static. There is no inference engine for deriving compatibility from external attributes.
- Field schemas support mapping previews and review, not full destination-specific completeness validation.
- Requirement overrides are additive metadata and do not recalculate case readiness by themselves.
- Reviewed release and submission provenance store the selected reference and version, not a frozen snapshot of the full target-pack definition.
- Target-pack overlays are only reapplied when the persisted selection still matches a registered pack id and version; otherwise the selection is preserved as provenance but no current registry overlay is assumed.