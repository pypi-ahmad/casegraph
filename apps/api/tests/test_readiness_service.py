"""Tests for the readiness / checklist foundation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.readiness import (
    ChecklistResponse,
    ReadinessResponse,
    UpdateChecklistItemRequest,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.readiness.models import (
    ChecklistItemModel,
    ChecklistModel,
)
from app.readiness.service import ReadinessService, ReadinessServiceError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _create_domain_case(session: Session, *, case_id: str | None = None) -> CaseRecordModel:
    """Insert a case scoped to the medical_us domain pack."""
    cid = case_id or str(uuid4())
    case = CaseRecordModel(
        case_id=cid,
        title="Test Medical Case",
        category="medical",
        domain_pack_id="medical_us",
        case_type_id="medical_us:record_review",
        jurisdiction="us",
        domain_category="medical",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _create_plain_case(session: Session) -> CaseRecordModel:
    """Insert a case without domain pack binding."""
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Generic Case",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(
    session: Session,
    *,
    case_id: str,
    doc_id: str | None = None,
    filename: str = "report.pdf",
    content_type: str = "application/pdf",
) -> DocumentRecord:
    """Insert a document record and link it to the case."""
    did = doc_id or str(uuid4())
    doc = DocumentRecord(
        document_id=did,
        filename=filename,
        content_type=content_type,
        classification="document",
        requested_mode="auto",
        resolved_mode="auto",
        processing_status="completed",
    )
    session.add(doc)
    link = CaseDocumentLinkModel(
        link_id=str(uuid4()),
        case_id=case_id,
        document_id=did,
    )
    session.add(link)
    session.commit()
    return doc


def _add_extraction(
    session: Session,
    *,
    case_id: str,
    document_id: str,
    template_id: str = "tmpl-1",
    status: str = "completed",
    fields_extracted: int = 5,
) -> ExtractionRunModel:
    """Insert an extraction run record."""
    run = ExtractionRunModel(
        extraction_id=str(uuid4()),
        document_id=document_id,
        template_id=template_id,
        case_id=case_id,
        strategy_used="llm",
        status=status,
        fields_extracted=fields_extracted,
        grounding_available=True,
    )
    session.add(run)
    session.commit()
    return run


# ---------------------------------------------------------------------------
# Checklist generation
# ---------------------------------------------------------------------------

class TestGenerateChecklist:
    def test_generates_checklist_from_domain_pack(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)

        result = svc.generate_checklist(case.case_id)

        assert isinstance(result, ChecklistResponse)
        checklist = result.checklist
        assert checklist.case_id == case.case_id
        assert checklist.generation.domain_pack_id == "medical_us"
        assert checklist.generation.case_type_id == "medical_us:record_review"
        assert checklist.generation.requirement_count > 0
        assert len(checklist.items) == checklist.generation.requirement_count

    def test_items_have_correct_initial_status(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)

        result = svc.generate_checklist(case.case_id)

        for item in result.checklist.items:
            if item.priority == "optional":
                assert item.status == "optional_unfilled"
            else:
                assert item.status == "missing"

    def test_rejects_non_domain_case(self, session: Session) -> None:
        case = _create_plain_case(session)
        svc = ReadinessService(session)

        with pytest.raises(ReadinessServiceError, match="domain pack"):
            svc.generate_checklist(case.case_id)

    def test_rejects_unknown_case(self, session: Session) -> None:
        svc = ReadinessService(session)
        with pytest.raises(ReadinessServiceError, match="not found"):
            svc.generate_checklist("nonexistent")

    def test_returns_existing_without_force(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)

        first = svc.generate_checklist(case.case_id)
        second = svc.generate_checklist(case.case_id)

        assert first.checklist.checklist_id == second.checklist.checklist_id

    def test_force_regenerates_new_checklist(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)

        first = svc.generate_checklist(case.case_id)
        second = svc.generate_checklist(case.case_id, force=True)

        assert first.checklist.checklist_id != second.checklist.checklist_id
        assert len(second.checklist.items) > 0

        # Old checklist should be gone.
        old = session.get(ChecklistModel, first.checklist.checklist_id)
        assert old is None

    def test_persists_checklist_items(self, session: Session) -> None:
        from sqlmodel import select

        case = _create_domain_case(session)
        svc = ReadinessService(session)

        result = svc.generate_checklist(case.case_id)
        checklist_id = result.checklist.checklist_id

        items_in_db = list(session.exec(
            select(ChecklistItemModel).where(
                ChecklistItemModel.checklist_id == checklist_id
            )
        ).all())
        assert len(items_in_db) == result.checklist.generation.requirement_count


# ---------------------------------------------------------------------------
# Get checklist
# ---------------------------------------------------------------------------

class TestGetChecklist:
    def test_returns_none_when_no_checklist(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        assert svc.get_checklist(case.case_id) is None

    def test_returns_existing_checklist(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        result = svc.get_checklist(case.case_id)

        assert result is not None
        assert result.checklist.case_id == case.case_id


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_evaluate_with_no_documents_all_missing(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        result = svc.evaluate(case.case_id)

        assert isinstance(result, ReadinessResponse)
        assert result.readiness.readiness_status == "incomplete"
        assert result.readiness.missing_items > 0
        assert result.readiness.supported_items == 0

    def test_evaluate_raises_without_checklist(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)

        with pytest.raises(ReadinessServiceError, match="No checklist"):
            svc.evaluate(case.case_id)

    def test_evaluate_links_matching_documents(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        # Add a document with "identity" in filename to match identity category.
        _add_document(session, case_id=case.case_id, filename="patient_identity_card.pdf")

        result = svc.evaluate(case.case_id)

        # Find the identity requirement item.
        identity_items = [
            i for i in result.readiness.missing_required
            if "identity" in i.display_name.lower()
        ]
        # At least the items with documents should not be missing anymore.
        assert result.readiness.partially_supported_items > 0 or result.readiness.supported_items > 0

    def test_evaluate_with_document_and_extraction_gives_supported(
        self, session: Session,
    ) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        doc = _add_document(
            session, case_id=case.case_id, filename="patient_identity_scan.pdf",
        )
        _add_extraction(
            session, case_id=case.case_id, document_id=doc.document_id,
        )

        result = svc.evaluate(case.case_id)
        assert result.readiness.supported_items >= 1

    def test_evaluate_only_extraction_without_doc_link_gives_needs_review(
        self, session: Session,
    ) -> None:
        """Extraction-only support is explicit and requires human review."""
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        # Add a document but DON'T link it to case. Add an extraction.
        did = str(uuid4())
        doc = DocumentRecord(
            document_id=did,
            filename="identity_form.pdf",
            content_type="application/pdf",
            classification="document",
            requested_mode="auto",
            resolved_mode="auto",
            processing_status="completed",
        )
        session.add(doc)
        run = ExtractionRunModel(
            extraction_id=str(uuid4()),
            document_id=did,
            template_id="tmpl-1",
            case_id=case.case_id,
            strategy_used="llm",
            status="completed",
            fields_extracted=3,
            grounding_available=False,
        )
        session.add(run)
        session.commit()

        result = svc.evaluate(case.case_id)
        assert result.readiness.needs_review_items >= 1

    def test_all_required_partial_support_requires_review_status(
        self, session: Session,
    ) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        _add_document(
            session,
            case_id=case.case_id,
            filename="patient_identity_card.pdf",
        )
        _add_document(
            session,
            case_id=case.case_id,
            filename="clinical_notes_20240101.pdf",
        )

        result = svc.evaluate(case.case_id)

        assert result.readiness.partially_supported_items >= 2
        assert result.readiness.readiness_status == "needs_review"

    def test_evaluate_incomplete_extraction_ignored(
        self, session: Session,
    ) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        doc = _add_document(
            session, case_id=case.case_id, filename="identity_card.pdf",
        )
        _add_extraction(
            session,
            case_id=case.case_id,
            document_id=doc.document_id,
            status="failed",
        )

        result = svc.evaluate(case.case_id)
        # Failed extraction should be ignored, so item should be
        # partially_supported (doc linked) not supported (both linked).
        assert result.readiness.partially_supported_items >= 1

    def test_readiness_counts_are_consistent(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)
        result = svc.evaluate(case.case_id)

        r = result.readiness
        total_counted = (
            r.supported_items
            + r.partially_supported_items
            + r.missing_items
            + r.needs_review_items
            + r.optional_unfilled_items
            + r.waived_items
        )
        assert total_counted == r.total_items

    def test_evaluate_idempotent(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        first = svc.evaluate(case.case_id)
        second = svc.evaluate(case.case_id)

        assert first.readiness.readiness_status == second.readiness.readiness_status
        assert first.readiness.missing_items == second.readiness.missing_items


# ---------------------------------------------------------------------------
# Item update
# ---------------------------------------------------------------------------

class TestUpdateItem:
    def test_update_operator_notes(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        result = svc.generate_checklist(case.case_id)
        item_id = result.checklist.items[0].item_id

        updated = svc.update_item(
            case.case_id,
            item_id,
            UpdateChecklistItemRequest(operator_notes="Verified by phone"),
        )

        assert updated.operator_notes == "Verified by phone"

    def test_update_status_override(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        result = svc.generate_checklist(case.case_id)
        item_id = result.checklist.items[0].item_id

        updated = svc.update_item(
            case.case_id,
            item_id,
            UpdateChecklistItemRequest(status_override="waived"),
        )

        assert updated.status == "waived"

    def test_update_rejects_manual_supported_override(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        result = svc.generate_checklist(case.case_id)
        item_id = result.checklist.items[0].item_id

        with pytest.raises(ReadinessServiceError, match="cannot mark an item as supported"):
            svc.update_item(
                case.case_id,
                item_id,
                UpdateChecklistItemRequest(status_override="supported"),
            )

    def test_update_nonexistent_item_raises(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)

        with pytest.raises(ReadinessServiceError, match="not found"):
            svc.update_item(
                case.case_id,
                "nonexistent",
                UpdateChecklistItemRequest(operator_notes="x"),
            )

    def test_update_item_wrong_case_raises(self, session: Session) -> None:
        case1 = _create_domain_case(session)
        case2 = _create_domain_case(session)
        svc = ReadinessService(session)

        result = svc.generate_checklist(case1.case_id)
        svc.generate_checklist(case2.case_id)
        item_id = result.checklist.items[0].item_id

        with pytest.raises(ReadinessServiceError, match="does not belong"):
            svc.update_item(
                case2.case_id,
                item_id,
                UpdateChecklistItemRequest(operator_notes="x"),
            )


# ---------------------------------------------------------------------------
# Readiness summary (read-only)
# ---------------------------------------------------------------------------

class TestGetReadiness:
    def test_returns_none_without_checklist(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        assert svc.get_readiness(case.case_id) is None

    def test_returns_not_evaluated_after_generate(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)

        result = svc.get_readiness(case.case_id)

        assert result is not None
        assert result.readiness.readiness_status == "not_evaluated"
        assert result.readiness.evaluated_at == ""

    def test_returns_data_after_evaluate(self, session: Session) -> None:
        case = _create_domain_case(session)
        svc = ReadinessService(session)
        svc.generate_checklist(case.case_id)
        svc.evaluate(case.case_id)

        result = svc.get_readiness(case.case_id)

        assert result is not None
        assert result.readiness.case_id == case.case_id
        assert result.readiness.total_items > 0


# ---------------------------------------------------------------------------
# Document matching heuristic
# ---------------------------------------------------------------------------

class TestDocumentMatchesCategory:
    @pytest.mark.parametrize(
        "filename,category,expected",
        [
            ("patient_identity_card.pdf", "identity", True),
            ("passport_scan.jpg", "identity", True),
            ("paid_invoice.pdf", "identity", False),
            ("clinical_notes_20240101.pdf", "clinical_notes", True),
            ("lab_report.pdf", "diagnostic_report", True),
            ("referral_letter.pdf", "referral_order", True),
            ("random_file.pdf", "identity", False),
            ("photo.jpg", "clinical_notes", False),
            ("invoice_summary.pdf", "invoice_bill", True),
            ("policy_document.pdf", "policy_document", True),
            ("w2_2024.pdf", "income_document", True),
        ],
    )
    def test_filename_matching(
        self, filename: str, category: str, expected: bool,
    ) -> None:
        doc = DocumentRecord(
            document_id="test",
            filename=filename,
            content_type="application/pdf",
            classification="document",
            requested_mode="auto",
            resolved_mode="auto",
            processing_status="completed",
        )
        assert ReadinessService._document_matches_category(doc, category) is expected

    def test_empty_keywords_category_returns_false(self) -> None:
        doc = DocumentRecord(
            document_id="test",
            filename="anything.pdf",
            content_type="application/pdf",
            classification="document",
            requested_mode="auto",
            resolved_mode="auto",
            processing_status="completed",
        )
        assert ReadinessService._document_matches_category(doc, "other") is False
        assert ReadinessService._document_matches_category(doc, "supporting_attachment") is False


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------

class TestDeriveStatus:
    def test_no_evidence_required_gives_missing(self) -> None:
        item = ChecklistItemModel(
            item_id="i1", checklist_id="c1", requirement_id="r1",
            display_name="Test", document_category="identity", priority="required",
        )
        assert ReadinessService._derive_status(item, 0, 0) == "missing"

    def test_no_evidence_optional_gives_optional_unfilled(self) -> None:
        item = ChecklistItemModel(
            item_id="i1", checklist_id="c1", requirement_id="r1",
            display_name="Test", document_category="identity", priority="optional",
        )
        assert ReadinessService._derive_status(item, 0, 0) == "optional_unfilled"

    def test_doc_only_gives_partially_supported(self) -> None:
        item = ChecklistItemModel(
            item_id="i1", checklist_id="c1", requirement_id="r1",
            display_name="Test", document_category="identity", priority="required",
        )
        assert ReadinessService._derive_status(item, 1, 0) == "partially_supported"

    def test_both_doc_and_extraction_gives_supported(self) -> None:
        item = ChecklistItemModel(
            item_id="i1", checklist_id="c1", requirement_id="r1",
            display_name="Test", document_category="identity", priority="required",
        )
        assert ReadinessService._derive_status(item, 2, 1) == "supported"

    def test_extraction_only_gives_needs_review(self) -> None:
        item = ChecklistItemModel(
            item_id="i1", checklist_id="c1", requirement_id="r1",
            display_name="Test", document_category="identity", priority="required",
        )
        assert ReadinessService._derive_status(item, 0, 1) == "needs_human_review"


# ---------------------------------------------------------------------------
# API endpoint tests (TestClient)
# ---------------------------------------------------------------------------

class TestReadinessAPI:
    @pytest.fixture()
    def client(self):
        from sqlalchemy.pool import StaticPool

        from fastapi import FastAPI
        from fastapi.testclient import TestClient as TC

        from app.readiness.router import router
        from app.persistence.database import get_session

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)

        def override_session():
            with Session(engine) as session:
                yield session

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = override_session

        # Seed a domain case.
        with Session(engine) as seed:
            case = CaseRecordModel(
                case_id="api-test-case",
                title="API Test Case",
                domain_pack_id="medical_us",
                case_type_id="medical_us:record_review",
                jurisdiction="us",
                domain_category="medical",
            )
            seed.add(case)
            seed.commit()

        with TC(app) as c:
            c.case_id = "api-test-case"  # type: ignore[attr-defined]
            yield c

    def test_get_checklist_404_when_none(self, client) -> None:
        resp = client.get(f"/cases/{client.case_id}/checklist")
        assert resp.status_code == 404

    def test_generate_and_get_checklist(self, client) -> None:
        resp = client.post(f"/cases/{client.case_id}/checklist/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert "checklist" in data
        assert data["checklist"]["case_id"] == client.case_id
        assert len(data["checklist"]["items"]) > 0

        # GET should return the same checklist.
        resp2 = client.get(f"/cases/{client.case_id}/checklist")
        assert resp2.status_code == 200
        assert resp2.json()["checklist"]["checklist_id"] == data["checklist"]["checklist_id"]

    def test_evaluate_returns_readiness(self, client) -> None:
        client.post(f"/cases/{client.case_id}/checklist/generate")
        resp = client.post(f"/cases/{client.case_id}/checklist/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert "readiness" in data
        assert data["readiness"]["readiness_status"] in [
            "not_evaluated", "incomplete", "needs_review", "ready",
        ]

    def test_get_readiness_404_without_checklist(self, client) -> None:
        resp = client.get(f"/cases/{client.case_id}/readiness")
        assert resp.status_code == 404

    def test_patch_item(self, client) -> None:
        resp = client.post(f"/cases/{client.case_id}/checklist/generate")
        item_id = resp.json()["checklist"]["items"][0]["item_id"]

        resp2 = client.patch(
            f"/cases/{client.case_id}/checklist/items/{item_id}",
            json={"operator_notes": "Checked manually"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["operator_notes"] == "Checked manually"

    def test_force_regenerate(self, client) -> None:
        resp1 = client.post(f"/cases/{client.case_id}/checklist/generate")
        cid1 = resp1.json()["checklist"]["checklist_id"]

        resp2 = client.post(
            f"/cases/{client.case_id}/checklist/generate",
            json={"force": True},
        )
        cid2 = resp2.json()["checklist"]["checklist_id"]
        assert cid1 != cid2

    def test_generate_for_nonexistent_case(self, client) -> None:
        resp = client.post("/cases/nope/checklist/generate")
        assert resp.status_code == 404
