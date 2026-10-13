from datetime import datetime
from enum import Enum
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CriterionKind(str, Enum):
    BUILTIN = "builtin"
    CUSTOM = "custom"


BUILTIN_CRITERIA_DEFAULTS = {
    "mandatory_compliance": {
        "name": "Mandatory compliance",
        "guidance": "Share of mandatory requirements the vendor meets with evidence. Any mandatory failure is also shown separately.",
        "default_weight": 35,
        "position": 0,
    },
    "service_coverage": {
        "name": "Service coverage",
        "guidance": "How fully the proposal covers the required services, frequencies and staffing.",
        "default_weight": 20,
        "position": 1,
    },
    "cost_comparability": {
        "name": "Cost comparability",
        "guidance": "How clearly and completely costs are stated: base, GST, inclusions, exclusions and unknowns.",
        "default_weight": 20,
        "position": 2,
    },
    "sla_operational": {
        "name": "SLA / operational",
        "guidance": "Response times, supervision, reporting and penalties stated in the proposal.",
        "default_weight": 15,
        "position": 3,
    },
    "unresolved_risks": {
        "name": "Unresolved risks",
        "guidance": "Fewer exclusions, ambiguities, contradictions and unknown costs score higher.",
        "default_weight": 10,
        "position": 4,
    },
}


class EvaluationCriterionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    kind: CriterionKind
    builtin_key: Optional[str] = None
    name: str
    guidance: str
    weight: int
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationCriterionUpdateItem(BaseModel):
    id: Optional[uuid.UUID] = None
    kind: CriterionKind
    builtin_key: Optional[str] = None
    name: str = Field(..., max_length=80)
    guidance: str = Field(..., min_length=20, max_length=1000)
    weight: int = Field(..., ge=0, le=100)
    position: Optional[int] = 0

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Criterion name cannot be empty")
        if len(stripped) > 80:
            raise ValueError("Criterion name cannot exceed 80 characters")
        return stripped

    @field_validator("guidance")
    @classmethod
    def validate_guidance(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 20 or len(stripped) > 1000:
            raise ValueError("Guidance must be between 20 and 1000 characters")
        return stripped


class CriteriaSnapshotItem(BaseModel):
    key: str
    kind: str
    name: str
    guidance: str
    weight: int
