from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import OpportunityStatus, SourceConnectorType, UserRole


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Invalid email")
    return email


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str

    _normalize_email = field_validator("email")(normalize_email)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8)
    full_name: str | None = None
    role: UserRole = UserRole.VIEWER

    _normalize_email = field_validator("email")(normalize_email)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    _normalize_email = field_validator("email")(normalize_email)


class UserRead(OrmModel):
    id: int
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool


class KeywordSynonymRead(OrmModel):
    id: int
    term: str


class KeywordCategoryBase(BaseModel):
    name: str
    description: str | None = None
    threshold: float = 0
    is_active: bool = True
    strategic_tags: list[str] = Field(default_factory=list)


class KeywordCategoryCreate(KeywordCategoryBase):
    pass


class KeywordCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    threshold: float | None = None
    is_active: bool | None = None
    strategic_tags: list[str] | None = None


class KeywordCategoryRead(KeywordCategoryBase, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class KeywordBase(BaseModel):
    category_id: int
    term: str
    weight: float = 3
    is_active: bool = True
    exclusions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)


class KeywordCreate(KeywordBase):
    pass


class KeywordUpdate(BaseModel):
    category_id: int | None = None
    term: str | None = None
    weight: float | None = None
    is_active: bool | None = None
    exclusions: list[str] | None = None
    tags: list[str] | None = None
    synonyms: list[str] | None = None


class KeywordRead(OrmModel):
    id: int
    category_id: int
    term: str
    weight: float
    is_active: bool
    exclusions: list[str]
    tags: list[str]
    synonyms: list[KeywordSynonymRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SourceBase(BaseModel):
    name: str
    connector_type: SourceConnectorType
    url: str | None = None
    api_endpoint: str | None = None
    frequency_minutes: int = 1440
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    connector_type: SourceConnectorType | None = None
    url: str | None = None
    api_endpoint: str | None = None
    frequency_minutes: int | None = None
    is_active: bool | None = None
    config: dict[str, Any] | None = None


class SourceRead(SourceBase, OrmModel):
    id: int
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceRunRead(OrmModel):
    id: int
    source_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    fetched_count: int
    created_count: int
    error_message: str | None
    logs: list[dict[str, Any]]


class SourceRunLaunchResponse(BaseModel):
    task_id: str
    source_id: int
    status: str


class SourceRunTaskResponse(BaseModel):
    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class AgentRunRead(OrmModel):
    id: int
    agent_id: int
    status: str
    task_name: str
    target_type: str | None
    target_id: str | None
    started_at: datetime
    finished_at: datetime | None
    input_count: int
    output_count: int
    success_count: int
    failure_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str | None
    error_message: str | None
    logs: list[dict[str, Any]]
    metadata_json: dict[str, Any]


class AgentStats(BaseModel):
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    success_rate: float = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    orchestrated_tokens: int = 0
    orchestrated_input_tokens: int = 0
    orchestrated_output_tokens: int = 0
    last_status: str | None = None


class AgentRead(OrmModel):
    id: int
    slug: str
    name: str
    description: str
    task: str
    is_active: bool
    sort_order: int
    config: dict[str, Any]
    last_run_at: datetime | None
    schedule_enabled: bool
    schedule_frequency: str
    schedule_interval: int
    schedule_time: str
    schedule_weekday: int
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    stats: AgentStats = Field(default_factory=AgentStats)
    recent_runs: list[AgentRunRead] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    is_active: bool | None = None
    config: dict[str, Any] | None = None
    schedule_enabled: bool | None = None
    schedule_frequency: str | None = None
    schedule_interval: int | None = None
    schedule_time: str | None = None
    schedule_weekday: int | None = None


class AgentRunRequest(BaseModel):
    config_override: dict[str, Any] = Field(default_factory=dict)


class OpportunityImport(BaseModel):
    source: str = "manual"
    source_url: str | None = None
    source_reference: str | None = None
    title: str
    buyer: str | None = None
    description: str
    location: str | None = None
    deadline: datetime | None = None
    publication_date: datetime | None = None
    cpv: list[str] = Field(default_factory=list)


class OpportunityStatusUpdate(BaseModel):
    status: OpportunityStatus
    origin: str | None = Field(default=None, max_length=120)


class OpportunityAuditRead(BaseModel):
    id: int
    action: str
    action_label: str
    actor_user_id: int | None = None
    actor_label: str
    actor_role: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    transition: dict[str, Any] | None = None
    created_at: datetime


class OpportunityBatchAnalyzeRequest(BaseModel):
    opportunity_ids: list[int] = Field(default_factory=list, min_length=1, max_length=50)


class OpportunityRead(OrmModel):
    id: int
    source: str
    source_url: str | None
    source_reference: str | None
    title: str
    buyer: str | None
    buyer_type: str | None
    object: str | None
    description: str | None
    lots: list[dict[str, Any]]
    cpv: list[str]
    procedure: str | None
    market_type: str | None
    location: str | None
    publication_date: datetime | None
    deadline: datetime | None
    estimated_budget: float | None
    status: OpportunityStatus
    global_score: float
    score_by_family: dict[str, float]
    ai_summary: str | None
    ai_report: dict[str, Any] | None
    keyword_traces: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class OpportunityListItem(OrmModel):
    id: int
    source: str
    source_url: str | None
    source_reference: str | None
    title: str
    buyer: str | None
    object: str | None
    description: str | None
    location: str | None
    publication_date: datetime | None
    deadline: datetime | None
    status: OpportunityStatus
    global_score: float
    ai_summary: str | None
    created_at: datetime
    updated_at: datetime


class OpportunityBatchAnalyzeResponse(BaseModel):
    run_id: int | None = None
    analyzed_count: int
    failed_count: int
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    opportunities: list[OpportunityRead]
    errors: list[dict[str, Any]] = Field(default_factory=list)


class OpportunitySearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    run_id: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    items: list[OpportunityListItem]
    highlights: dict[int, list[str]] = Field(default_factory=dict)


class OpportunityListResponse(BaseModel):
    items: list[OpportunityListItem]
    total: int


class AnalysisResponse(BaseModel):
    opportunity: OpportunityRead
    score: dict[str, Any]
    report: dict[str, Any]


class OpportunityDocumentRead(OrmModel):
    id: int
    opportunity_id: int
    filename: str
    content_type: str | None
    content_hash: str
    created_at: datetime


class AiReportRead(OrmModel):
    id: int
    opportunity_id: int
    model: str
    report_json: dict[str, Any]
    html: str | None
    raw_model_json: dict[str, Any]
    confidence_score: float
    human_review_required: bool
    created_at: datetime


class NotificationRead(OrmModel):
    id: int
    type: str
    title: str
    message: str
    opportunity_id: int | None
    is_read: bool
    payload: dict[str, Any]
    created_at: datetime


class DashboardTokenUsage(BaseModel):
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    run_count: int = 0
    orchestration_run_count: int = 0
    orchestrated_tokens: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_run_at: datetime | None = None
    last_model: str | None = None


class DashboardMapOpportunity(BaseModel):
    id: int
    title: str
    buyer: str | None = None
    status: str
    global_score: float
    deadline: datetime | None = None


class DashboardMapPoint(BaseModel):
    key: str
    department_code: str | None = None
    department_name: str
    label: str
    latitude: float | None = None
    longitude: float | None = None
    x: float | None = None
    y: float | None = None
    is_overseas: bool = False
    count: int
    highest_score: float
    status_counts: dict[str, int] = Field(default_factory=dict)
    deadline_counts: dict[str, int] = Field(default_factory=dict)
    search_text: str | None = None
    opportunities: list[DashboardMapOpportunity] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    total_opportunities: int
    rejected_opportunities: int = 0
    high_relevance: int
    to_analyze: int
    analyzed_opportunities: int
    relevant_opportunities: int
    study_opportunities: int
    deadlines_soon: int
    active_sources: int
    token_usage: DashboardTokenUsage
    score_buckets: dict[str, int]
    status_counts: dict[str, int]
    latest_opportunities: list[OpportunityListItem]
    urgent_opportunities: list[OpportunityListItem]
    map_points: list[DashboardMapPoint] = Field(default_factory=list)


class FrontAnalysisRequest(BaseModel):
    analysis_date: date | None = None
    keywords: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    days_back: int = Field(default=14, ge=1, le=90)
    limit: int = Field(default=50, ge=1, le=1000)
    min_live_score: float = Field(default=25, ge=0, le=100)


class RejectedCandidate(BaseModel):
    source: str
    source_reference: str | None = None
    opportunity_id: int | None = None
    title: str | None = None
    score: float = 0
    reason: str | None = None


class FrontAnalysisResponse(BaseModel):
    analysis_date: date
    days_back: int
    status: str
    fetched_count: int
    new_count: int
    already_known_count: int
    skipped_low_score_count: int
    analyzed_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    run_id: int
    new_opportunities: list[OpportunityListItem]
    rejected_candidates: list[RejectedCandidate]


class FrontAnalysisLaunchResponse(BaseModel):
    task_id: str
    status: str


class FrontAnalysisTaskResponse(BaseModel):
    task_id: str
    status: str
    result: FrontAnalysisResponse | None = None
    error: str | None = None
