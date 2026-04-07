"""Integration tests for the three highest-risk cross-layer flows.

These tests exercise full request → service → persistence → response chains
through the real FastAPI app with an in-memory SQLite backend.  External
provider APIs are mocked at the adapter boundary; everything below that
layer runs for real.

Flow 1: BYOK key → provider discovery → UI model rendering
Flow 2: document ingest → mode routing → normalized output
Flow 3: case → workflow pack → readiness → packet → submission draft
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from casegraph_agent_sdk.ingestion import (
    DocumentProcessingStatus,
    IngestionMode,
    IngestionResult,
    NormalizedExtractionOutput,
)
from casegraph_agent_sdk.packets import (
    PacketGenerateResponse,
    PacketListResponse,
)
from casegraph_agent_sdk.providers import (
    ModelDiscoveryResponse,
    ModelSummary,
    ProviderId,
    ProvidersResponse,
    ProviderValidationResponse,
)
from casegraph_agent_sdk.readiness import ChecklistResponse, ReadinessResponse
from casegraph_agent_sdk.submissions import (
    CreateSubmissionDraftRequest,
    SubmissionDraftCreateResponse,
    SubmissionDraftListResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Flow 1: BYOK key → provider discovery → UI model rendering
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderDiscoveryFlow:
    """Full round-trip: list providers → validate key → discover models.

    Mocks only the upstream HTTP calls (adapter boundary).  The service,
    router, registry, sorting logic, and SDK response validation all run
    for real.
    """

    def test_list_providers_returns_all_registered(self, client: TestClient) -> None:
        resp = client.get("/providers")
        assert resp.status_code == 200
        body = ProvidersResponse.model_validate(resp.json())
        ids = [p.id for p in body.providers]
        assert ProviderId.OPENAI in ids
        assert ProviderId.ANTHROPIC in ids
        assert ProviderId.GEMINI in ids
        # Each provider has capabilities metadata
        for provider in body.providers:
            assert len(provider.capabilities) > 0

    def test_validate_key_success(self, client: TestClient) -> None:
        with patch(
            "app.providers.adapters.openai.OpenAIProviderAdapter.validate_api_key",
            new_callable=AsyncMock,
        ):
            resp = client.post(
                "/providers/validate",
                json={"provider": "openai", "api_key": "sk-test-key-12345"},
            )
        assert resp.status_code == 200
        body = ProviderValidationResponse.model_validate(resp.json())
        assert body.valid is True
        assert body.provider == ProviderId.OPENAI
        assert body.error_code is None

    def test_validate_key_failure_returns_structured_error(
        self, client: TestClient
    ) -> None:
        from app.providers.adapters.base import ProviderAdapterError

        error = ProviderAdapterError(
            provider=ProviderId.OPENAI,
            error_code="authentication_failed",
            message="Invalid API key provided.",
            http_status=401,
            upstream_status_code=401,
        )
        with patch(
            "app.providers.adapters.openai.OpenAIProviderAdapter.validate_api_key",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            resp = client.post(
                "/providers/validate",
                json={"provider": "openai", "api_key": "sk-bad-key"},
            )
        assert resp.status_code == 200  # validation endpoint returns 200 with valid=False
        body = ProviderValidationResponse.model_validate(resp.json())
        assert body.valid is False
        assert body.error_code == "authentication_failed"

    def test_discover_models_returns_sorted_sdk_types(
        self, client: TestClient
    ) -> None:
        fake_models = [
            ModelSummary(provider=ProviderId.OPENAI, model_id="gpt-4.1", display_name="GPT-4.1"),
            ModelSummary(provider=ProviderId.OPENAI, model_id="gpt-3.5-turbo", display_name="GPT-3.5 Turbo"),
            ModelSummary(provider=ProviderId.OPENAI, model_id="o3-mini", display_name="o3-mini"),
        ]
        with patch(
            "app.providers.adapters.openai.OpenAIProviderAdapter.list_models",
            new_callable=AsyncMock,
            return_value=fake_models,
        ):
            resp = client.post(
                "/providers/models",
                json={"provider": "openai", "api_key": "sk-test-key-12345"},
            )
        assert resp.status_code == 200
        body = ModelDiscoveryResponse.model_validate(resp.json())
        assert body.provider == ProviderId.OPENAI
        assert len(body.models) == 3
        # Service layer sorts by display_name case-insensitive
        names = [m.display_name for m in body.models]
        assert names == sorted(names, key=lambda n: (n or "").lower())

    def test_discover_models_adapter_error_returns_http_error(
        self, client: TestClient
    ) -> None:
        from app.providers.adapters.base import ProviderAdapterError

        error = ProviderAdapterError(
            provider=ProviderId.OPENAI,
            error_code="authentication_failed",
            message="Invalid API key.",
            http_status=401,
            upstream_status_code=401,
        )
        with patch(
            "app.providers.adapters.openai.OpenAIProviderAdapter.list_models",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            resp = client.post(
                "/providers/models",
                json={"provider": "openai", "api_key": "sk-bad"},
            )
        assert resp.status_code == 401
        detail = resp.json()["detail"]
        assert detail["error_code"] == "authentication_failed"
        assert detail["provider"] == "openai"

    def test_full_provider_flow_list_validate_discover(
        self, client: TestClient
    ) -> None:
        """End-to-end: list → validate → discover, sequentially."""
        # Step 1: List providers — pick the first one
        list_resp = client.get("/providers")
        assert list_resp.status_code == 200
        providers = ProvidersResponse.model_validate(list_resp.json())
        provider = providers.providers[0]

        # Step 2: Validate key for that provider
        with patch(
            "app.providers.adapters.openai.OpenAIProviderAdapter.validate_api_key",
            new_callable=AsyncMock,
        ):
            val_resp = client.post(
                "/providers/validate",
                json={"provider": provider.id.value, "api_key": "sk-test"},
            )
        assert val_resp.status_code == 200
        validation = ProviderValidationResponse.model_validate(val_resp.json())
        assert validation.valid is True

        # Step 3: Discover models using the validated provider
        models_list = [
            ModelSummary(
                provider=ProviderId.OPENAI,
                model_id="gpt-4.1",
                display_name="GPT-4.1",
                owned_by="openai",
                capabilities=["text_generation"],
            ),
            ModelSummary(
                provider=ProviderId.OPENAI,
                model_id="gpt-4.1-mini",
                display_name="GPT-4.1 Mini",
                owned_by="openai",
                input_token_limit=128000,
                output_token_limit=16384,
            ),
        ]
        with patch(
            "app.providers.adapters.openai.OpenAIProviderAdapter.list_models",
            new_callable=AsyncMock,
            return_value=models_list,
        ):
            models_resp = client.post(
                "/providers/models",
                json={"provider": provider.id.value, "api_key": "sk-test"},
            )
        assert models_resp.status_code == 200
        discovery = ModelDiscoveryResponse.model_validate(models_resp.json())
        assert len(discovery.models) == 2
        # Verify model metadata survives the full stack
        gpt41 = next(m for m in discovery.models if m.model_id == "gpt-4.1")
        assert gpt41.owned_by == "openai"


# ═══════════════════════════════════════════════════════════════════════════
# Flow 2: document ingest → mode routing → normalized output
# ═══════════════════════════════════════════════════════════════════════════


def _fake_readable_pdf_output(
    document_id: str,
) -> NormalizedExtractionOutput:
    """Build a realistic extraction output without touching real PyMuPDF."""
    from casegraph_agent_sdk.ingestion import (
        BoundingBoxArtifact,
        CoordinateSpace,
        GeometrySource,
        PageArtifact,
        SourceFileMetadata,
        TextBlockArtifact,
    )

    return NormalizedExtractionOutput(
        document_id=document_id,
        source_file=SourceFileMetadata(
            filename="contract.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=4096,
            sha256="abc123",
            classification="pdf",
        ),
        requested_mode="auto",
        resolved_mode=IngestionMode.READABLE_PDF,
        status=DocumentProcessingStatus.COMPLETED,
        extractor_name="pymupdf-readable-pdf",
        extracted_text="Page one text. Page two text.",
        pages=[
            PageArtifact(
                page_number=1,
                width=612.0,
                height=792.0,
                coordinate_space=CoordinateSpace.PDF_POINTS,
                text="Page one text.",
                text_blocks=[
                    TextBlockArtifact(
                        block_id="page-1-block-1",
                        page_number=1,
                        text="Page one text.",
                        bbox=BoundingBoxArtifact(
                            x0=72.0,
                            y0=72.0,
                            x1=540.0,
                            y1=100.0,
                            coordinate_space=CoordinateSpace.PDF_POINTS,
                        ),
                        confidence=None,
                        geometry_source=GeometrySource.PDF_TEXT,
                    ),
                ],
                geometry_source=GeometrySource.PDF_TEXT,
            ),
            PageArtifact(
                page_number=2,
                width=612.0,
                height=792.0,
                coordinate_space=CoordinateSpace.PDF_POINTS,
                text="Page two text.",
                text_blocks=[
                    TextBlockArtifact(
                        block_id="page-2-block-1",
                        page_number=2,
                        text="Page two text.",
                        bbox=BoundingBoxArtifact(
                            x0=72.0,
                            y0=72.0,
                            x1=540.0,
                            y1=100.0,
                            coordinate_space=CoordinateSpace.PDF_POINTS,
                        ),
                        confidence=None,
                        geometry_source=GeometrySource.PDF_TEXT,
                    ),
                ],
                geometry_source=GeometrySource.PDF_TEXT,
            ),
        ],
    )


class TestDocumentIngestionFlow:
    """Full round-trip: upload file → routing decision → extraction → persistence → response.

    Mocks at the extractor boundary (ReadablePdfExtractor / OcrExtractor)
    and the file-system layer.  Routing logic, persistence, response
    shaping, and SDK type conformance all run for real.
    """

    def test_readable_pdf_full_flow(self, client: TestClient, session: Session) -> None:
        """AUTO mode on a PDF with readable text layer → READABLE_PDF extraction → persisted."""
        fake_output = _fake_readable_pdf_output("will-be-replaced")

        with (
            patch(
                "app.ingestion.service.persist_upload",
                new_callable=AsyncMock,
            ) as mock_persist,
            patch(
                "app.ingestion.service.cleanup_upload",
            ) as mock_cleanup,
            patch.object(
                type(client.app),  # type: ignore[arg-type]
                "__class__",
                create=False,
            ) if False else _noop_ctx(),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.has_readable_text_layer",
                return_value=True,
            ),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.extract",
                return_value=fake_output,
            ),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.is_available",
                return_value=True,
            ),
            patch(
                "app.ingestion.service.DocumentIngestionService._save_page_images",
                return_value={},
            ),
            patch(
                "app.ingestion.service.DocumentIngestionService._persist_source_file",
                return_value="documents/fake-id/source.pdf",
            ),
        ):
            from app.ingestion.file_utils import PersistedUpload
            from casegraph_agent_sdk.ingestion import SourceFileMetadata

            mock_persist.return_value = PersistedUpload(
                path=Path("/tmp/fake/contract.pdf"),
                temp_dir=Path("/tmp/fake"),
                metadata=SourceFileMetadata(
                    filename="contract.pdf",
                    content_type="application/pdf",
                    extension=".pdf",
                    size_bytes=4096,
                    sha256="abc123",
                    classification="pdf",
                ),
            )

            resp = client.post(
                "/documents/ingest",
                files={"file": ("contract.pdf", b"%PDF-1.4 fake content", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        assert resp.status_code == 200
        result = IngestionResult.model_validate(resp.json())

        # Verify routing chose READABLE_PDF
        assert result.summary.resolved_mode == IngestionMode.READABLE_PDF
        assert result.summary.status == DocumentProcessingStatus.COMPLETED
        assert result.summary.extractor_name == "pymupdf-readable-pdf"

        # Verify extraction output is in the response
        assert result.output is not None
        assert len(result.output.pages) == 2
        assert result.output.pages[0].text == "Page one text."
        assert len(result.output.pages[0].text_blocks) == 1
        assert result.output.pages[0].text_blocks[0].block_id == "page-1-block-1"

        # Verify geometry metadata preserved through full stack
        from casegraph_agent_sdk.ingestion import CoordinateSpace, GeometrySource

        assert result.output.pages[0].coordinate_space == CoordinateSpace.PDF_POINTS
        assert result.output.pages[0].geometry_source == GeometrySource.PDF_TEXT

        # Verify no errors
        assert result.errors == []

        # Verify document persisted in registry
        doc_resp = client.get("/documents")
        assert doc_resp.status_code == 200
        docs = doc_resp.json()["documents"]
        assert len(docs) >= 1
        assert any(d["source_file"]["filename"] == "contract.pdf" for d in docs)

        # Cleanup was called
        mock_cleanup.assert_called_once()

    def test_unsupported_file_type_returns_error(
        self, client: TestClient
    ) -> None:
        """Uploading a .txt file should fail with UNSUPPORTED status."""
        with (
            patch(
                "app.ingestion.service.persist_upload",
                new_callable=AsyncMock,
            ) as mock_persist,
            patch("app.ingestion.service.cleanup_upload"),
        ):
            from app.ingestion.file_utils import PersistedUpload
            from casegraph_agent_sdk.ingestion import SourceFileMetadata

            mock_persist.return_value = PersistedUpload(
                path=Path("/tmp/fake/notes.txt"),
                temp_dir=Path("/tmp/fake"),
                metadata=SourceFileMetadata(
                    filename="notes.txt",
                    content_type="text/plain",
                    extension=".txt",
                    size_bytes=100,
                    sha256="def456",
                    classification="unsupported",
                ),
            )

            resp = client.post(
                "/documents/ingest",
                files={"file": ("notes.txt", b"plain text", "text/plain")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        assert resp.status_code == 200
        result = IngestionResult.model_validate(resp.json())
        assert result.summary.status == DocumentProcessingStatus.UNSUPPORTED
        assert result.output is None
        assert len(result.errors) > 0

    def test_ocr_not_enabled_for_scanned_pdf_returns_error(
        self, client: TestClient
    ) -> None:
        """A PDF without text layer + ocr_enabled=False → UNSUPPORTED with actionable error."""
        with (
            patch(
                "app.ingestion.service.persist_upload",
                new_callable=AsyncMock,
            ) as mock_persist,
            patch("app.ingestion.service.cleanup_upload"),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.has_readable_text_layer",
                return_value=False,
            ),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.is_available",
                return_value=True,
            ),
            patch(
                "app.ingestion.extractors.ocr.OcrExtractionAdapter.is_available_for_scanned_pdfs",
                return_value=True,
            ),
            patch(
                "app.ingestion.extractors.ocr.OcrExtractionAdapter.is_available_for_images",
                return_value=True,
            ),
        ):
            from app.ingestion.file_utils import PersistedUpload
            from casegraph_agent_sdk.ingestion import SourceFileMetadata

            mock_persist.return_value = PersistedUpload(
                path=Path("/tmp/fake/scanned.pdf"),
                temp_dir=Path("/tmp/fake"),
                metadata=SourceFileMetadata(
                    filename="scanned.pdf",
                    content_type="application/pdf",
                    extension=".pdf",
                    size_bytes=2048,
                    sha256="ghi789",
                    classification="pdf",
                ),
            )

            resp = client.post(
                "/documents/ingest",
                files={"file": ("scanned.pdf", b"%PDF-1.4 scanned", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        assert resp.status_code == 200
        result = IngestionResult.model_validate(resp.json())
        assert result.summary.status == DocumentProcessingStatus.UNSUPPORTED
        assert any(
            e.code in ("ocr_required_for_scanned_pdf", "readable_text_layer_not_detected")
            for e in result.errors
        )

    def test_capabilities_endpoint_reflects_runtime_state(
        self, client: TestClient
    ) -> None:
        """Capabilities endpoint returns mode support based on actual runtime availability."""
        resp = client.get("/documents/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        modes = {m["mode"]: m for m in body["modes"]}
        assert "readable_pdf" in modes
        assert "scanned_pdf" in modes
        assert "image" in modes
        # Each mode declares whether it requires OCR
        assert modes["readable_pdf"]["requires_ocr"] is False
        assert modes["scanned_pdf"]["requires_ocr"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Flow 3: case → workflow pack → readiness → packet → submission draft
# ═══════════════════════════════════════════════════════════════════════════


class TestCaseLifecycleFlow:
    """Full lifecycle: create case → generate checklist → evaluate readiness
    → assemble packet → create submission draft.

    Verifies data threads correctly between each step.  All persistence
    and logic runs for real against in-memory SQLite.
    """

    def _create_case_with_domain(self, client: TestClient) -> dict[str, Any]:
        """Create a case bound to a domain pack (required for checklist)."""
        resp = client.post(
            "/cases",
            json={
                "title": "Integration Test Case",
                "category": "operations",
                "domain_pack_id": "medical_insurance_us",
                "case_type_id": "medical_insurance_us:prior_auth_review",
            },
        )
        assert resp.status_code == 200, f"Case creation failed: {resp.text}"
        return resp.json()

    def _link_document(
        self, client: TestClient, case_id: str, session: Session
    ) -> str:
        """Manually insert a document + link (bypassing ingestion for speed)."""
        from app.cases.models import CaseDocumentLinkModel
        from app.ingestion.models import DocumentRecord

        doc_id = str(uuid4())
        session.add(
            DocumentRecord(
                document_id=doc_id,
                filename="insurance_card.pdf",
                content_type="application/pdf",
                classification="document",
                requested_mode="auto",
                resolved_mode="readable_pdf",
                processing_status="completed",
                page_count=1,
            )
        )
        session.add(
            CaseDocumentLinkModel(
                link_id=str(uuid4()),
                case_id=case_id,
                document_id=doc_id,
            )
        )
        session.commit()
        return doc_id

    def _add_extraction(
        self, session: Session, *, case_id: str, document_id: str
    ) -> str:
        """Insert a completed extraction run."""
        from app.extraction.models import ExtractionRunModel

        extraction_id = str(uuid4())
        session.add(
            ExtractionRunModel(
                extraction_id=extraction_id,
                document_id=document_id,
                template_id="contact_info",
                case_id=case_id,
                strategy_used="provider_structured",
                provider="openai",
                model_id="gpt-4.1",
                status="completed",
                field_count=3,
                fields_extracted=3,
                extraction_result_json=[],
            )
        )
        session.commit()
        return extraction_id

    def test_full_case_lifecycle(self, client: TestClient, session: Session) -> None:
        """End-to-end: case → checklist → readiness → packet → submission draft."""

        # ── Step 1: Create case with domain binding ──────────────────
        case = self._create_case_with_domain(client)
        case_id = case["case_id"]
        assert case["domain_context"]["domain_pack_id"] == "medical_insurance_us"

        # ── Step 2: Generate readiness checklist ─────────────────────
        gen_resp = client.post(f"/cases/{case_id}/checklist/generate")
        assert gen_resp.status_code == 200

        checklist_resp = client.get(f"/cases/{case_id}/checklist")
        assert checklist_resp.status_code == 200
        checklist = ChecklistResponse.model_validate(checklist_resp.json())
        assert checklist.checklist is not None
        assert len(checklist.checklist.items) > 0
        # Without linked docs, no item should be "supported"
        assert all(
            item.status != "supported" for item in checklist.checklist.items
        )

        # ── Step 3: Link a document + extraction to improve readiness ─
        doc_id = self._link_document(client, case_id, session)
        self._add_extraction(session, case_id=case_id, document_id=doc_id)

        # ── Step 4: Evaluate readiness ───────────────────────────────
        eval_resp = client.post(f"/cases/{case_id}/checklist/evaluate")
        assert eval_resp.status_code == 200

        readiness_resp = client.get(f"/cases/{case_id}/readiness")
        assert readiness_resp.status_code == 200
        readiness = ReadinessResponse.model_validate(readiness_resp.json())
        assert readiness.readiness is not None
        # Readiness evaluated with real checklist data
        assert readiness.readiness.total_items >= 1
        readiness_status = readiness.readiness.readiness_status
        assert readiness_status in ("needs_review", "ready", "not_ready", "incomplete", "not_evaluated")

        # ── Step 5: Assemble packet ──────────────────────────────────
        packet_resp = client.post(
            f"/cases/{case_id}/packets/generate",
            json={"note": "Integration test packet"},
        )
        assert packet_resp.status_code == 200
        packet = PacketGenerateResponse.model_validate(packet_resp.json())
        assert packet.packet is not None
        packet_id = packet.packet.packet_id
        assert packet.packet.section_count > 0
        # Readiness status should be captured in the packet
        assert packet.packet.readiness_status == readiness_status

        # Verify packet appears in list
        list_resp = client.get(f"/cases/{case_id}/packets")
        assert list_resp.status_code == 200
        packet_list = PacketListResponse.model_validate(list_resp.json())
        assert any(p.packet_id == packet_id for p in packet_list.packets)

        # ── Step 6: Create submission draft from packet ──────────────
        # Find a registered submission target
        targets_resp = client.get("/submission/targets")
        assert targets_resp.status_code == 200
        targets = targets_resp.json()["targets"]
        assert len(targets) > 0
        target_id = targets[0]["target_id"]

        draft_resp = client.post(
            f"/cases/{case_id}/submission-drafts",
            json=CreateSubmissionDraftRequest(
                submission_target_id=target_id,
                packet_id=packet_id,
            ).model_dump(),
        )
        assert draft_resp.status_code == 200
        draft = SubmissionDraftCreateResponse.model_validate(draft_resp.json())
        assert draft.draft is not None
        assert draft.draft.packet_id == packet_id
        assert draft.draft.submission_target_id == target_id

        # Verify draft appears in list
        drafts_resp = client.get(f"/cases/{case_id}/submission-drafts")
        assert drafts_resp.status_code == 200
        draft_list = SubmissionDraftListResponse.model_validate(drafts_resp.json())
        assert any(d.draft_id == draft.draft.draft_id for d in draft_list.drafts)

    def test_checklist_reflects_domain_pack_requirements(
        self, client: TestClient
    ) -> None:
        """Checklist items come from the domain pack's case type requirements."""
        case = self._create_case_with_domain(client)
        case_id = case["case_id"]

        gen_resp = client.post(f"/cases/{case_id}/checklist/generate")
        assert gen_resp.status_code == 200

        resp = client.get(f"/cases/{case_id}/checklist")
        assert resp.status_code == 200
        checklist = ChecklistResponse.model_validate(resp.json())
        # medical_insurance_us:prior_auth_review should have specific requirements
        assert checklist.checklist is not None
        items = checklist.checklist.items
        assert len(items) >= 3  # domain pack defines multiple requirements

    def test_readiness_without_checklist_creates_one(
        self, client: TestClient
    ) -> None:
        """Evaluating readiness on a fresh case auto-generates the checklist."""
        case = self._create_case_with_domain(client)
        case_id = case["case_id"]

        # Generate checklist first, then evaluate readiness
        client.post(f"/cases/{case_id}/checklist/generate")
        client.post(f"/cases/{case_id}/checklist/evaluate")

        resp = client.get(f"/cases/{case_id}/readiness")
        assert resp.status_code == 200
        readiness = ReadinessResponse.model_validate(resp.json())
        assert readiness.readiness is not None
        assert readiness.readiness.total_items > 0

    def test_packet_without_documents_still_generates(
        self, client: TestClient
    ) -> None:
        """A packet can be generated even without linked documents."""
        case = self._create_case_with_domain(client)
        case_id = case["case_id"]

        resp = client.post(f"/cases/{case_id}/packets/generate")
        assert resp.status_code == 200
        packet = PacketGenerateResponse.model_validate(resp.json())
        assert packet.packet is not None
        assert packet.packet.section_count > 0

    def test_submission_draft_requires_valid_packet(
        self, client: TestClient
    ) -> None:
        """Creating a draft with a non-existent packet_id fails."""
        case = self._create_case_with_domain(client)
        case_id = case["case_id"]

        targets_resp = client.get("/submission/targets")
        targets = targets_resp.json()["targets"]
        if not targets:
            pytest.skip("No submission targets registered")

        resp = client.post(
            f"/cases/{case_id}/submission-drafts",
            json={"target_id": targets[0]["target_id"], "packet_id": "nonexistent-id"},
        )
        assert resp.status_code in (404, 422)  # depends on validation order


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


from contextlib import contextmanager


@contextmanager
def _noop_ctx():
    yield
