"""Shared test fixtures for the CaseGraph API test suite.

Provides a SQLite-backed session, a full-app TestClient with all routers,
and helpers for test-data construction.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Import every SQLModel subclass so metadata.create_all registers all tables.
import app.audit.models  # noqa: F401
import app.cases.models  # noqa: F401
import app.communications.models  # noqa: F401
import app.evals.models  # noqa: F401
import app.execution.models  # noqa: F401
import app.extraction.models  # noqa: F401
import app.human_validation.models  # noqa: F401
import app.ingestion.models  # noqa: F401
import app.operator_review.models  # noqa: F401
import app.packets.models  # noqa: F401
import app.readiness.models  # noqa: F401
import app.review.models  # noqa: F401
import app.review.annotation_models  # noqa: F401
import app.reviewed_handoff.models  # noqa: F401
import app.reviewed_release.models  # noqa: F401
import app.submissions.models  # noqa: F401
import app.tasks.models  # noqa: F401
import app.work_management.models  # noqa: F401
import app.workflow_packs.models  # noqa: F401

from app.main import app as real_app
from app.persistence.database import get_session


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    """In-memory SQLite session with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture()
def client(session: Session) -> Generator[TestClient, None, None]:
    """Full-app TestClient with session override — all routers mounted."""

    def _override_session() -> Generator[Session, None, None]:
        yield session

    real_app.dependency_overrides[get_session] = _override_session
    with TestClient(real_app, raise_server_exceptions=False) as tc:
        yield tc
    real_app.dependency_overrides.clear()
