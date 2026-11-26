from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class SourceConnectorType(str, enum.Enum):
    BOAMP_API = "BOAMP_API"
    TED_API = "TED_API"
    WEB_WATCH = "WEB_WATCH"
    RSS = "RSS"
    EMAIL_IMPORT = "EMAIL_IMPORT"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"


class SourceRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AgentRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class OpportunityStatus(str, enum.Enum):
    NEW = "nouveau"
    ANALYZED = "analyse"
    TO_QUALIFY = "a_qualifier"
    RELEVANT = "pertinent"
    NOT_RELEVANT = "non_pertinent"
    GO = "go"
    WATCH = "watch"
    NO_GO = "no_go"
    ARCHIVED = "archive"


class NotificationType(str, enum.Enum):
    NEW_OPPORTUNITY = "new_opportunity"
    HIGH_SCORE = "high_score"
    DEADLINE_SOON = "deadline_soon"
    CONNECTOR_ERROR = "connector_error"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    connector_type: Mapped[SourceConnectorType] = mapped_column(Enum(SourceConnectorType, name="source_connector_type"))
    url: Mapped[Optional[str]] = mapped_column(Text)
    api_endpoint: Mapped[Optional[str]] = mapped_column(Text)
    frequency_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    runs: Mapped[list["SourceRun"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceRun(TimestampMixin, Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    status: Mapped[SourceRunStatus] = mapped_column(Enum(SourceRunStatus, name="source_run_status"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    logs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    source: Mapped[Source] = relationship(back_populates="runs")


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    task: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    schedule_frequency: Mapped[str] = mapped_column(String(40), default="manual")
    schedule_interval: Mapped[int] = mapped_column(Integer, default=1)
    schedule_time: Mapped[str] = mapped_column(String(5), default="08:00")
    schedule_weekday: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    runs: Mapped[list["AgentRun"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    status: Mapped[AgentRunStatus] = mapped_column(Enum(AgentRunStatus, name="agent_run_status"))
    task_name: Mapped[str] = mapped_column(String(255))
    target_type: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    input_count: Mapped[int] = mapped_column(Integer, default=0)
    output_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[Optional[str]] = mapped_column(String(120))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    logs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    agent: Mapped[Agent] = relationship(back_populates="runs")


class RawNotice(TimestampMixin, Base):
    __tablename__ = "raw_notices"
    __table_args__ = (UniqueConstraint("source_id", "source_reference", name="uq_raw_notice_source_reference"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("source", "source_reference", name="uq_opportunity_source_reference"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_notice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("raw_notices.id", ondelete="SET NULL"), index=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(Text)
    buyer: Mapped[Optional[str]] = mapped_column(String(512), index=True)
    buyer_type: Mapped[Optional[str]] = mapped_column(String(255))
    object: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    lots: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    cpv: Mapped[list[str]] = mapped_column(JSON, default=list)
    procedure: Mapped[Optional[str]] = mapped_column(String(255))
    market_type: Mapped[Optional[str]] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(512), index=True)
    publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    estimated_budget: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[OpportunityStatus] = mapped_column(Enum(OpportunityStatus, name="opportunity_status"), default=OpportunityStatus.NEW, index=True)
    global_score: Mapped[float] = mapped_column(Float, default=0)
    score_by_family: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    ai_report: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    keyword_traces: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    documents: Mapped[list["OpportunityDocument"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")
    matches: Mapped[list["KeywordMatch"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")
    scores: Mapped[list["OpportunityScore"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")
    reports: Mapped[list["AiReport"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")


class OpportunityDocument(TimestampMixin, Base):
    __tablename__ = "opportunity_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[Optional[str]] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    opportunity: Mapped[Opportunity] = relationship(back_populates="documents")


class DocumentChunk(TimestampMixin, Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunity_documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    opportunity: Mapped[Opportunity] = relationship(back_populates="chunks")


class KeywordCategory(TimestampMixin, Base):
    __tablename__ = "keyword_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    threshold: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    strategic_tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    keywords: Mapped[list["Keyword"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Keyword(TimestampMixin, Base):
    __tablename__ = "keywords"
    __table_args__ = (UniqueConstraint("category_id", "term", name="uq_keyword_category_term"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("keyword_categories.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(512), index=True)
    weight: Mapped[float] = mapped_column(Float, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    exclusions: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    category: Mapped[KeywordCategory] = relationship(back_populates="keywords")
    synonyms: Mapped[list["KeywordSynonym"]] = relationship(back_populates="keyword", cascade="all, delete-orphan")


class KeywordSynonym(TimestampMixin, Base):
    __tablename__ = "keyword_synonyms"
    __table_args__ = (UniqueConstraint("keyword_id", "term", name="uq_keyword_synonym_term"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(512), index=True)

    keyword: Mapped[Keyword] = relationship(back_populates="synonyms")


class KeywordMatch(TimestampMixin, Base):
    __tablename__ = "keyword_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    keyword_id: Mapped[Optional[int]] = mapped_column(ForeignKey("keywords.id", ondelete="SET NULL"), index=True)
    category_name: Mapped[str] = mapped_column(String(255), index=True)
    keyword_term: Mapped[str] = mapped_column(String(512))
    matched_term: Mapped[str] = mapped_column(String(512))
    excerpt: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float)
    match_type: Mapped[str] = mapped_column(String(40))

    opportunity: Mapped[Opportunity] = relationship(back_populates="matches")


class OpportunityScore(TimestampMixin, Base):
    __tablename__ = "opportunity_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    global_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(40))
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    matched_keywords: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    maluses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    opportunity: Mapped[Opportunity] = relationship(back_populates="scores")


class AiReport(TimestampMixin, Base):
    __tablename__ = "ai_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(120), default="heuristic")
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    html: Mapped[Optional[str]] = mapped_column(Text)
    raw_model_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True)

    opportunity: Mapped[Opportunity] = relationship(back_populates="reports")


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, name="notification_type"))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    entity_type: Mapped[str] = mapped_column(String(120), index=True)
    entity_id: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(120))
    before: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    after: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
