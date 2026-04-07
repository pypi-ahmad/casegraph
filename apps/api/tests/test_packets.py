"""Tests for the packet assembly and export foundation."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel, WorkflowRunRecordModel
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.operator_review.models import ActionItemModel, ReviewNoteModel
from app.packets.errors import PacketServiceError
from app.packets.router import router as packets_router
from app.packets.service import PacketAssemblyService
from app.persistence.database import get_session
from app.readiness.service import ReadinessService


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _create_case(
    session: Session,
    *,
    domain: bool = False,
    workflow_id: str | None = None,
    current_stage: str = "intake",
) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Packet Test Case",
        category="operations",
        selected_workflow_id=workflow_id,
        current_stage=current_stage,
        domain_pack_id="medical_us" if domain else None,
        case_type_id="medical_us:record_review" if domain else None,
        jurisdiction="us" if domain else None,
        domain_category="medical" if domain else None,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(
    session: Session,
    *,
    case_id: str,
    filename: str = "report.pdf",
) -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename=filename,
        content_type="application/pdf",
        classification="document",
        requested_mode="auto",
        resolved_mode="auto",
        processing_status="completed",
        page_count=3,
    )
    session.add(document)
    session.add(CaseDocumentLinkModel(
        link_id=str(uuid4()),
        case_id=case_id,
        document_id=document.document_id,
    ))
    session.commit()
    return document


def _add_extraction(
    session: Session,
    *,
    case_id: str,
    document_id: str,
    status: str = "completed",
) -> ExtractionRunModel:
    extraction = ExtractionRunModel(
        extraction_id=str(uuid4()),
        document_id=document_id,
        template_id="template-1",
        case_id=case_id,
        strategy_used="provider_structured",
        provider="openai",
        model_id="gpt-4",
        status=status,
        field_count=5,
        fields_extracted=4,
        grounding_available=True,
    )
    session.add(extraction)
    session.commit()
    return extraction


def _add_workflow_run(
    session: Session,
    *,
    case_id: str,
    status: str = "completed",
) -> WorkflowRunRecordModel:
    run = WorkflowRunRecordModel(
        run_id=str(uuid4()),
        case_id=case_id,
        workflow_id="provider-task-execution",
        status=status,
    )
    session.add(run)
    session.commit()
    return run


def _add_review_note(
    session: Session,
    *,
    case_id: str,
    body: str = "Test note",
) -> ReviewNoteModel:
    note = ReviewNoteModel(
        note_id=str(uuid4()),
        case_id=case_id,
        body=body,
        decision="note_only",
        stage_snapshot="intake",
    )
    session.add(note)
    session.commit()
    return note


def _add_open_action(
    session: Session,
    *,
    case_id: str,
) -> ActionItemModel:
    action = ActionItemModel(
        action_item_id=str(uuid4()),
        case_id=case_id,
        fingerprint=f"test:{uuid4()}",
        category="missing_document",
        source="case",
        priority="high",
        status="open",
        title="Test action",
        description="Test action description",
        source_reason="Test reason",
    )
    session.add(action)
    session.commit()
    return action


class TestPacketAssemblyService:
    def test_generate_packet_minimal_case(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        assert result.result.success is True
        assert result.packet is not None
        assert result.packet.case_id == case.case_id
        assert result.packet.section_count == 9
        assert result.packet.artifact_count == 2
        assert len(result.artifacts) == 2

    def test_generate_packet_with_documents(self, session: Session) -> None:
        case = _create_case(session)
        _add_document(session, case_id=case.case_id, filename="medical_record.pdf")
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        manifest = detail.manifest
        docs_section = next(s for s in manifest.sections if s.section_type == "linked_documents")
        assert docs_section.item_count == 1
        assert docs_section.empty is False
        assert manifest.linked_document_count == 1

    def test_generate_packet_with_extractions(self, session: Session) -> None:
        case = _create_case(session)
        doc = _add_document(session, case_id=case.case_id)
        _add_extraction(session, case_id=case.case_id, document_id=doc.document_id)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        assert detail.manifest.extraction_count == 1
        ext_section = next(s for s in detail.manifest.sections if s.section_type == "extraction_results")
        assert ext_section.item_count == 1

    def test_generate_packet_with_run_history(self, session: Session) -> None:
        case = _create_case(session)
        _add_workflow_run(session, case_id=case.case_id, status="completed")
        _add_workflow_run(session, case_id=case.case_id, status="failed")
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        assert detail.manifest.run_count == 2
        run_section = next(s for s in detail.manifest.sections if s.section_type == "run_history")
        assert run_section.item_count == 2

    def test_generate_packet_with_actions_and_notes(self, session: Session) -> None:
        case = _create_case(session)
        _add_open_action(session, case_id=case.case_id)
        _add_review_note(session, case_id=case.case_id, body="Operator observed gap")
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        assert detail.manifest.open_action_count == 1
        assert detail.manifest.review_note_count == 1

    def test_generate_packet_includes_note(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id, note="For external review")

        assert result.packet.note == "For external review"
        detail = service.get_packet(result.packet.packet_id)
        assert detail.manifest.note == "For external review"

    def test_empty_sections_marked_honestly(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        docs_section = next(s for s in detail.manifest.sections if s.section_type == "linked_documents")
        assert docs_section.empty is True
        assert docs_section.item_count == 0

    def test_domain_metadata_section_populated(self, session: Session) -> None:
        case = _create_case(session, domain=True)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        domain_section = next(s for s in detail.manifest.sections if s.section_type == "domain_metadata")
        assert domain_section.empty is False
        assert domain_section.data["domain_pack_id"] == "medical_us"

    def test_domain_metadata_section_empty_without_domain(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        domain_section = next(s for s in detail.manifest.sections if s.section_type == "domain_metadata")
        assert domain_section.empty is True

    def test_list_packets(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        service.generate_packet(case.case_id, note="First")
        service.generate_packet(case.case_id, note="Second")

        packet_list = service.list_packets(case.case_id)
        assert len(packet_list.packets) == 2
        assert packet_list.packets[0].note == "Second"
        assert packet_list.packets[1].note == "First"

    def test_list_artifacts(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        artifacts = service.list_artifacts(result.packet.packet_id)
        assert len(artifacts.artifacts) == 2
        assert [a.format for a in artifacts.artifacts] == [
            "json_manifest",
            "markdown_summary",
        ]

    def test_download_artifact_content(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        json_artifact = next(a for a in result.artifacts if a.format == "json_manifest")
        _model, content = service.get_artifact_content(
            result.packet.packet_id,
            json_artifact.artifact_id,
        )
        assert len(content) > 0
        assert '"packet_id"' in content

    def test_markdown_artifact_contains_disclaimer(self, session: Session) -> None:
        case = _create_case(session)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        md_artifact = next(a for a in result.artifacts if a.format == "markdown_summary")
        _model, content = service.get_artifact_content(
            result.packet.packet_id,
            md_artifact.artifact_id,
        )
        assert "does not constitute" in content
        assert "regulatory filing" in content

    def test_nonexistent_case_raises(self, session: Session) -> None:
        service = PacketAssemblyService(session)
        with pytest.raises(PacketServiceError, match="not found"):
            service.generate_packet("nonexistent")

    def test_nonexistent_packet_raises(self, session: Session) -> None:
        service = PacketAssemblyService(session)
        with pytest.raises(PacketServiceError, match="not found"):
            service.get_packet("nonexistent")

    def test_readiness_section_for_domain_case(self, session: Session) -> None:
        case = _create_case(session, domain=True)
        readiness = ReadinessService(session)
        readiness.generate_checklist(case.case_id)
        readiness.evaluate(case.case_id)
        service = PacketAssemblyService(session)
        result = service.generate_packet(case.case_id)

        detail = service.get_packet(result.packet.packet_id)
        rs_section = next(s for s in detail.manifest.sections if s.section_type == "readiness_summary")
        assert rs_section.empty is False
        assert rs_section.data["checklist_available"] is True
        assert "readiness_status" in rs_section.data


class TestPacketAPI:
    @pytest.fixture()
    def client(self) -> TestClient:
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
        app.include_router(packets_router)
        app.dependency_overrides[get_session] = override_session

        with Session(engine) as seed:
            case = CaseRecordModel(
                case_id="packet-api-case",
                title="Packet API Test Case",
            )
            seed.add(case)
            seed.commit()

        with TestClient(app) as client:
            client.case_id = "packet-api-case"  # type: ignore[attr-defined]
            yield client

    def test_generate_and_list_packets(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        response = client.post(f"/cases/{case_id}/packets/generate", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["success"] is True
        assert data["packet"] is not None

        list_response = client.get(f"/cases/{case_id}/packets")
        assert list_response.status_code == 200
        assert len(list_response.json()["packets"]) == 1

    def test_get_packet_detail(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        gen = client.post(f"/cases/{case_id}/packets/generate", json={})
        packet_id = gen.json()["packet"]["packet_id"]

        detail = client.get(f"/packets/{packet_id}")
        assert detail.status_code == 200
        assert detail.json()["manifest"]["case_id"] == case_id
        assert len(detail.json()["manifest"]["sections"]) == 9

    def test_get_manifest(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        gen = client.post(f"/cases/{case_id}/packets/generate", json={})
        packet_id = gen.json()["packet"]["packet_id"]

        manifest = client.get(f"/packets/{packet_id}/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["manifest"]["packet_id"] == packet_id

    def test_list_and_download_artifacts(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        gen = client.post(f"/cases/{case_id}/packets/generate", json={})
        packet_id = gen.json()["packet"]["packet_id"]

        artifacts = client.get(f"/packets/{packet_id}/artifacts")
        assert artifacts.status_code == 200
        arts = artifacts.json()["artifacts"]
        assert len(arts) == 2

        for art in arts:
            download = client.get(f"/packets/{packet_id}/download/{art['artifact_id']}")
            assert download.status_code == 200
            assert len(download.text) > 0

    def test_generate_for_nonexistent_case_returns_404(self, client: TestClient) -> None:
        response = client.post("/cases/nonexistent/packets/generate", json={})
        assert response.status_code == 404

    def test_get_nonexistent_packet_returns_404(self, client: TestClient) -> None:
        response = client.get("/packets/nonexistent")
        assert response.status_code == 404
