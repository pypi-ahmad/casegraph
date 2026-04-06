"""CaseGraph API — FastAPI application entry point."""

import platform
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ingestion.extractors import ocr_runtime_available
from app.audit.router import router as audit_router
from app.cases.router import router as cases_router
from app.ingestion.router import router as ingestion_router
from app.knowledge.dependencies import embedding_available, vector_store_available
from app.knowledge.router import router as knowledge_router
from app.providers.router import router as providers_router
from app.runtime.router import router as runtime_router
from app.topology.router import router as topology_router
from app.evals.router import router as evals_router
from app.automation.router import router as automation_router
from app.tasks.router import router as tasks_router
from app.rag.router import router as rag_router
from app.review.router import router as review_router
from app.extraction.router import router as extraction_router
from app.domains.router import router as domains_router
from app.operator_review.router import router as operator_review_router
from app.packets.router import router as packets_router
from app.readiness.router import router as readiness_router
from app.submissions.router import router as submissions_router
from app.communications.router import router as communications_router
from app.execution.router import router as execution_router
from app.workflow_packs.router import router as workflow_packs_router
from app.human_validation.router import router as human_validation_router
from app.reviewed_handoff.router import router as reviewed_handoff_router
from app.reviewed_release.router import router as reviewed_release_router
from app.work_management.router import router as work_management_router
from app.target_packs.router import router as target_packs_router
from app.extraction.service import langextract_available
from app.observability.langfuse_client import get_langfuse, langfuse_configured, shutdown_langfuse
from app.observability.middleware import RequestLoggingMiddleware
from app.persistence.database import init_database
from app.status import get_platform_status


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_database()
    # Startup — initialise Langfuse if configured
    get_langfuse()
    yield
    # Shutdown — flush traces
    shutdown_langfuse()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(ingestion_router)
app.include_router(cases_router)
app.include_router(audit_router)
app.include_router(knowledge_router)
app.include_router(providers_router)
app.include_router(runtime_router)
app.include_router(topology_router)
app.include_router(evals_router)
app.include_router(automation_router)
app.include_router(tasks_router)
app.include_router(rag_router)
app.include_router(review_router)
app.include_router(extraction_router)
app.include_router(domains_router)
app.include_router(readiness_router)
app.include_router(operator_review_router)
app.include_router(packets_router)
app.include_router(submissions_router)
app.include_router(communications_router)
app.include_router(execution_router)
app.include_router(workflow_packs_router)
app.include_router(human_validation_router)
app.include_router(reviewed_handoff_router)
app.include_router(reviewed_release_router)
app.include_router(work_management_router)
app.include_router(target_packs_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status/modules")
async def status_modules() -> dict:
    return get_platform_status().model_dump()


@app.get("/info")
async def info() -> dict[str, object]:
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "python_version": platform.python_version(),
        "capabilities": {
            "byok_provider_discovery": True,
            "agents": True,
            "document_ingestion": True,
            "retrieval": embedding_available() and vector_store_available(),
            "ocr": ocr_runtime_available(),
            "evals": True,
            "langfuse": langfuse_configured(),
            "automation": True,
            "cases": True,
            "task_execution": True,
            "rag_task_execution": True,
            "document_review": True,
            "schema_extraction": True,
            "langextract": langextract_available(),
            "domain_packs": True,
            "case_readiness": True,
            "operator_review": True,
            "packet_assembly": True,
            "submission_drafts": True,
            "communication_drafts": True,
            "automation_execution": True,
            "audit_traceability": True,
            "human_validation": True,
            "reviewed_handoff": True,
            "reviewed_release": True,
            "work_management": True,
            "target_packs": True,
        },
    }
