"""Tests for the human validation foundation — field validation, requirement review, and reviewed state."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.audit.service import AuditTrailService
from app.cases.models import CaseRecordModel
from app.extraction.models import ExtractionRunModel
from app.human_validation.service import HumanValidationService, HumanValidationServiceError
from app.persistence.database import utcnow
from app.readiness.models import ChecklistItemModel, ChecklistModel


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client() -> TestClient:
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_case(session: Session, *, title: str = "Validation Test Case") -> CaseRecordModel:
    now = utcnow()
    case = CaseRecordModel(
        case_id=f"val-case-{now.timestamp()}",
        title=title,
        status="open",
        created_at=now,
        updated_at=now,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _create_extraction(
    session: Session,
    case_id: str,
    *,
    extraction_id: str = "ext-001",
    fields: list[dict] | None = None,
) -> ExtractionRunModel:
    now = utcnow()
    if fields is None:
        fields = [
            {"field_id": "patient_name", "field_type": "string", "value": "Jane Doe", "raw_value": "Jane Doe", "is_present": True, "grounding": []},
            {"field_id": "date_of_birth", "field_type": "date", "value": "1990-01-15", "raw_value": "1990-01-15", "is_present": True, "grounding": []},
            {"field_id": "policy_number", "field_type": "string", "value": None, "raw_value": None, "is_present": False, "grounding": []},
        ]
    run = ExtractionRunModel(
        extraction_id=extraction_id,
        document_id="doc-001",
        template_id="test-template",
        case_id=case_id,
        strategy_used="provider_structured",
        status="completed",
        field_count=len(fields),
        fields_extracted=sum(1 for f in fields if f.get("is_present")),
        grounding_available=False,
        fields_json=fields,
        errors_json=[],
        events_json=[],
        created_at=now,
    )
    session.merge(run)
    session.commit()
    return run


def _create_checklist(session: Session, case_id: str) -> tuple[ChecklistModel, list[ChecklistItemModel]]:
    now = utcnow()
    checklist = ChecklistModel(
        checklist_id=f"chk-{case_id}",
        case_id=case_id,
        domain_pack_id="test-pack",
        case_type_id="test-case-type",
        requirement_count=2,
        created_at=now,
    )
    session.add(checklist)

    items = []
    for i, name in enumerate(["Medical records", "Identity document"], start=1):
        item = ChecklistItemModel(
            item_id=f"item-{case_id}-{i}",
            checklist_id=checklist.checklist_id,
            requirement_id=f"req-{i}",
            display_name=name,
            description=f"Test requirement: {name}",
            document_category=f"category_{i}",
            priority="required" if i == 1 else "recommended",
            status="missing",
            created_at=now,
        )
        session.add(item)
        items.append(item)

    session.commit()
    return checklist, items


# ---------------------------------------------------------------------------
# Field validation tests
# ---------------------------------------------------------------------------


class TestFieldValidation:
    def test_validate_field_accept(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        result = service.validate_field(
            ext.extraction_id, "patient_name",
            ValidateFieldRequest(
                status="accepted",
                note="Value looks correct",
                reviewer_id="op-1",
                reviewer_display_name="Test Operator",
            ),
        )

        v = result.validation
        assert v.extraction_id == ext.extraction_id
        assert v.field_id == "patient_name"
        assert v.status == "accepted"
        assert v.original.value == "Jane Doe"
        assert v.reviewer.reviewer_id == "op-1"
        assert v.note == "Value looks correct"

    def test_validate_field_correct(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id, extraction_id="ext-correct")
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        result = service.validate_field(
            ext.extraction_id, "patient_name",
            ValidateFieldRequest(
                status="corrected",
                reviewed_value="Jane M. Doe",
                reviewer_id="op-2",
            ),
        )

        v = result.validation
        assert v.status == "corrected"
        assert v.original.value == "Jane Doe"
        assert v.reviewed_value == "Jane M. Doe"

    def test_validate_field_upsert(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id, extraction_id="ext-upsert")
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        service.validate_field(
            ext.extraction_id, "date_of_birth",
            ValidateFieldRequest(status="needs_followup", note="Check date format"),
        )
        result = service.validate_field(
            ext.extraction_id, "date_of_birth",
            ValidateFieldRequest(status="accepted", note="Confirmed correct"),
        )

        v = result.validation
        assert v.status == "accepted"
        assert v.note == "Confirmed correct"

    def test_validate_field_not_found(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id, extraction_id="ext-notfound")
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        with pytest.raises(HumanValidationServiceError, match="not found"):
            service.validate_field(
                ext.extraction_id, "nonexistent_field",
                ValidateFieldRequest(status="accepted"),
            )

    def test_validate_extraction_not_found(self, session: Session) -> None:
        service = HumanValidationService(session)
        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        with pytest.raises(HumanValidationServiceError, match="not found"):
            service.validate_field(
                "no-such-extraction", "field",
                ValidateFieldRequest(status="accepted"),
            )

    def test_get_extraction_validations(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id, extraction_id="ext-list")
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        service.validate_field(ext.extraction_id, "patient_name", ValidateFieldRequest(status="accepted"))
        service.validate_field(ext.extraction_id, "date_of_birth", ValidateFieldRequest(status="corrected", reviewed_value="1990-02-15"))

        result = service.get_extraction_validations(case.case_id)
        assert result.case_id == case.case_id
        assert len(result.validations) == 2

    def test_field_validation_emits_audit(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id, extraction_id="ext-audit")
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        service.validate_field(ext.extraction_id, "patient_name", ValidateFieldRequest(status="accepted", reviewer_id="op-audit"))

        audit = AuditTrailService(session)
        decisions = audit.get_case_decisions(case.case_id)
        field_decisions = [d for d in decisions.decisions if d.decision_type == "field_validated"]
        assert len(field_decisions) >= 1
        assert field_decisions[0].outcome == "accepted"


# ---------------------------------------------------------------------------
# Requirement review tests
# ---------------------------------------------------------------------------


class TestRequirementReview:
    def test_review_requirement_confirm(self, session: Session) -> None:
        case = _create_case(session)
        checklist, items = _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        result = service.review_requirement(
            case.case_id, items[0].item_id,
            ReviewRequirementRequest(
                status="confirmed_supported",
                note="Medical records uploaded and verified",
                reviewer_id="op-1",
                reviewer_display_name="Test Operator",
            ),
        )

        r = result.review
        assert r.case_id == case.case_id
        assert r.item_id == items[0].item_id
        assert r.status == "confirmed_supported"
        assert r.original_machine_status == "missing"
        assert r.note == "Medical records uploaded and verified"

    def test_review_requirement_missing(self, session: Session) -> None:
        case = _create_case(session)
        checklist, items = _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        result = service.review_requirement(
            case.case_id, items[1].item_id,
            ReviewRequirementRequest(
                status="confirmed_missing",
                note="Patient has not provided identity document yet",
            ),
        )

        assert result.review.status == "confirmed_missing"

    def test_review_requirement_upsert(self, session: Session) -> None:
        case = _create_case(session)
        checklist, items = _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        service.review_requirement(
            case.case_id, items[0].item_id,
            ReviewRequirementRequest(status="requires_more_information"),
        )
        result = service.review_requirement(
            case.case_id, items[0].item_id,
            ReviewRequirementRequest(status="confirmed_supported", note="Document received"),
        )
        assert result.review.status == "confirmed_supported"
        assert result.review.note == "Document received"

    def test_review_requirement_not_found(self, session: Session) -> None:
        case = _create_case(session)
        _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        with pytest.raises(HumanValidationServiceError, match="not found"):
            service.review_requirement(
                case.case_id, "nonexistent-item",
                ReviewRequirementRequest(status="confirmed_supported"),
            )

    def test_review_no_checklist(self, session: Session) -> None:
        case = _create_case(session)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        with pytest.raises(HumanValidationServiceError, match="No checklist"):
            service.review_requirement(
                case.case_id, "item-1",
                ReviewRequirementRequest(status="confirmed_supported"),
            )

    def test_get_requirement_reviews(self, session: Session) -> None:
        case = _create_case(session)
        checklist, items = _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        service.review_requirement(case.case_id, items[0].item_id, ReviewRequirementRequest(status="confirmed_supported"))
        service.review_requirement(case.case_id, items[1].item_id, ReviewRequirementRequest(status="confirmed_missing"))

        result = service.get_requirement_reviews(case.case_id)
        assert result.case_id == case.case_id
        assert len(result.reviews) == 2

    def test_requirement_review_emits_audit(self, session: Session) -> None:
        case = _create_case(session)
        checklist, items = _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        service.review_requirement(
            case.case_id, items[0].item_id,
            ReviewRequirementRequest(status="confirmed_supported", reviewer_id="op-audit"),
        )

        audit = AuditTrailService(session)
        decisions = audit.get_case_decisions(case.case_id)
        req_decisions = [d for d in decisions.decisions if d.decision_type == "requirement_reviewed"]
        assert len(req_decisions) >= 1
        assert req_decisions[0].outcome == "confirmed_supported"


# ---------------------------------------------------------------------------
# Reviewed case state projection tests
# ---------------------------------------------------------------------------


class TestReviewedCaseState:
    def test_empty_state(self, session: Session) -> None:
        case = _create_case(session)
        service = HumanValidationService(session)
        result = service.get_reviewed_state(case.case_id)
        state = result.state

        assert state.case_id == case.case_id
        assert state.has_reviewed_state is False
        assert state.field_validation.total_fields == 0
        assert state.field_validation.reviewed_fields == 0

    def test_state_with_validations(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id, extraction_id="ext-state")
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest
        service.validate_field(ext.extraction_id, "patient_name", ValidateFieldRequest(status="accepted"))
        service.validate_field(ext.extraction_id, "date_of_birth", ValidateFieldRequest(status="corrected", reviewed_value="1990-02-15"))
        service.validate_field(ext.extraction_id, "policy_number", ValidateFieldRequest(status="rejected", note="Not applicable"))

        result = service.get_reviewed_state(case.case_id)
        state = result.state

        assert state.has_reviewed_state is True
        assert state.field_validation.total_fields == 3
        assert state.field_validation.reviewed_fields == 3
        assert state.field_validation.accepted_fields == 1
        assert state.field_validation.corrected_fields == 1
        assert state.field_validation.rejected_fields == 1

    def test_state_with_requirement_reviews(self, session: Session) -> None:
        case = _create_case(session)
        checklist, items = _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ReviewRequirementRequest
        service.review_requirement(case.case_id, items[0].item_id, ReviewRequirementRequest(status="confirmed_supported"))

        result = service.get_reviewed_state(case.case_id)
        state = result.state

        assert state.has_reviewed_state is True
        assert state.requirement_review.total_items == 2
        assert state.requirement_review.reviewed_items == 1
        assert state.requirement_review.confirmed_supported == 1
        assert state.requirement_review.unresolved_count == 1

    def test_unresolved_items(self, session: Session) -> None:
        case = _create_case(session)
        ext = _create_extraction(session, case.case_id, extraction_id="ext-unresolved")
        checklist, items = _create_checklist(session, case.case_id)
        service = HumanValidationService(session)

        from casegraph_agent_sdk.human_validation import ValidateFieldRequest, ReviewRequirementRequest
        service.validate_field(ext.extraction_id, "patient_name", ValidateFieldRequest(status="needs_followup", note="Verify with patient"))
        service.review_requirement(case.case_id, items[1].item_id, ReviewRequirementRequest(status="requires_more_information", note="Missing docs"))

        result = service.get_reviewed_state(case.case_id)
        assert len(result.state.unresolved_items) == 2
        types = {item.item_type for item in result.state.unresolved_items}
        assert "field_validation" in types
        assert "requirement_review" in types

    def test_case_not_found(self, session: Session) -> None:
        service = HumanValidationService(session)
        with pytest.raises(HumanValidationServiceError, match="not found"):
            service.get_reviewed_state("nonexistent-case")


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


class TestHumanValidationAPI:
    @pytest.fixture()
    def client(self):
        from fastapi import FastAPI
        from sqlalchemy.pool import StaticPool
        from app.human_validation.router import router as hv_router
        from app.persistence.database import get_session

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)

        def override_session():
            with Session(engine) as s:
                yield s

        app = FastAPI()
        app.include_router(hv_router)
        app.dependency_overrides[get_session] = override_session

        # Seed a case
        with Session(engine) as seed:
            case = CaseRecordModel(
                case_id="hv-api-case",
                title="HV API Test Case",
            )
            seed.add(case)
            seed.commit()

        with TestClient(app) as tc:
            tc._engine = engine  # type: ignore[attr-defined]
            yield tc

    def test_review_state_empty(self, client: TestClient) -> None:
        resp = client.get("/cases/hv-api-case/review-state")
        assert resp.status_code == 200
        state = resp.json()["state"]
        assert state["has_reviewed_state"] is False

    def test_validate_field_via_api(self, client: TestClient) -> None:
        engine = client._engine  # type: ignore[attr-defined]
        with Session(engine) as seed:
            _create_extraction(seed, "hv-api-case", extraction_id="api-ext-001")

        resp = client.post(
            "/extractions/api-ext-001/fields/patient_name/validate",
            json={"status": "accepted", "note": "Verified", "reviewer_id": "op-api"},
        )
        assert resp.status_code == 200
        assert resp.json()["validation"]["status"] == "accepted"
        assert resp.json()["validation"]["original"]["value"] == "Jane Doe"

        list_resp = client.get("/cases/hv-api-case/extraction-validations")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["validations"]) == 1

    def test_review_requirement_via_api(self, client: TestClient) -> None:
        engine = client._engine  # type: ignore[attr-defined]
        with Session(engine) as seed:
            _create_checklist(seed, "hv-api-case")

        resp = client.post(
            "/cases/hv-api-case/checklist/items/item-hv-api-case-1/review",
            json={"status": "confirmed_supported", "note": "Evidence reviewed"},
        )
        assert resp.status_code == 200
        assert resp.json()["review"]["status"] == "confirmed_supported"

        list_resp = client.get("/cases/hv-api-case/requirement-reviews")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["reviews"]) == 1

    def test_review_state_after_validations(self, client: TestClient) -> None:
        engine = client._engine  # type: ignore[attr-defined]
        with Session(engine) as seed:
            _create_extraction(seed, "hv-api-case", extraction_id="api-ext-state")

        client.post(
            "/extractions/api-ext-state/fields/patient_name/validate",
            json={"status": "accepted"},
        )
        client.post(
            "/extractions/api-ext-state/fields/date_of_birth/validate",
            json={"status": "corrected", "reviewed_value": "1990-02-15"},
        )

        resp = client.get("/cases/hv-api-case/review-state")
        assert resp.status_code == 200
        state = resp.json()["state"]
        assert state["has_reviewed_state"] is True
        assert state["field_validation"]["reviewed_fields"] == 2

    def test_missing_case_returns_404(self, client: TestClient) -> None:
        assert client.get("/cases/no-such-case/review-state").status_code == 404
        assert client.get("/cases/no-such-case/extraction-validations").status_code == 404
        assert client.get("/cases/no-such-case/requirement-reviews").status_code == 404
