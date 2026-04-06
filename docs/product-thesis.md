# CaseGraph — Product Thesis

> This document defines the business problem CaseGraph exists to solve, the solution approach, operational guardrails, and how the platform's technical architecture maps to real work value. It is grounded in what the codebase actually implements and plans — nothing is exaggerated, and limitations are stated explicitly.

---

## 1. The Problem

Regulated and document-heavy operations — medical records review, insurance claims intake, prior authorization coordination, policy administration, tax notice handling — share a common structural failure: the work is repetitive, fragmented, and poorly traced.

The daily reality for teams in these domains:

- **Manual document triage.** Operators receive packets of PDFs, scanned images, faxes, and portal exports. They spend time opening, reading, sorting, and extracting the same categories of information (names, dates, policy numbers, diagnosis codes, amounts) from each packet.
- **Fragmented tool landscape.** A single case may touch an email inbox, a document management system, a payer portal, a spreadsheet tracker, an internal review tool, and a filing system. There is no unified workspace. Context is scattered.
- **Repeated extraction of the same facts.** The same patient name, claim number, or tax notice ID gets manually copied into multiple systems across the lifecycle of a single case. There is no structured reuse.
- **Inconsistent processing.** Without standardized workflows, two operators handling similar cases may follow different steps, miss different requirements, and produce different quality of output. Institutional knowledge lives in people's heads or buried in ad-hoc process docs.
- **Poor traceability.** When a case is reviewed, escalated, or audited, it is difficult to reconstruct what happened, what evidence was considered, what was extracted, and what decision path was followed. Audit trails are manual or absent.
- **Slow case assembly.** Before any real analysis can begin, an operator must locate the right documents, verify they are complete, extract baseline facts, and assemble a working view of the case. This setup work is overhead that repeats for every case.
- **Portal and administrative burden.** Operators spend time navigating web portals to look up status, retrieve documents, submit forms, and update records — work that follows predictable patterns but remains manual.

These patterns recur across healthcare, insurance, and tax/compliance operations. The result is slow handling, repeated rework, and inconsistent case preparation.

---

## 2. Who Experiences This

The people most affected work in operational and coordination roles:

- **Operations analysts and case workers** who process incoming packets, extract required data, and assemble case files across medical, insurance, and tax domains.
- **Claims and pre-authorization coordinators** who gather clinical documentation, verify coverage, assemble evidence packets, and track case progress through review stages.
- **Intake and review teams** who triage incoming requests, classify document types, route work, and prepare cases for decision-making.
- **Insurance operations staff** who handle policy reviews, coverage determinations, and notice processing across personal and commercial lines.
- **Tax document handling teams** who process notices, reconcile filings, gather supporting documents, and prepare response packets.
- **Internal compliance and process teams** who need to verify that operational work was performed consistently, with proper evidence linkage and traceability.

These roles share a common pattern: the work includes repeated assembly, lookup, extraction, and coordination before final review can even begin.

---

## 3. Why Current Workflows Are Broken

The operational failures above are not caused by lack of effort. They emerge from structural problems in how work is organized:

- **Copy-paste as integration.** Data moves between systems through manual copy-paste. This is slow, error-prone, and untraced.
- **Siloed tools with no case context.** Each tool (email, portal, spreadsheet, document viewer) operates independently. None of them know what case the operator is working on or what has already been done.
- **No evidence linkage.** When a fact is stated in a review or a decision is made, there is no structured link back to the source document, page, or extracted field. Verification requires manual re-reading.
- **Repeated manual review.** Multiple people may re-read the same document because there is no shared extraction or annotation layer. Prior work is not reusable.
- **Weak case-centric coordination.** Most tools are organized around documents or tasks in isolation, not around the case as a whole. Operators must mentally reconstruct the case state from scattered sources.
- **No structured reuse of prior work.** Knowledge gained in one case (extracted fields, retrieved evidence, assembled context) does not carry forward to similar cases in any structured way.
- **Traceability gaps.** When something needs to be audited or escalated, reconstructing the sequence of actions, documents considered, and logic applied requires manual archaeology.

---

## 4. Why a Generic Chatbot Is Not Enough

General-purpose AI chat interfaces can answer questions and generate text, but they do not solve the structural problems described above. The operational domains CaseGraph targets require a system that is:

- **Case-centric.** Work must be organized around a persistent case workspace, not a conversation thread. A case accumulates documents, extracted data, evidence, runs, and status over time.
- **Document-aware.** The system must ingest real documents (PDFs, scans, images), extract structured content, preserve source geometry, and link extracted facts back to their origin pages and blocks.
- **Retrieval-aware.** Answers and outputs must be grounded in evidence retrieved from the case's own document base, not generated from general training data alone.
- **Workflow-aware.** Operational work follows repeatable patterns (intake → extraction → review → output). The system must support defined workflows, not free-form conversation.
- **Reviewable.** Every extraction, every retrieved evidence chunk, every generated output must be inspectable by a human operator. The system assists — it does not autonomously decide.
- **Auditable.** Runs, events, and lifecycle transitions must be recorded so that what happened on a case can be reconstructed later.
- **Agent and tool orchestrated.** Complex operational work requires multiple specialized capabilities (extraction, retrieval, classification, automation) coordinated through defined agent roles and tool registries — not a single monolithic prompt.
- **Human-in-the-loop.** In regulated domains, the human operator remains the decision-maker. The system reduces their assembly and extraction burden; it does not replace their judgment.

A chat interface can be a component within such a system. It cannot be the system itself.

---

## 5. The Solution Thesis

**CaseGraph is a local-first, BYOK, case-centric operating platform for document-heavy and workflow-heavy operations in regulated domains.**

It provides a unified workspace where operators can:

1. **Ingest and process document packets** — PDFs, scans, and images are ingested with real text extraction and OCR, producing structured page-level artifacts with source geometry.
2. **Extract structured data from documents** — Schema-driven extraction templates pull typed fields from ingested documents, with source grounding that links each extracted value back to its origin page and text block.
3. **Build and search a case knowledge base** — Ingested document content is chunked, embedded, and indexed locally. Retrieval queries return evidence grounded in the case's own documents.
4. **Assemble and manage case workspaces** — Cases are persistent workspaces that accumulate linked documents, domain context, extraction results, evidence, workflow runs, and operational status.
5. **Execute the currently supported workflow paths** — Direct task execution and evidence-backed task execution run against user-provided LLM keys, producing traced results with lifecycle events and optional structured output.
6. **Specialize by domain and jurisdiction** — Domain packs provide operational metadata (case types, document requirements, workflow bindings, extraction bindings) for medical, insurance, and tax operations across US and India jurisdictions.
7. **Prepare grounded communication drafts** — CaseGraph can now prepare reviewable missing-document requests, internal handoff notes, and packet cover note drafts from explicit case state, with source references and optional provider-assisted wording.
8. **Inspect and review everything** — Document review workspaces show page images with real extraction geometry overlays. Extraction results show source grounding. RAG results show retrieved evidence chunks and citations. All runs record lifecycle events.

### What CaseGraph is not

CaseGraph is not a chatbot, not a generic AI dashboard, and not a tool marketplace. It is an operational workspace where the unit of work is the *case*, the raw material is *documents and evidence*, and the execution model is *defined workflows with human review*.

### Architecture principles

- **BYOK (Bring Your Own Key).** CaseGraph does not bundle or resell model access. Operators provide their own API keys for OpenAI, Anthropic, or Gemini. The platform routes to the selected provider.
- **Local-first.** Data stays local by default. SQLite for persistence, local embedding models, local vector stores (ChromaDB/Milvus Lite), local file storage for artifacts. No mandatory cloud dependency for core operations.
- **Open-source-first for non-model infrastructure.** Embedding, vector storage, OCR, document processing, and orchestration use open-source components where practical.
- **Multi-agent architecture.** The agent runtime supports multiple specialized agents (intake, router, review) coordinated through a supervisor graph. Workflows define multi-step agent coordination. Today, agents are placeholder-only; the execution foundation is real.
- **Registry-driven extensibility.** Providers, agents, tools, extraction templates, domain packs, tasks, and workflows are all managed through typed in-memory registries. Adding new capabilities follows a consistent registration pattern.

---

## 6. Core Jobs to Be Done

CaseGraph is designed to reduce the time and inconsistency of repeatable operational work. The core job shapes:

1. **Ingest and normalize a document packet.** Accept a set of files, extract text and structure, and produce normalized page-level artifacts ready for downstream use.
2. **Extract required facts from documents.** Apply schema-driven extraction templates to pull typed fields (names, dates, identifiers, amounts, categories) with source grounding references.
3. **Link facts to evidence.** Connect extracted values and generated outputs to their source documents, pages, and text blocks so that any claim can be verified by inspection.
4. **Retrieve related supporting information.** Search the case's indexed knowledge base for evidence relevant to a query, returning ranked chunks with source metadata.
5. **Assemble a reviewable case workspace.** Bring together documents, extractions, evidence, domain context, and run history into a single persistent workspace for a specific case.
6. **Choose and execute a workflow.** Select a defined workflow (task execution, evidence-backed execution) appropriate for the case type and run it with traceability.
7. **Track what happened and why.** Record lifecycle events, execution metadata, and run results so that the history of a case is reconstructable.
8. **Hand off work across agents and tools.** Coordinate specialized capabilities (extraction, retrieval, classification, automation) through defined agent roles and tool registries rather than manual operator switching.
9. **Prepare structured outputs for operator review.** Produce typed, inspectable results (extracted fields, evidence-backed answers, structured summaries) that operators can review, verify, and act on.
10. **Prepare reviewable communication artifacts.** Turn current case state into operator-reviewed outreach or handoff drafts without sending them externally or inventing missing facts.
11. **Automate repetitive browser and portal steps.** Where appropriate and approved, use browser automation (Playwright MCP, computer-use adapters) to reduce manual portal navigation. This capability is scaffolded but not yet executing.

---

## 7. System Guardrails and Non-Goals

### What CaseGraph is NOT

- **Not a medical diagnosis engine.** CaseGraph does not diagnose conditions, recommend treatments, or make clinical decisions. It helps organize and extract information from medical documents.
- **Not a claim adjudication engine.** CaseGraph does not approve or deny insurance claims. It helps intake, extract, and organize claim packets for human review.
- **Not a tax filing engine.** CaseGraph does not file tax returns, calculate tax liability, or interpret tax law. It helps organize tax documents and notices.
- **Not a legal decision engine.** CaseGraph does not provide legal advice or make legal determinations.
- **Not an autonomous submission engine.** CaseGraph does not submit forms, filings, or responses to external systems without explicit human approval. No autonomous submissions are implemented.
- **Not a fully autonomous browser agent.** Browser automation adapters are scaffolded for future use. No browser actions execute autonomously today.
- **Not a guaranteed compliance engine.** CaseGraph provides operational structure (domain packs, document requirements, workflow definitions). It does not guarantee regulatory compliance. Compliance remains the operator's responsibility.

### Safety and honesty guardrails

- **Final decisions stay human-reviewed.** The system assists with assembly, extraction, retrieval, and preparation. Operators make decisions.
- **Grounding and evidence must be honest.** Source grounding references (page numbers, text blocks, geometry) are only shown when they genuinely exist from the extraction or ingestion process. No fabricated citations, confidence scores, or geometry.
- **Domain packs are metadata and workflow structure first.** They define case types, document requirements, and workflow/extraction bindings. They are not rules engines, payer databases, or regulatory codebooks.
- **Extraction templates produce structured fields, not interpretations.** The extraction layer pulls typed values from document text. It does not interpret medical codes, adjudicate claims, or calculate tax obligations.
- **No fabricated metrics or benchmarks.** This document and the platform do not claim specific accuracy rates, time savings, or ROI figures that have not been measured.

---

## 8. What "Good" Looks Like

Success for CaseGraph is measured in operational improvement categories, not fabricated benchmarks:

- **Reduced manual document triage.** Less time spent opening, reading, and classifying incoming document packets before real work begins.
- **Faster case setup.** A case workspace with linked documents, domain context, and extraction results assembled with less manual gathering and fewer disconnected handoffs.
- **More consistent extraction.** Schema-driven extraction produces the same structured output regardless of which operator runs it, reducing variability.
- **Clearer evidence linkage.** Every extracted fact and generated output links back to its source document and page, making verification straightforward.
- **Fewer lost attachments and context.** A case workspace accumulates all relevant documents, evidence, and run history in one place instead of across scattered tools.
- **Cleaner workflow traceability.** Run records with lifecycle events make it possible to reconstruct what happened on a case without manual investigation.
- **More reviewable outputs.** Structured extraction results, evidence-backed answers, and source grounding give operators inspectable artifacts instead of opaque outputs.
- **Better operator handoff quality.** When a case is handed from one operator to another, the workspace carries its full context — documents, extractions, evidence, domain metadata, and run history.
- **Faster communication preparation.** Reviewable drafts reduce the amount of manual summarization and checklist transcription required before an operator can ask for missing material or hand off a case.
- **Safer automation boundaries.** Browser automation and agent execution are gated, traced, and human-approved rather than opaque and autonomous.

---

## 9. Architecture-to-Value Mapping

How each major technical pillar in the current codebase maps to operational value:

| Technical Pillar | What It Does Today | Business Value |
|---|---|---|
| **BYOK provider layer** | Validates API keys, discovers models, routes to OpenAI/Anthropic/Gemini per request | Operators choose their own model provider without vendor lock-in. No bundled model cost. |
| **Document ingestion + OCR** | Ingests PDFs and images, extracts text via PyMuPDF or RapidOCR, produces page-level artifacts with source geometry | Operationalizes messy document packets — scanned records, faxes, born-digital PDFs — into structured, reviewable page artifacts. |
| **Document review workspace** | Renders page images with SVG bounding-box and polygon overlays from real extraction geometry | Operators can visually verify what was extracted and where, reducing blind trust in extraction output. |
| **Knowledge retrieval (RAG)** | Chunks, embeds, and indexes document content locally; semantic search returns ranked evidence | Enables reusable evidence-backed work instead of operators re-reading documents for every question. |
| **Case workspaces** | Persistent case records with linked documents, domain context, run history, and status | A single operational workspace per case replaces scattered tracking across tools and inboxes. |
| **Communication draft layer** | Creates reviewable missing-document requests, handoff notes, and packet cover notes from explicit case state, with source and evidence references | Reduces manual status-summary and outreach-preparation work while keeping operators in control of final wording and delivery. |
| **Run execution + lifecycle events** | Task execution and RAG execution produce traced results with recorded lifecycle events | Every action on a case is recorded and reconstructable, supporting audit and review. |
| **Extraction templates** | Schema-driven structured extraction with source grounding to document pages and text blocks | Repeatable, consistent intake and review — the same fields extracted the same way every time. |
| **Domain packs** | Jurisdiction-aware case type templates with document requirements, workflow bindings, and extraction bindings | Operational specialization by domain (medical, insurance, tax) and jurisdiction (US, India) without building separate systems. |
| **Automation adapters** | Playwright MCP tool adapters and computer-use provider metadata (scaffolded, not executing) | Future reduction of repetitive browser and portal administration work, within defined safety boundaries. |
| **Eval and observability** | Promptfoo benchmark scaffolds, Langfuse trace integration at execution boundaries | Safer iteration — ability to measure and regression-test changes to extraction, retrieval, and generation quality. |
| **Agent runtime + supervisor graph** | Typed agent registry, workflow definitions, supervisor graph compilation, handoff structure | Foundation for multi-agent coordination where specialized agents handle different operational steps. Not executing real intelligence yet. |
| **Auth + protected UI** | Local credentials, JWT sessions, protected dashboard pages | Operator-scoped access to case workspaces without requiring external identity infrastructure for local deployment. |

---

## 10. Current Implementation Status

> Honest accounting of what exists today vs. what is planned.

### Implemented and functional

- BYOK provider validation, model discovery, and per-request routing (OpenAI, Anthropic, Gemini)
- Document ingestion with readable PDF extraction (PyMuPDF) and OCR (RapidOCR) paths
- Page-level artifact persistence with source geometry (bounding boxes, polygons, coordinate spaces)
- Document review workspace with page image viewer and geometry overlays
- Knowledge base with local embedding (sentence-transformers), vector store (ChromaDB/Milvus Lite), chunking, and semantic search
- Persistent case workspaces with document linking, domain context, and run tracking
- Case-scoped communication draft generation for missing-document requests, internal handoff notes, and packet cover notes, with source metadata and optional provider-assisted wording
- Single-turn provider-backed task execution with structured output
- Single-turn evidence-backed (RAG) task execution with citation extraction
- Schema-driven extraction with three generic templates and source grounding
- Domain pack registry with eight jurisdiction-aware packs and case type templates
- Ten built-in domain workflow packs across medical insurance, general insurance, and tax operations, all reusing the same explicit stage orchestration pattern
- Eval/observability instrumentation hooks (Langfuse) and benchmark scaffolds (Promptfoo)
- Browser automation tool adapters (Playwright MCP) — adapter boundary only
- Computer-use provider capability metadata — metadata only
- Agent runtime with supervisor graph, typed agents, and workflow definitions — placeholder execution only
- Protected frontend with auth, case management, document review, extraction lab, RAG lab, domain explorer, and inspection pages

### Not yet implemented

- Real LLM-powered agent intelligence (agents return placeholder results)
- Multi-turn conversation or streaming
- Autonomous multi-agent reasoning or execution
- General workflow execution engine (only ten built-in domain workflow packs work today)
- Domain-specific extraction templates, tasks, or prompts
- Browser automation execution (adapters exist, MCP client does not)
- Computer-use execution
- Per-case document requirement fulfillment tracking
- Outbound communication delivery, recipient resolution, or communication tracking
- Human review stages, approval workflows, or collaboration features
- Production database migration tooling
- CI/CD pipeline
- Docker Compose or deployment configuration
- Multi-tenant isolation or organization-level access control
- Cost tracking or budget enforcement

---

## 11. Assumptions

This document makes the following assumptions:

1. The platform will continue to target regulated and document-heavy operational domains (medical, insurance, tax) rather than general-purpose AI use cases.
2. BYOK model access will remain the primary model integration path. CaseGraph will not bundle or resell model API access.
3. Local-first deployment will remain the default. Cloud deployment paths may be added but will not replace local operation.
4. The case workspace will remain the primary unit of operational organization.
5. Human-in-the-loop review will remain a design requirement for all domains, not an optional mode.
6. Domain packs will expand in specificity (more case types, more jurisdiction-specific metadata) but will remain metadata and workflow structure — not regulatory decision engines.
7. Non-model infrastructure (embedding, vector storage, OCR, document processing) will prefer open-source components.
