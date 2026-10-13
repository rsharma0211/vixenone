from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.company import EvaluationLocationResponse


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
    location_id: Optional[uuid.UUID] = None
    vendor_names: Optional[List[str]] = Field(default_factory=list)

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
    def validate_vendors(cls, v: Optional[List[str]]) -> List[str]:
        if v is None:
            return []
        if len(v) > 3:
            raise ValueError("An evaluation can have at most 3 vendors.")
        cleaned: List[str] = []
        for name in v:
            s = name.strip()
            if not s:
                raise ValueError("Vendor name cannot be empty")
            if len(s) > 80:
                raise ValueError("Vendor name cannot exceed 80 characters")
            cleaned.append(s)
        lower_names = [name.lower() for name in cleaned]
        if len(set(lower_names)) != len(cleaned):
            raise ValueError("Vendor names must be unique")
        return cleaned


class VendorCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Vendor name cannot be empty")
        if len(s) > 80:
            raise ValueError("Vendor name cannot exceed 80 characters")
        return s


class VendorUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Vendor name cannot be empty")
        if len(s) > 80:
            raise ValueError("Vendor name cannot exceed 80 characters")
        return s


class EvaluationUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    status: Optional[EvaluationStatus] = None
    location_id: Optional[uuid.UUID] = None


class ExtractRequirementsRequest(BaseModel):
    confirm_replace: bool = False


class AnalyseEvaluationRequest(BaseModel):
    confirm_rerun: bool = False


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

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Requirement code cannot be empty")
        if len(stripped) > 20:
            raise ValueError("Requirement code cannot exceed 20 characters")
        return stripped

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Requirement text cannot be empty")
        if len(stripped) > 1000:
            raise ValueError("Requirement text cannot exceed 1000 characters")
        return stripped

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) > 80:
            raise ValueError("Requirement category cannot exceed 80 characters")
        return stripped

    @field_validator("acceptance")
    @classmethod
    def validate_acceptance(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) > 1000:
            raise ValueError("Requirement acceptance cannot exceed 1000 characters")
        return stripped


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
    location: Optional[EvaluationLocationResponse] = None
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
    location: Optional[EvaluationLocationResponse] = None
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
    monthly_base: Optional[float] = None
    gst_18: Optional[float] = None
    monthly_total: Optional[float] = None
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
    display_total: Optional[int] = None  # display alias
    raw_score: Optional[float] = None  # exact
    exact_total: Optional[float] = None  # exact alias
    mandatory_met: int = 0
    mandatory_total: int = 0
    mandatory_failures: int = 0
    mandatory_not_evidenced: int = 0
    mandatory_needs_review: int = 0
    monthly_base_inr: Optional[float] = None
    gst_rate: float = 0.18
    monthly_gst_inr: Optional[float] = None
    monthly_total_inr: Optional[float] = None
    unknown_costs_count: int = 0
    needs_review_count: int = 0
    criterion_scores: Dict[str, CriterionScoreCell] = Field(default_factory=dict)


class RecommendationResponse(BaseModel):
    state: str  # recommended | insufficient
    vendor_id: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)


class EvaluationResultsResponse(BaseModel):
    status: str
    company_name: Optional[str] = None
    criteria_snapshot: Optional[List[Dict[str, Any]]] = None
    vendors: List[VendorResultItem]
    findings: List[FindingResponse]
    costs: List[CostBreakdownResponse]
    clarifications: Dict[str, List[str]]
    scoring: List[CriterionScoreRow]
    vendor_totals: Dict[str, VendorTotalResult]
    recommendation: Optional[RecommendationResponse] = None
