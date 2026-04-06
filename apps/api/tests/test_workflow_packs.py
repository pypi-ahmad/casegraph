"""Tests for domain workflow-pack orchestration."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.workflow_packs import WorkflowPackExecutionRequest, WorkflowPackStageResult

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.ingestion.models import DocumentRecord
from app.persistence.database import get_session
from app.workflow_packs.registry import get_workflow_pack_registry
from app.workflow_packs.router import router as workflow_packs_router
from app.workflow_packs.service import WorkflowPackOrchestrationService


@pytest.fixture()
def session() -> Session:
    import app.cases.models  # noqa: F401
    import app.extraction.models  # noqa: F401
    import app.ingestion.models  # noqa: F401
    import app.operator_review.models  # noqa: F401
    import app.packets.models  # noqa: F401
    import app.readiness.models  # noqa: F401
    import app.submissions.models  # noqa: F401
    import app.workflow_packs.models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture()
def client(session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(workflow_packs_router)

    def _get_session() -> Session:
        return session

    app.dependency_overrides[get_session] = _get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_case(
    session: Session,
    *,
    domain_pack_id: str = "medical_insurance_us",
    case_type_id: str = "medical_insurance_us:prior_auth_review",
    domain_category: str = "medical_insurance",
    jurisdiction: str = "us",
) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Workflow Pack Test Case",
        category="operations",
        status="open",
        summary="Workflow pack verification case",
        current_stage="intake",
        domain_pack_id=domain_pack_id,
        case_type_id=case_type_id,
        jurisdiction=jurisdiction,
        domain_category=domain_category,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(session: Session, *, case_id: str, filename: str = "packet.pdf") -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename=filename,
        content_type="application/pdf",
        classification="document",
        requested_mode="auto",
        resolved_mode="auto",
        processing_status="completed",
        page_count=2,
    )
    session.add(document)
    session.add(
        CaseDocumentLinkModel(
            link_id=str(uuid4()),
            case_id=case_id,
            document_id=document.document_id,
        )
    )
    session.commit()
    session.refresh(document)
    return document


def test_registry_exposes_real_prior_auth_and_pre_claim_packs() -> None:
    registry = get_workflow_pack_registry()

    packs = {pack.metadata.workflow_pack_id: pack for pack in registry.list_packs()}

    assert {"prior_auth_packet_review", "pre_claim_packet_review"}.issubset(packs)
    assert packs["prior_auth_packet_review"].metadata.domain_pack_id == "medical_insurance_us"
    assert packs["pre_claim_packet_review"].metadata.domain_pack_id == "medical_insurance_india"
    assert packs["prior_auth_packet_review"].stages[1].display_name == "Extraction Coverage Review"


def test_registry_exposes_insurance_claim_intake_and_coverage_packs() -> None:
    registry = get_workflow_pack_registry()

    packs = {pack.metadata.workflow_pack_id: pack for pack in registry.list_packs()}

    assert "insurance_claim_intake_review" in packs
    assert "insurance_claim_intake_review_india" in packs
    assert "coverage_correspondence_review" in packs
    assert "coverage_correspondence_review_india" in packs

    us_pack = packs["insurance_claim_intake_review"]
    assert us_pack.metadata.domain_pack_id == "insurance_us"
    assert us_pack.metadata.domain_category == "insurance"
    assert us_pack.metadata.jurisdiction == "us"
    assert "insurance_us:policy_review" in us_pack.metadata.compatible_case_type_ids
    assert "insurance_us:coverage_review" in us_pack.metadata.compatible_case_type_ids
    assert len(us_pack.stages) == 7

    india_coverage = packs["coverage_correspondence_review_india"]
    assert india_coverage.metadata.domain_pack_id == "insurance_india"
    assert "insurance_india:coverage_review" in india_coverage.metadata.compatible_case_type_ids


def test_registry_exposes_tax_intake_and_notice_packs() -> None:
    registry = get_workflow_pack_registry()

    packs = {pack.metadata.workflow_pack_id: pack for pack in registry.list_packs()}

    assert "tax_intake_packet_review" in packs
    assert "tax_intake_packet_review_india" in packs
    assert "tax_notice_review" in packs
    assert "tax_notice_review_india" in packs

    us_intake = packs["tax_intake_packet_review"]
    assert us_intake.metadata.domain_pack_id == "tax_us"
    assert us_intake.metadata.domain_category == "taxation"
    assert us_intake.metadata.jurisdiction == "us"
    assert us_intake.metadata.compatible_case_type_ids == ["tax_us:intake_review"]
    assert len(us_intake.stages) == 7

    india_notice = packs["tax_notice_review_india"]
    assert india_notice.metadata.domain_pack_id == "tax_india"
    assert india_notice.metadata.compatible_case_type_ids == ["tax_india:notice_review"]


def test_execute_without_documents_reports_honest_partial_state(session: Session) -> None:
    case = _create_case(session)
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="prior_auth_packet_review",
            operator_id="operator-1",
        )
    )

    stages = {stage.stage_id: stage for stage in response.run.stage_results}

    assert response.run.status == "completed_partial"
    assert stages["intake_document_check"].status == "completed_partial"
    assert stages["packet_assembly"].status == "skipped"
    assert stages["submission_draft_preparation"].status == "skipped"
    assert response.run.review_recommendation.suggested_next_stage == "awaiting_documents"


def test_execute_with_linked_document_generates_draft_and_plan(session: Session) -> None:
    case = _create_case(session)
    _add_document(session, case_id=case.case_id)
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="prior_auth_packet_review",
            operator_id="operator-2",
        )
    )

    stages = {stage.stage_id: stage for stage in response.run.stage_results}
    submission_stage = stages["submission_draft_preparation"]

    assert stages["packet_assembly"].status == "completed"
    assert submission_stage.status == "completed"
    assert submission_stage.summary["draft_generated"] is True
    assert submission_stage.summary["plan_generated"] is True
    assert submission_stage.summary["plan_id"]


def test_workflow_pack_routes_list_detail_and_execute(client: TestClient, session: Session) -> None:
    case = _create_case(session)

    list_response = client.get("/workflow-packs")
    assert list_response.status_code == 200
    pack_ids = {pack["workflow_pack_id"] for pack in list_response.json()["packs"]}
    assert "prior_auth_packet_review" in pack_ids

    detail_response = client.get("/workflow-packs/prior_auth_packet_review")
    assert detail_response.status_code == 200
    assert detail_response.json()["definition"]["metadata"]["workflow_pack_id"] == "prior_auth_packet_review"

    execute_response = client.post(
        f"/cases/{case.case_id}/workflow-packs/prior_auth_packet_review/execute",
        json={
            "case_id": case.case_id,
            "workflow_pack_id": "prior_auth_packet_review",
            "operator_id": "route-operator",
            "skip_optional_stages": False,
            "notes": [],
        },
    )
    assert execute_response.status_code == 200
    payload = execute_response.json()
    assert payload["run"]["workflow_pack_id"] == "prior_auth_packet_review"
    assert payload["run"]["review_recommendation"]["suggested_next_stage"] == "awaiting_documents"


def test_derive_final_status_prioritizes_blocked_over_completed(session: Session) -> None:
    service = WorkflowPackOrchestrationService(session)

    status = service._derive_final_status([
        WorkflowPackStageResult(stage_id="intake_document_check", status="completed"),
        WorkflowPackStageResult(stage_id="extraction_pass", status="blocked"),
    ])

    assert status == "blocked"


def test_insurance_claim_intake_executes_without_documents(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="insurance_us",
        case_type_id="insurance_us:policy_review",
        domain_category="insurance",
    )
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="insurance_claim_intake_review",
            operator_id="operator-ins-1",
        )
    )

    stages = {stage.stage_id: stage for stage in response.run.stage_results}

    assert response.run.status == "completed_partial"
    assert stages["intake_document_check"].status == "completed_partial"
    assert stages["packet_assembly"].status == "skipped"
    assert response.run.review_recommendation.suggested_next_stage == "awaiting_documents"


def test_insurance_claim_intake_with_document_generates_packet(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="insurance_us",
        case_type_id="insurance_us:coverage_review",
        domain_category="insurance",
    )
    _add_document(session, case_id=case.case_id, filename="policy.pdf")
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="insurance_claim_intake_review",
            operator_id="operator-ins-2",
        )
    )

    stages = {stage.stage_id: stage for stage in response.run.stage_results}

    assert stages["packet_assembly"].status == "completed"
    assert stages["submission_draft_preparation"].status == "completed"
    assert stages["submission_draft_preparation"].summary["draft_generated"] is True


def test_coverage_correspondence_review_executes(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="insurance_us",
        case_type_id="insurance_us:coverage_review",
        domain_category="insurance",
    )
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="coverage_correspondence_review",
            operator_id="operator-cov-1",
        )
    )

    assert response.run.workflow_pack_id == "coverage_correspondence_review"
    assert response.run.status in {"completed", "completed_partial"}

    stages = {stage.stage_id: stage for stage in response.run.stage_results}
    assert stages["checklist_refresh"].status == "completed"
    assert "readiness_evaluation" in stages


def test_insurance_pack_route_list_includes_new_packs(client: TestClient) -> None:
    list_response = client.get("/workflow-packs")
    assert list_response.status_code == 200
    pack_ids = {pack["workflow_pack_id"] for pack in list_response.json()["packs"]}
    assert "insurance_claim_intake_review" in pack_ids
    assert "coverage_correspondence_review" in pack_ids
    assert "insurance_claim_intake_review_india" in pack_ids
    assert "coverage_correspondence_review_india" in pack_ids


def test_insurance_pack_incompatible_case_type_rejected(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="medical_insurance_us",
        case_type_id="medical_insurance_us:prior_auth_review",
        domain_category="medical_insurance",
    )
    service = WorkflowPackOrchestrationService(session)

    from app.workflow_packs.service import WorkflowPackError
    with pytest.raises(WorkflowPackError) as exc_info:
        service.execute(
            WorkflowPackExecutionRequest(
                case_id=case.case_id,
                workflow_pack_id="insurance_claim_intake_review",
                operator_id="operator-bad",
            )
        )
    assert exc_info.value.status_code == 400


def test_tax_intake_review_executes_without_documents(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="tax_us",
        case_type_id="tax_us:intake_review",
        domain_category="taxation",
    )
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="tax_intake_packet_review",
            operator_id="operator-tax-1",
        )
    )

    stages = {stage.stage_id: stage for stage in response.run.stage_results}

    assert response.run.status == "completed_partial"
    assert stages["intake_document_check"].status == "completed_partial"
    assert stages["packet_assembly"].status == "skipped"
    assert response.run.review_recommendation.suggested_next_stage == "awaiting_documents"


def test_tax_intake_review_with_document_generates_packet(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="tax_us",
        case_type_id="tax_us:intake_review",
        domain_category="taxation",
    )
    _add_document(session, case_id=case.case_id, filename="income_statement.pdf")
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="tax_intake_packet_review",
            operator_id="operator-tax-2",
        )
    )

    stages = {stage.stage_id: stage for stage in response.run.stage_results}

    assert stages["packet_assembly"].status == "completed"
    assert stages["submission_draft_preparation"].status == "completed"
    assert stages["submission_draft_preparation"].summary["draft_generated"] is True


def test_tax_notice_review_executes(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="tax_us",
        case_type_id="tax_us:notice_review",
        domain_category="taxation",
    )
    _add_document(session, case_id=case.case_id, filename="irs_notice.pdf")
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="tax_notice_review",
            operator_id="operator-tax-3",
        )
    )

    assert response.run.workflow_pack_id == "tax_notice_review"
    assert response.run.status in {"completed", "completed_partial"}

    stages = {stage.stage_id: stage for stage in response.run.stage_results}
    assert stages["checklist_refresh"].status == "completed"
    assert "readiness_evaluation" in stages


def test_tax_intake_review_india_executes(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="tax_india",
        case_type_id="tax_india:intake_review",
        domain_category="taxation",
        jurisdiction="india",
    )
    _add_document(session, case_id=case.case_id, filename="salary_slip.pdf")
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="tax_intake_packet_review_india",
            operator_id="operator-tax-ind-intake",
        )
    )

    assert response.run.workflow_pack_id == "tax_intake_packet_review_india"
    assert response.run.status in {"completed", "completed_partial"}

    stages = {stage.stage_id: stage for stage in response.run.stage_results}
    assert stages["checklist_refresh"].status == "completed"
    assert stages["packet_assembly"].status == "completed"


def test_tax_notice_review_india_executes(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="tax_india",
        case_type_id="tax_india:notice_review",
        domain_category="taxation",
        jurisdiction="india",
    )
    _add_document(session, case_id=case.case_id, filename="gst_notice.pdf")
    service = WorkflowPackOrchestrationService(session)

    response = service.execute(
        WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id="tax_notice_review_india",
            operator_id="operator-tax-ind-1",
        )
    )

    assert response.run.workflow_pack_id == "tax_notice_review_india"
    assert response.run.status in {"completed", "completed_partial"}

    stages = {stage.stage_id: stage for stage in response.run.stage_results}
    assert stages["checklist_refresh"].status == "completed"
    assert stages["packet_assembly"].status == "completed"


def test_tax_pack_route_list_includes_new_packs(client: TestClient) -> None:
    list_response = client.get("/workflow-packs")
    assert list_response.status_code == 200
    pack_ids = {pack["workflow_pack_id"] for pack in list_response.json()["packs"]}
    assert "tax_intake_packet_review" in pack_ids
    assert "tax_intake_packet_review_india" in pack_ids
    assert "tax_notice_review" in pack_ids
    assert "tax_notice_review_india" in pack_ids


def test_tax_pack_incompatible_case_type_rejected(session: Session) -> None:
    case = _create_case(
        session,
        domain_pack_id="insurance_us",
        case_type_id="insurance_us:policy_review",
        domain_category="insurance",
    )
    service = WorkflowPackOrchestrationService(session)

    from app.workflow_packs.service import WorkflowPackError

    with pytest.raises(WorkflowPackError) as exc_info:
        service.execute(
            WorkflowPackExecutionRequest(
                case_id=case.case_id,
                workflow_pack_id="tax_intake_packet_review",
                operator_id="operator-tax-bad",
            )
        )

    assert exc_info.value.status_code == 400