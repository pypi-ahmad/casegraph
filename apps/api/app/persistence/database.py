"""Typed persistence helpers for the CaseGraph API."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def isoformat_utc(value: datetime | None) -> str:
    """Convert a datetime to a Z-suffixed UTC ISO string.

    Returns an empty string for ``None`` values.  This is the canonical
    helper that replaces the per-service ``_iso`` / ``_isoformat`` /
    ``_iso_now`` copies.
    """
    if value is None:
        return ""
    normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sqlite_connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _sqlite_database_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url[len(prefix) :])


def _ensure_database_parent(database_url: str) -> None:
    db_path = _sqlite_database_path(database_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)


def _build_engine(database_url: str, *, echo: bool) -> Engine:
    _ensure_database_parent(database_url)
    return create_engine(
        database_url,
        echo=echo,
        connect_args=_sqlite_connect_args(database_url),
    )


_engine = _build_engine(settings.database_url, echo=settings.database_echo)


def configure_engine(database_url: str, *, echo: bool = False) -> None:
    global _engine
    _engine = _build_engine(database_url, echo=echo)


def get_engine() -> Engine:
    return _engine


def _ensure_sqlite_document_registry_compatibility() -> None:
    if _engine.url.get_backend_name() != "sqlite":
        return

    inspector = inspect(_engine)
    if "documents" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("documents")}
    statements: list[str] = []

    if "page_count" not in existing_columns:
        statements.append(
            "ALTER TABLE documents ADD COLUMN page_count INTEGER NOT NULL DEFAULT 0"
        )
    if "text_block_count" not in existing_columns:
        statements.append(
            "ALTER TABLE documents ADD COLUMN text_block_count INTEGER NOT NULL DEFAULT 0"
        )
    if "geometry_present" not in existing_columns:
        statements.append(
            "ALTER TABLE documents ADD COLUMN geometry_present BOOLEAN NOT NULL DEFAULT 0"
        )
    if "geometry_sources_json" not in existing_columns:
        statements.append(
            "ALTER TABLE documents ADD COLUMN geometry_sources_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "source_file_path" not in existing_columns:
        statements.append(
            "ALTER TABLE documents ADD COLUMN source_file_path TEXT"
        )
    if "extraction_output_json" not in existing_columns:
        statements.append(
            "ALTER TABLE documents ADD COLUMN extraction_output_json TEXT"
        )

    if not statements:
        return

    with _engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_sqlite_case_domain_columns() -> None:
    """Add domain pack and operator-stage columns to existing cases table if missing."""
    if _engine.url.get_backend_name() != "sqlite":
        return

    db_inspector = inspect(_engine)
    if "cases" not in db_inspector.get_table_names():
        return

    existing = {col["name"] for col in db_inspector.get_columns("cases")}
    stmts: list[str] = []

    if "domain_pack_id" not in existing:
        stmts.append("ALTER TABLE cases ADD COLUMN domain_pack_id TEXT")
    if "current_stage" not in existing:
        stmts.append("ALTER TABLE cases ADD COLUMN current_stage TEXT NOT NULL DEFAULT 'intake'")
    if "jurisdiction" not in existing:
        stmts.append("ALTER TABLE cases ADD COLUMN jurisdiction TEXT")
    if "case_type_id" not in existing:
        stmts.append("ALTER TABLE cases ADD COLUMN case_type_id TEXT")
    if "domain_category" not in existing:
        stmts.append("ALTER TABLE cases ADD COLUMN domain_category TEXT")

    if stmts:
        with _engine.begin() as connection:
            for stmt in stmts:
                connection.execute(text(stmt))


def _ensure_sqlite_submission_plan_step_columns() -> None:
    if _engine.url.get_backend_name() != "sqlite":
        return

    db_inspector = inspect(_engine)
    if "submission_automation_plan_steps" not in db_inspector.get_table_names():
        return

    existing = {col["name"] for col in db_inspector.get_columns("submission_automation_plan_steps")}
    stmts: list[str] = []

    if "execution_mode" not in existing:
        stmts.append(
            "ALTER TABLE submission_automation_plan_steps ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'blocked'"
        )
    if "checkpoint_required" not in existing:
        stmts.append(
            "ALTER TABLE submission_automation_plan_steps ADD COLUMN checkpoint_required BOOLEAN NOT NULL DEFAULT 0"
        )
    if "checkpoint_reason" not in existing:
        stmts.append(
            "ALTER TABLE submission_automation_plan_steps ADD COLUMN checkpoint_reason TEXT NOT NULL DEFAULT ''"
        )
    if "fallback_hint_json" not in existing:
        stmts.append(
            "ALTER TABLE submission_automation_plan_steps ADD COLUMN fallback_hint_json TEXT NOT NULL DEFAULT '{}'"
        )

    if stmts:
        with _engine.begin() as connection:
            for stmt in stmts:
                connection.execute(text(stmt))


def _ensure_sqlite_automation_run_columns() -> None:
    if _engine.url.get_backend_name() != "sqlite":
        return

    db_inspector = inspect(_engine)
    if "automation_runs" not in db_inspector.get_table_names():
        return

    existing = {col["name"] for col in db_inspector.get_columns("automation_runs")}
    stmts: list[str] = []

    if "paused_run_json" not in existing:
        stmts.append("ALTER TABLE automation_runs ADD COLUMN paused_run_json TEXT")
    if "source_mode" not in existing:
        stmts.append(
            "ALTER TABLE automation_runs ADD COLUMN source_mode TEXT NOT NULL DEFAULT 'live_case_state'"
        )
    if "source_reviewed_snapshot_id" not in existing:
        stmts.append(
            "ALTER TABLE automation_runs ADD COLUMN source_reviewed_snapshot_id TEXT NOT NULL DEFAULT ''"
        )

    if stmts:
        with _engine.begin() as connection:
            for stmt in stmts:
                connection.execute(text(stmt))


def _ensure_sqlite_reviewed_handoff_columns() -> None:
    if _engine.url.get_backend_name() != "sqlite":
        return

    db_inspector = inspect(_engine)

    if "case_packets" in db_inspector.get_table_names():
        existing = {col["name"] for col in db_inspector.get_columns("case_packets")}
        stmts: list[str] = []
        if "source_mode" not in existing:
            stmts.append(
                "ALTER TABLE case_packets ADD COLUMN source_mode TEXT NOT NULL DEFAULT 'live_case_state'"
            )
        if "source_reviewed_snapshot_id" not in existing:
            stmts.append(
                "ALTER TABLE case_packets ADD COLUMN source_reviewed_snapshot_id TEXT NOT NULL DEFAULT ''"
            )
        if stmts:
            with _engine.begin() as connection:
                for stmt in stmts:
                    connection.execute(text(stmt))

    if "submission_drafts" in db_inspector.get_table_names():
        existing = {col["name"] for col in db_inspector.get_columns("submission_drafts")}
        stmts = []
        if "source_mode" not in existing:
            stmts.append(
                "ALTER TABLE submission_drafts ADD COLUMN source_mode TEXT NOT NULL DEFAULT 'live_case_state'"
            )
        if "source_reviewed_snapshot_id" not in existing:
            stmts.append(
                "ALTER TABLE submission_drafts ADD COLUMN source_reviewed_snapshot_id TEXT NOT NULL DEFAULT ''"
            )
        if stmts:
            with _engine.begin() as connection:
                for stmt in stmts:
                    connection.execute(text(stmt))

    if "submission_automation_plans" in db_inspector.get_table_names():
        existing = {col["name"] for col in db_inspector.get_columns("submission_automation_plans")}
        stmts = []
        if "source_mode" not in existing:
            stmts.append(
                "ALTER TABLE submission_automation_plans ADD COLUMN source_mode TEXT NOT NULL DEFAULT 'live_case_state'"
            )
        if "source_reviewed_snapshot_id" not in existing:
            stmts.append(
                "ALTER TABLE submission_automation_plans ADD COLUMN source_reviewed_snapshot_id TEXT NOT NULL DEFAULT ''"
            )
        if stmts:
            with _engine.begin() as connection:
                for stmt in stmts:
                    connection.execute(text(stmt))


def _ensure_sqlite_reviewed_release_columns() -> None:
    if _engine.url.get_backend_name() != "sqlite":
        return

    db_inspector = inspect(_engine)
    if "release_bundles" not in db_inspector.get_table_names():
        return

    existing = {col["name"] for col in db_inspector.get_columns("release_bundles")}
    stmts: list[str] = []

    if "signoff_id" not in existing:
        stmts.append("ALTER TABLE release_bundles ADD COLUMN signoff_id TEXT NOT NULL DEFAULT ''")

    if stmts:
        with _engine.begin() as connection:
            for stmt in stmts:
                connection.execute(text(stmt))


def init_database() -> None:
    import app.audit.models  # noqa: F401
    import app.cases.models  # noqa: F401
    import app.ingestion.models  # noqa: F401
    import app.review.models  # noqa: F401
    import app.extraction.models  # noqa: F401
    import app.tasks.models  # noqa: F401
    import app.readiness.models  # noqa: F401
    import app.operator_review.models  # noqa: F401
    import app.packets.models  # noqa: F401
    import app.submissions.models  # noqa: F401
    import app.communications.models  # noqa: F401
    import app.execution.models  # noqa: F401
    import app.workflow_packs.models  # noqa: F401
    import app.human_validation.models  # noqa: F401
    import app.reviewed_handoff.models  # noqa: F401
    import app.reviewed_release.models  # noqa: F401
    import app.work_management.models  # noqa: F401

    SQLModel.metadata.create_all(_engine)
    _ensure_sqlite_document_registry_compatibility()
    _ensure_sqlite_case_domain_columns()
    _ensure_sqlite_submission_plan_step_columns()
    _ensure_sqlite_automation_run_columns()
    _ensure_sqlite_reviewed_handoff_columns()
    _ensure_sqlite_reviewed_release_columns()


def get_session() -> Generator[Session, None, None]:
    with Session(_engine) as session:
        yield session