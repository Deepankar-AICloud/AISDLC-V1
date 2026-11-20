"""Database engine and ORM models (SQLite locally; PostgreSQL / Azure SQL in deployment)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entra_oid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), default="")
    display_name: Mapped[str] = mapped_column(String(200), default="")
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def is_shared(self) -> bool:
        return self.entra_oid == "shared:admin"


class GitHubLink(Base):
    """One Entra user <-> one GitHub account, verified by the OAuth connect step."""

    __tablename__ = "github_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    github_id: Mapped[int] = mapped_column(Integer, unique=True)
    github_login: Mapped[str] = mapped_column(String(100), index=True)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Draft(Base):
    """Short-lived preview state (encrypted). Deleted on submit or after DRAFT_TTL_MINUTES."""

    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    payload_enc: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class IntakeRequest(Base):
    __tablename__ = "requests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    repository: Mapped[str] = mapped_column(String(200))
    issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    issue_url: Mapped[str] = mapped_column(String(500), default="")
    overflow_branch: Mapped[str] = mapped_column(String(200), default="")
    overflow_parts_total: Mapped[int] = mapped_column(Integer, default=0)
    overflow_parts_posted: Mapped[int] = mapped_column(Integer, default=0)
    submit_step: Mapped[str] = mapped_column(String(40), default="pending")
    status: Mapped[str] = mapped_column(String(40), default="submitting")
    stage: Mapped[str] = mapped_column(String(40), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    files_meta: Mapped[list[dict]] = mapped_column(JSON, default=list)
    status_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RequestAccessGrant(Base):
    """Bearer access for anonymous request tracking; only the token hash is stored."""

    __tablename__ = "request_access_grants"
    request_id: Mapped[str] = mapped_column(ForeignKey("requests.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("request_id", "github_login"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("requests.id"), index=True)
    github_login: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(40), default="codeowner")


class AuditEntry(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    entra_oid: Mapped[str] = mapped_column(String(64), default="")
    github_login: Mapped[str] = mapped_column(String(100), default="")
    identity: Mapped[str] = mapped_column(String(20))  # "user" | "service" | "portal"
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str] = mapped_column(String(30))
    target_ref: Mapped[str] = mapped_column(String(200))
    github_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20))
    portal_request_id: Mapped[str] = mapped_column(String(40), default="")
    correlation_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    delivery_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Database:
    def __init__(self, url: str) -> None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def _pragma(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()

        self.sessionmaker = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        with self.sessionmaker() as s:
            yield s
