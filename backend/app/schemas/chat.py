from enum import Enum
from typing import Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field


class ChatAction(str, Enum):
    START = "start"
    START_EXTRACTION = "start_extraction"
    RUN_ANALYSIS = "run_analysis"
    REVIEW_FIRST = "review_first"
    TRY_AGAIN = "try_again"
    CONFIRM_RERUN = "confirm_rerun"


class ChatCollectedDetails(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    vendor_names: Optional[List[str]] = Field(default_factory=list)


class ChatChoiceOption(BaseModel):
    action: str
    label: str
    link: Optional[str] = None


class ChatExpect(BaseModel):
    kind: Literal["text", "file", "choice"]
    file_kind: Optional[Literal["requirements", "proposal"]] = None
    vendor_id: Optional[uuid.UUID] = None
    vendor_name: Optional[str] = None
    options: Optional[List[ChatChoiceOption]] = None


class ChatJobInfo(BaseModel):
    id: Optional[uuid.UUID] = None
    status: str
    step_label: Optional[str] = None


class ChatVendorSummary(BaseModel):
    name: str
    total: int
    mandatory_met: str
    mandatory_failures: int
    mandatory_to_check: int
    monthly_total: str
    needs_review_count: int


class ChatSummary(BaseModel):
    vendors: List[ChatVendorSummary]
    outcome: str
    recommended_vendor: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)


class ChatTurnRequest(BaseModel):
    evaluation_id: Optional[uuid.UUID] = None
    message: Optional[str] = Field(default=None, max_length=1000)
    action: Optional[ChatAction] = None
    collected: Optional[ChatCollectedDetails] = None


class ChatTurnResponse(BaseModel):
    reply: str
    state: str
    evaluation_id: Optional[uuid.UUID] = None
    collected: Optional[ChatCollectedDetails] = None
    expect: Optional[ChatExpect] = None
    job: Optional[ChatJobInfo] = None
    summary: Optional[ChatSummary] = None
    links: Optional[Dict[str, str]] = None
