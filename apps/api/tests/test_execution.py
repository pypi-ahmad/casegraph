"""Tests for approval-gated automation execution with human checkpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.automation import (
    AutomationBackend,
    AutomationCapabilitiesResponse,
    ToolCapabilityFlags,
    ToolMetadata,
)
from casegraph_agent_sdk.execution import (
    ApproveCheckpointRequest,
    AutomationExecutionRequest,
    AutomationResumeRequest,
    BlockCheckpointRequest,
    SkipCheckpointRequest,
)
from casegraph_agent_sdk.submissions import (
    ApprovalRequirementMetadata,
    AutomationFallbackRoutingHint,
    AutomationPlan,
    AutomationPlanStep,
    DryRunResultSummary,
    ExecutionGuardrailMetadata,
)

from app.cases.models import CaseRecordModel
from app.execution.gating import (
    BLOCKED_STEP_TYPES,
    EXECUTABLE_STEP_TYPES,
    check_execution_approval,
    classify_blocked_steps,
    is_step_executable,
)
from app.execution.service import AutomationExecutionService
from app.persistence.database import get_session, utcnow
from app.submissions.models import (
    AutomationPlanModel,
    AutomationPlanStepModel,
    SubmissionDraftModel,
)


async def _caps_with_browser() -> AutomationCapabilitiesResponse:
    return AutomationCapabilitiesResponse(
        tools=[
            ToolMetadata(
                id="playwright.navigate",
                version="0.1.0",
                display_name="Playwright Navigate",
                description="Navigate to a URL.",
                category="browser_automation",
                safety_level="read_only",
                implementation_status="adapter_only",
                capability_flags=ToolCapabilityFlags(
                    read_only=True,
                    requires_approval=False,
                    requires_browser_session=True,
                    requires_computer_use_provider=False,
                ),
            )
        ],
        backends=[
            AutomationBackend(
                id="playwright_mcp",
                display_name="Playwright MCP",
                status="adapter_only",
                notes=["Configured locally."],
            )
        ],
    )


async def _caps_empty() -> AutomationCapabilitiesResponse:
    return AutomationCapabilitiesResponse()


@pytest.fixture()
def session() -> Session:
    import app.cases.models  # noqa: F401
    import app.execution.models  # noqa: F401
    import app.extraction.models  # noqa: F401
    import app.ingestion.models  # noqa: F401
    import app.operator_review.models  # noqa: F401
    import app.packets.models  # noqa: F401
    import app.readiness.models  # noqa: F401
    import app.review.models  # noqa: F401
    import app.submissions.models  # noqa: F401
    import app.tasks.models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def _make_case(session: Session) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Execution Test Case",
        category="operations",
        status="open",
        summary="Summary",
        current_stage="document_review",
        case_metadata_json={},
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _make_draft(
    session: Session,
    case_id: str,
    *,
    approval_status: str = "approved_for_future_execution",
    status: str = "approved_for_future_execution",
    approved_by: str = "operator@example.com",
) -> SubmissionDraftModel:
    draft = SubmissionDraftModel(
        draft_id=str(uuid4()),
        case_id=case_id,
        packet_id=str(uuid4()),
        submission_target_id="portal_submission",
        submission_target_category="portal",
        status=status,
        approval_status=approval_status,
        approved_by=approved_by,
        approved_at=utcnow() if approved_by else None,
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def _make_plan(
    session: Session,
    draft_id: str,
    *,
    status: str = "approved_for_future_execution",
) -> AutomationPlanModel:
    plan = AutomationPlanModel(
        plan_id=str(uuid4()),
        draft_id=draft_id,
        target_id="portal_submission",
        status=status,
        dry_run=True,
        guardrails_json=ExecutionGuardrailMetadata().model_dump(mode="json"),
        dry_run_summary_json=DryRunResultSummary(plan_status=status, total_steps=6).model_dump(mode="json"),
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


_STEP_SEQUENCE = [
    {
        "step_type": "open_target",
        "title": "Open portal",
        "status": "informational",
        "tool_id": "playwright.navigate",
        "backend_id": "playwright_mcp",
        "target_reference": "https://example.com/portal",
        "execution_mode": "playwright_mcp",
        "checkpoint_required": False,
        "checkpoint_reason": "",
        "fallback_hint": None,
    },
    {
        "step_type": "navigate_section",
        "title": "Go to claims section",
        "status": "informational",
        "tool_id": None,
        "backend_id": None,
        "target_reference": "claims_section",
        "execution_mode": "computer_use_fallback",
        "checkpoint_required": True,
        "checkpoint_reason": "Operator review is required before non-deterministic section navigation.",
        "fallback_hint": AutomationFallbackRoutingHint(
            recommended_mode="computer_use_fallback",
            reason="Selectors are not modeled for this transition.",
            supported_provider_ids=["openai_computer_use"],
            notes=["Fallback remains metadata-only in this build."],
        ),
    },
    {
        "step_type": "populate_field_placeholder",
        "title": "Populate full name",
        "status": "blocked",
        "tool_id": None,
        "backend_id": None,
        "target_reference": "",
        "execution_mode": "blocked",
        "checkpoint_required": False,
        "checkpoint_reason": "",
        "fallback_hint": None,
    },
    {
        "step_type": "attach_document_placeholder",
        "title": "Attach claim document",
        "status": "blocked",
        "tool_id": None,
        "backend_id": None,
        "target_reference": "",
        "execution_mode": "blocked",
        "checkpoint_required": False,
        "checkpoint_reason": "",
        "fallback_hint": None,
    },
    {
        "step_type": "review_before_submit",
        "title": "Final review checkpoint",
        "status": "informational",
        "tool_id": None,
        "backend_id": None,
        "target_reference": "review_before_submit",
        "execution_mode": "manual_only",
        "checkpoint_required": True,
        "checkpoint_reason": "Explicit human confirmation is required before any submission-adjacent review step.",
        "fallback_hint": AutomationFallbackRoutingHint(
            recommended_mode="manual_only",
            reason="Final review must remain operator-controlled.",
            supported_provider_ids=[],
            notes=["No final submit action is performed in this build."],
        ),
    },
    {
        "step_type": "submit_blocked_placeholder",
        "title": "Submit (blocked)",
        "status": "blocked",
        "tool_id": None,
        "backend_id": None,
        "target_reference": "",
        "execution_mode": "blocked",
        "checkpoint_required": False,
        "checkpoint_reason": "",
        "fallback_hint": None,
    },
]


def _make_plan_steps(session: Session, plan_id: str) -> list[AutomationPlanStepModel]:
    steps: list[AutomationPlanStepModel] = []
    for index, step_data in enumerate(_STEP_SEQUENCE, start=1):
        fallback_hint = step_data["fallback_hint"]
        step = AutomationPlanStepModel(
            step_id=str(uuid4()),
            plan_id=plan_id,
            step_index=index,
            step_type=step_data["step_type"],
            status=step_data["status"],
            title=step_data["title"],
            description=f"Step {index}: {step_data['title']}",
            target_reference=step_data["target_reference"],
            tool_id=step_data["tool_id"],
            backend_id=step_data["backend_id"],
            execution_mode=step_data["execution_mode"],
            checkpoint_required=step_data["checkpoint_required"],
            checkpoint_reason=step_data["checkpoint_reason"],
            fallback_hint_json=fallback_hint.model_dump(mode="json") if fallback_hint is not None else {},
            notes_json=[],
        )
        session.add(step)
        steps.append(step)
    session.commit()
    return steps


def _build_plan_sdk(plan_model: AutomationPlanModel, steps: list[AutomationPlanStepModel]) -> AutomationPlan:
    return AutomationPlan(
        plan_id=plan_model.plan_id,
        draft_id=plan_model.draft_id,
        target_id=plan_model.target_id,
        status=plan_model.status,
        dry_run=plan_model.dry_run,
        generated_at=plan_model.created_at.isoformat(),
        guardrails=ExecutionGuardrailMetadata.model_validate(plan_model.guardrails_json),
        dry_run_summary=DryRunResultSummary.model_validate(plan_model.dry_run_summary_json),
        steps=[
            AutomationPlanStep(
                step_id=step.step_id,
                step_index=step.step_index,
                step_type=step.step_type,
                status=step.status,
                title=step.title,
                description=step.description,
                target_reference=step.target_reference,
                tool_id=step.tool_id,
                backend_id=step.backend_id,
                execution_mode=step.execution_mode,
                checkpoint_required=step.checkpoint_required,
                checkpoint_reason=step.checkpoint_reason,
                fallback_hint=(
                    AutomationFallbackRoutingHint.model_validate(step.fallback_hint_json)
                    if step.fallback_hint_json else None
                ),
                notes=[],
            )
            for step in steps
        ],
    )


class TestApprovalGating:
    def test_approved_draft_passes_gate(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id)
        steps = _make_plan_steps(session, plan_model.plan_id)
        plan = _build_plan_sdk(plan_model, steps)
        approval = ApprovalRequirementMetadata(
            requires_operator_approval=True,
            approval_status="approved_for_future_execution",
            approved_by="operator@example.com",
            scope="future_execution",
        )

        gate = check_execution_approval(draft, plan, approval)

        assert gate.allowed is True
        assert gate.reason == "Execution approved."

    def test_unapproved_draft_fails_gate(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(
            session,
            case.case_id,
            approval_status="awaiting_operator_review",
            status="awaiting_operator_review",
        )
        plan_model = _make_plan(session, draft.draft_id)
        steps = _make_plan_steps(session, plan_model.plan_id)
        plan = _build_plan_sdk(plan_model, steps)
        approval = ApprovalRequirementMetadata(
            requires_operator_approval=True,
            approval_status="awaiting_operator_review",
            scope="future_execution",
        )

        gate = check_execution_approval(draft, plan, approval)

        assert gate.allowed is False
        assert "awaiting_operator_review" in gate.reason

    def test_superseded_draft_blocked(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(
            session,
            case.case_id,
            status="superseded_placeholder",
            approval_status="approved_for_future_execution",
        )
        plan_model = _make_plan(session, draft.draft_id)
        steps = _make_plan_steps(session, plan_model.plan_id)
        plan = _build_plan_sdk(plan_model, steps)
        approval = ApprovalRequirementMetadata(
            requires_operator_approval=True,
            approval_status="approved_for_future_execution",
            scope="future_execution",
        )

        gate = check_execution_approval(draft, plan, approval)

        assert gate.allowed is False
        assert "Superseded" in gate.reason

    def test_blocked_plan_fails_gate(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id, status="blocked")
        steps = _make_plan_steps(session, plan_model.plan_id)
        plan = _build_plan_sdk(plan_model, steps)
        approval = ApprovalRequirementMetadata(
            requires_operator_approval=True,
            approval_status="approved_for_future_execution",
            scope="future_execution",
        )

        gate = check_execution_approval(draft, plan, approval)

        assert gate.allowed is False
        assert "blocked" in gate.reason.lower()

    def test_classify_blocked_steps_identifies_all_blocked_types(self) -> None:
        steps = [
            AutomationPlanStep(
                step_id=str(uuid4()),
                step_index=index,
                step_type=step_type,
                status="blocked" if step_type in BLOCKED_STEP_TYPES else "informational",
                title=f"Step {index}",
            )
            for index, step_type in enumerate(
                [
                    "open_target",
                    "populate_field_placeholder",
                    "attach_document_placeholder",
                    "submit_blocked_placeholder",
                ],
                start=1,
            )
        ]

        blocked = classify_blocked_steps(steps)

        assert {record.step_type for record in blocked} == BLOCKED_STEP_TYPES

    def test_is_step_executable_for_safe_types(self) -> None:
        for step_type in EXECUTABLE_STEP_TYPES:
            step = AutomationPlanStep(
                step_id=str(uuid4()),
                step_index=1,
                step_type=step_type,
                status="informational",
                title="Test",
            )
            assert is_step_executable(step) is True

    def test_is_step_executable_rejects_blocked_types(self) -> None:
        for step_type in BLOCKED_STEP_TYPES:
            step = AutomationPlanStep(
                step_id=str(uuid4()),
                step_index=1,
                step_type=step_type,
                status="blocked",
                title="Test",
            )
            assert is_step_executable(step) is False


class TestExecutionService:
    def test_blocked_when_unapproved(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(
            session,
            case.case_id,
            approval_status="awaiting_operator_review",
            status="awaiting_operator_review",
        )
        plan_model = _make_plan(session, draft.draft_id)
        _make_plan_steps(session, plan_model.plan_id)
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        response = asyncio.run(
            service.execute(
                AutomationExecutionRequest(
                    draft_id=draft.draft_id,
                    plan_id=plan_model.plan_id,
                )
            )
        )

        assert response.result.success is False
        assert response.run.status == "blocked"
        assert response.run.run_id == ""

    def test_execute_pauses_at_first_checkpoint(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id)
        _make_plan_steps(session, plan_model.plan_id)
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        response = asyncio.run(
            service.execute(
                AutomationExecutionRequest(
                    draft_id=draft.draft_id,
                    plan_id=plan_model.plan_id,
                    operator_id="operator-1",
                )
            )
        )
        detail = service.get_run_detail(response.run.run_id)

        assert response.result.success is True
        assert response.run.status == "awaiting_operator_review"
        assert response.run.operator_id == "operator-1"
        assert response.run.paused_run is not None
        assert len(detail.checkpoints) == 1
        assert detail.checkpoints[0].step_type == "navigate_section"
        assert detail.checkpoints[0].status == "pending_operator_review"
        assert detail.steps[0].step_type == "open_target"
        assert detail.steps[0].status == "skipped"
        assert detail.steps[1].step_type == "navigate_section"
        assert detail.steps[1].status == "awaiting_operator_review"

    def test_skip_checkpoint_then_resume_reaches_next_checkpoint(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id)
        _make_plan_steps(session, plan_model.plan_id)
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        execute_response = asyncio.run(
            service.execute(
                AutomationExecutionRequest(draft_id=draft.draft_id, plan_id=plan_model.plan_id)
            )
        )
        first_checkpoint = service.get_run_detail(execute_response.run.run_id).checkpoints[0]

        skip_response = service.skip_checkpoint(
            execute_response.run.run_id,
            first_checkpoint.checkpoint_id,
            SkipCheckpointRequest(
                operator_id="operator-2",
                decision_note="Do not attempt this in automation.",
                skip_reason="Operator will handle this transition manually.",
            ),
        )
        resume_response = asyncio.run(
            service.resume(
                execute_response.run.run_id,
                AutomationResumeRequest(operator_id="operator-2", note="Continue after manual transition."),
            )
        )
        detail = service.get_run_detail(execute_response.run.run_id)

        assert skip_response.checkpoint.status == "skipped"
        assert skip_response.override.decision_type == "skip_step"
        assert resume_response.run.status == "awaiting_operator_review"
        assert len(detail.checkpoints) == 2
        assert detail.checkpoints[0].status == "skipped"
        assert detail.checkpoints[1].step_type == "review_before_submit"
        assert detail.checkpoints[1].status == "pending_operator_review"

        step_statuses = {step.step_type: step.status for step in detail.steps}
        assert step_statuses["navigate_section"] == "skipped"
        assert step_statuses["populate_field_placeholder"] == "blocked"
        assert step_statuses["attach_document_placeholder"] == "blocked"
        assert step_statuses["review_before_submit"] == "awaiting_operator_review"

    def test_approve_all_checkpoints_and_resume_finishes_run(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id)
        _make_plan_steps(session, plan_model.plan_id)
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        execute_response = asyncio.run(
            service.execute(
                AutomationExecutionRequest(draft_id=draft.draft_id, plan_id=plan_model.plan_id)
            )
        )
        first_checkpoint = service.get_run_detail(execute_response.run.run_id).checkpoints[0]

        service.approve_checkpoint(
            execute_response.run.run_id,
            first_checkpoint.checkpoint_id,
            ApproveCheckpointRequest(
                operator_id="operator-3",
                decision_note="Continue without computer-use execution.",
            ),
        )
        after_first_resume = asyncio.run(
            service.resume(
                execute_response.run.run_id,
                AutomationResumeRequest(operator_id="operator-3", note="Resume after approval."),
            )
        )
        second_checkpoint = service.get_run_detail(execute_response.run.run_id).checkpoints[1]

        service.approve_checkpoint(
            execute_response.run.run_id,
            second_checkpoint.checkpoint_id,
            ApproveCheckpointRequest(operator_id="operator-3", decision_note="Manual review completed."),
        )
        final_response = asyncio.run(
            service.resume(
                execute_response.run.run_id,
                AutomationResumeRequest(operator_id="operator-3", note="Finish remaining safe steps."),
            )
        )
        detail = service.get_run_detail(execute_response.run.run_id)

        assert after_first_resume.run.status == "awaiting_operator_review"
        assert final_response.run.status == "completed_partial"
        assert final_response.run.paused_run is None
        assert detail.run.summary.checkpoint_count == 2
        assert detail.run.summary.pending_checkpoint_count == 0

        step_statuses = {step.step_type: step.status for step in detail.steps}
        assert step_statuses["open_target"] == "skipped"
        assert step_statuses["navigate_section"] == "skipped"
        assert step_statuses["review_before_submit"] == "completed"
        assert step_statuses["submit_blocked_placeholder"] == "blocked"

        checkpoint_statuses = {checkpoint.step_type: checkpoint.status for checkpoint in detail.checkpoints}
        assert checkpoint_statuses["navigate_section"] == "resolved"
        assert checkpoint_statuses["review_before_submit"] == "resolved"

    def test_block_checkpoint_stops_run(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id)
        _make_plan_steps(session, plan_model.plan_id)
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        execute_response = asyncio.run(
            service.execute(
                AutomationExecutionRequest(draft_id=draft.draft_id, plan_id=plan_model.plan_id)
            )
        )
        checkpoint = service.get_run_detail(execute_response.run.run_id).checkpoints[0]

        block_response = service.block_checkpoint(
            execute_response.run.run_id,
            checkpoint.checkpoint_id,
            BlockCheckpointRequest(
                operator_id="operator-4",
                decision_note="Unsafe to proceed.",
                block_reason="Target state does not match the approved plan.",
            ),
        )
        detail = service.get_run_detail(execute_response.run.run_id)

        assert block_response.checkpoint.status == "blocked"
        assert block_response.run.status == "blocked"
        assert detail.run.paused_run is None
        assert detail.steps[1].status == "blocked"
        assert any(event.event_type == "run_blocked" for event in detail.events)

    def test_list_runs_for_case_returns_runs_descending(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id)
        _make_plan_steps(session, plan_model.plan_id)
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        first = asyncio.run(
            service.execute(
                AutomationExecutionRequest(draft_id=draft.draft_id, plan_id=plan_model.plan_id)
            )
        )
        second = asyncio.run(
            service.execute(
                AutomationExecutionRequest(draft_id=draft.draft_id, plan_id=plan_model.plan_id)
            )
        )
        runs = service.list_runs_for_case(case.case_id)

        assert len(runs.runs) == 2
        assert runs.runs[0].run_id == second.run.run_id
        assert runs.runs[1].run_id == first.run.run_id

    def test_execute_missing_draft_raises(self, session: Session) -> None:
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        with pytest.raises(Exception, match="not found"):
            asyncio.run(
                service.execute(
                    AutomationExecutionRequest(draft_id="missing-draft", plan_id="missing-plan")
                )
            )

    def test_resume_without_operator_decision_raises(self, session: Session) -> None:
        case = _make_case(session)
        draft = _make_draft(session, case.case_id)
        plan_model = _make_plan(session, draft.draft_id)
        _make_plan_steps(session, plan_model.plan_id)
        service = AutomationExecutionService(
            session,
            playwright_mcp_url="http://localhost:19999",
            automation_capabilities_loader=_caps_empty,
        )

        execute_response = asyncio.run(
            service.execute(
                AutomationExecutionRequest(draft_id=draft.draft_id, plan_id=plan_model.plan_id)
            )
        )

        with pytest.raises(Exception, match="operator decision"):
            asyncio.run(
                service.resume(
                    execute_response.run.run_id,
                    AutomationResumeRequest(operator_id="operator-5"),
                )
            )


class TestExecutionAPI:
    @pytest.fixture()
    def client(self) -> TestClient:
        import app.cases.models  # noqa: F401
        import app.execution.models  # noqa: F401
        import app.extraction.models  # noqa: F401
        import app.ingestion.models  # noqa: F401
        import app.operator_review.models  # noqa: F401
        import app.packets.models  # noqa: F401
        import app.readiness.models  # noqa: F401
        import app.review.models  # noqa: F401
        import app.submissions.models  # noqa: F401
        import app.tasks.models  # noqa: F401

        from app.execution import router as execution_router_module
        from app.execution.router import router as execution_router

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)

        def override_session():
            with Session(engine) as db_session:
                yield db_session

        def override_service(session: Session = Depends(get_session)) -> AutomationExecutionService:
            return AutomationExecutionService(
                session,
                playwright_mcp_url="http://localhost:19999",
                automation_capabilities_loader=_caps_empty,
            )

        app = FastAPI()
        app.include_router(execution_router)
        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[execution_router_module._get_service] = override_service

        with Session(engine) as seed:
            case = _make_case(seed)
            draft = _make_draft(seed, case.case_id)
            plan_model = _make_plan(seed, draft.draft_id)
            _make_plan_steps(seed, plan_model.plan_id)
            case_id = case.case_id
            draft_id = draft.draft_id
            plan_id = plan_model.plan_id

        with TestClient(app) as test_client:
            test_client.case_id = case_id  # type: ignore[attr-defined]
            test_client.draft_id = draft_id  # type: ignore[attr-defined]
            test_client.plan_id = plan_id  # type: ignore[attr-defined]
            yield test_client

    def test_execute_via_api_pauses_at_checkpoint(self, client: TestClient) -> None:
        response = client.post(
            f"/submission-drafts/{client.draft_id}/execute",  # type: ignore[attr-defined]
            json={
                "draft_id": client.draft_id,  # type: ignore[attr-defined]
                "plan_id": client.plan_id,  # type: ignore[attr-defined]
                "operator_id": "api-operator",
            },
        )
        data = response.json()

        assert response.status_code == 200
        assert data["result"]["success"] is True
        assert data["run"]["status"] == "awaiting_operator_review"
        assert data["run"]["paused_run"]["checkpoint_status"] == "pending_operator_review"

    def test_case_run_list_and_checkpoint_routes(self, client: TestClient) -> None:
        execute_response = client.post(
            f"/submission-drafts/{client.draft_id}/execute",  # type: ignore[attr-defined]
            json={"draft_id": client.draft_id, "plan_id": client.plan_id},  # type: ignore[attr-defined]
        )
        run_id = execute_response.json()["run"]["run_id"]

        list_response = client.get(f"/cases/{client.case_id}/automation-runs")  # type: ignore[attr-defined]
        checkpoints_response = client.get(f"/automation-runs/{run_id}/checkpoints")

        assert list_response.status_code == 200
        assert list_response.json()["runs"][0]["run_id"] == run_id
        assert checkpoints_response.status_code == 200
        assert len(checkpoints_response.json()["checkpoints"]) == 1
        assert checkpoints_response.json()["checkpoints"][0]["step_type"] == "navigate_section"

    def test_skip_and_resume_via_api(self, client: TestClient) -> None:
        execute_response = client.post(
            f"/submission-drafts/{client.draft_id}/execute",  # type: ignore[attr-defined]
            json={"draft_id": client.draft_id, "plan_id": client.plan_id},  # type: ignore[attr-defined]
        )
        run_id = execute_response.json()["run"]["run_id"]
        checkpoint_id = client.get(f"/automation-runs/{run_id}/checkpoints").json()["checkpoints"][0]["checkpoint_id"]

        skip_response = client.post(
            f"/automation-runs/{run_id}/checkpoints/{checkpoint_id}/skip",
            json={
                "operator_id": "api-operator",
                "decision_note": "Skip via protected UI.",
                "skip_reason": "Manual transition required.",
            },
        )
        resume_response = client.post(
            f"/automation-runs/{run_id}/resume",
            json={"operator_id": "api-operator", "note": "Continue from API test."},
        )
        detail_response = client.get(f"/automation-runs/{run_id}/detail")

        assert skip_response.status_code == 200
        assert skip_response.json()["checkpoint"]["status"] == "skipped"
        assert resume_response.status_code == 200
        assert resume_response.json()["run"]["status"] == "awaiting_operator_review"
        assert len(detail_response.json()["checkpoints"]) == 2
        assert detail_response.json()["checkpoints"][1]["step_type"] == "review_before_submit"

    def test_block_checkpoint_via_api(self, client: TestClient) -> None:
        execute_response = client.post(
            f"/submission-drafts/{client.draft_id}/execute",  # type: ignore[attr-defined]
            json={"draft_id": client.draft_id, "plan_id": client.plan_id},  # type: ignore[attr-defined]
        )
        run_id = execute_response.json()["run"]["run_id"]
        checkpoint_id = client.get(f"/automation-runs/{run_id}/checkpoints").json()["checkpoints"][0]["checkpoint_id"]

        block_response = client.post(
            f"/automation-runs/{run_id}/checkpoints/{checkpoint_id}/block",
            json={
                "operator_id": "api-operator",
                "decision_note": "Stop here.",
                "block_reason": "Unexpected target state.",
            },
        )
        detail_response = client.get(f"/automation-runs/{run_id}/detail")

        assert block_response.status_code == 200
        assert block_response.json()["run"]["status"] == "blocked"
        assert detail_response.json()["run"]["paused_run"] is None

    def test_get_nonexistent_run_returns_error(self, client: TestClient) -> None:
        response = client.get("/automation-runs/missing-run/detail")

        assert response.status_code == 404