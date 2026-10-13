from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationStatus(str, Enum):
    DRAFT = "draft"
    REQUIREMENTS_REVIEW = "requirements_review"
    ANALYSED = "analysed"
    STALE = "stale"


class DocumentKind(str, Enum):
    REQUIREMENTS = "requirements"
    PROPOSAL = "proposal"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    READY = "ready"
    ERROR = "error"


class RequirementOrigin(str, Enum):
    EXTRACTED = "extracted"
    USER = "user"


class JobKind(str, Enum):
    EXTRACT_REQUIREMENTS = "extract_requirements"
    ANALYSE = "analyse"


class JobStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    ANALYSING = "analysing"
    DONE = "done"
    FAILED = "failed"


class FindingStatus(str, Enum):
    COMPLIANT = "Compliant"
    PARTIALLY_COMPLIANT = "Partially compliant"
    NON_COMPLIANT = "Non-compliant"
    NOT_EVIDENCED = "Not evidenced"


# --- Request models ---

class EvaluationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    vendor_names: List[str] = Field(..., min_length=2, max_length=3)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Title cannot be empty")
        return s

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Category cannot be empty")
        return s

    @field_validator("vendor_names")
    @classmethod
    def validate_vendors(cls, v: List[str]) -> List[str]:
        cleaned = [name.strip() for name in v if name.strip()]
        if len(cleaned) < 2 or len(cleaned) > 3:
            raise ValueError("Must provide 2 or 3 non-empty vendor names")
        lower_names = [name.lower() for name in cleaned]
        if len(set(lower_names)) != len(cleaned):
            raise ValueError("Vendor names must be unique")
        return cleaned


class EvaluationUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    status: Optional[EvaluationStatus] = None


class ExtractRequirementsRequest(BaseModel):
    confirm_replace: bool = False


# --- Response models ---

class VendorResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    name: str
    position: int

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    vendor_id: Optional[uuid.UUID] = None
    kind: DocumentKind
    filename: str
    mime: str
    size_bytes: int
    storage_key: str
    page_count: Optional[int] = None
    status: DocumentStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequirementItem(BaseModel):
    id: Optional[uuid.UUID] = None
    code: str
    text: str
    category: str
    mandatory: bool = False
    acceptance: str
    source_document_id: Optional[uuid.UUID] = None
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    position: int = 0
    origin: RequirementOrigin = RequirementOrigin.USER

    model_config = ConfigDict(from_attributes=True)


class AnalysisJobResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    kind: JobKind
    status: JobStatus
    step_label: str
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationKPIs(BaseModel):
    total: int
    needs_action: int
    analysed: int
    open_clarifications: int


class EvaluationSummaryResponse(BaseModel):
    id: uuid.UUID
    title: str
    name: str  # alias for frontend mock compatibility
    name_short: Optional[str] = None
    category: str
    status: EvaluationStatus
    lifecycle_status: str  # Capitalized display status for frontend
    vendors_count: int
    total_requirements: int
    mandatory_requirements: int
    updated_at: datetime
    created_at: datetime
    latest_job: Optional[AnalysisJobResponse] = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationsListResponse(BaseModel):
    evaluations: List[EvaluationSummaryResponse]
    kpis: EvaluationKPIs


class EvaluationDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    status: EvaluationStatus
    criteria_snapshot: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime
    vendors: List[VendorResponse]
    documents: List[DocumentResponse]
    requirements_count: int
    latest_job: Optional[AnalysisJobResponse] = None

    model_config = ConfigDict(from_attributes=True)


class FindingEvidence(BaseModel):
    quote: str
    highlight: Optional[str] = None
    document: str
    page: Optional[int] = None
    section: Optional[str] = None


class FindingResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    vendor_id: uuid.UUID
    requirement_id: Optional[uuid.UUID] = None
    criterion_key: Optional[str] = None
    status: str
    needs_review: bool
    inferred: bool
    confidence: str
    evidence_quote: Optional[str] = None
    evidence_document_id: Optional[uuid.UUID] = None
    evidence_page: Optional[int] = None
    evidence_section: Optional[str] = None
    evidence: Optional[FindingEvidence] = None
    risk_types: List[str] = []
    severity: Optional[str] = None
    clarification_question: Optional[str] = None
    fact_or_inference: str

    model_config = ConfigDict(from_attributes=True)


class CostBreakdownResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    vendor_id: uuid.UUID
    monthly_base: float
    gst_18: float
    monthly_total: float
    included: List[str]
    excluded: List[str]
    optional: List[str]
    unknown: List[str]

    model_config = ConfigDict(from_attributes=True)


class ClarificationResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    vendor_id: uuid.UUID
    question: str
    answered: bool

    class Config:
        from_attributes = True


# Scoring response details
class CriterionScoreCell(BaseModel):
    score: Optional[float] = None
    points: Optional[float] = None  # display: rounded half-up to 1 decimal
    raw_points: Optional[float] = None  # exact calculation


class CriterionScoreRow(BaseModel):
    criterion: str
    criterion_key: str
    weight: int
    vendor_scores: Dict[str, CriterionScoreCell]


class VendorTotalResult(BaseModel):
    score: Optional[int] = None  # display: whole number
    total: Optional[int] = None  # alias
    raw_score: Optional[float] = None  # exact
    raw_total: Optional[float] = None  # exact
    incomplete: bool = False


class VendorResultItem(BaseModel):
    id: str
    name: str
    tag: Optional[str] = None
    score: Optional[int] = None  # display
    raw_score: Optional[float] = None  # exact
    mandatory_failures: int
    monthly_base_inr: float
    gst_rate: float
    monthly_gst_inr: float
    monthly_total_inr: float
    unknown_costs_count: int
    needs_review_count: int


class EvaluationResultsResponse(BaseModel):
    status: str
    vendors: List[VendorResultItem]
    findings: List[FindingResponse]
    costs: List[CostBreakdownResponse]
    clarifications: Dict[str, List[str]]
    scoring: List[CriterionScoreRow]
    vendor_totals: Dict[str, VendorTotalResult]
    recommendation: Optional[Dict[str, Any]] = None
