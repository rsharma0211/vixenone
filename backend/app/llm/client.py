from abc import ABC, abstractmethod
import asyncio
from enum import Enum
import inspect
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, TypeVar
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

MAX_REQUIREMENTS_SECTION_CHARS = 30_000
MAX_CRITERIA_SECTION_CHARS = 15_000
MAX_PROPOSAL_SECTION_CHARS = 80_000

T = TypeVar("T", bound=BaseModel)


class GeminiClientError(Exception):
    """Raised when Gemini extraction or structured output validation fails."""

    pass


class PageText(BaseModel):
    page_number: int = Field(..., ge=1)
    text: str


class PdfPagesEnvelope(BaseModel):
    pages: List[PageText]


class ExtractedRequirement(BaseModel):
    code: str = ""
    text: str
    category: str
    mandatory: bool
    acceptance: str = ""
    source_page: Optional[int] = None
    source_section: Optional[str] = None


class ParsedEvaluationDetails(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    vendor_names: List[str] = Field(default_factory=list)


class ExtractedRequirementsEnvelope(BaseModel):
    requirements: List[ExtractedRequirement]


class LLMComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_EVIDENCED = "not_evidenced"


class LLMRiskType(str, Enum):
    EXCLUSION = "exclusion"
    OMISSION = "omission"
    AMBIGUITY = "ambiguity"
    CONTRADICTION = "contradiction"
    UNKNOWN_COST = "unknown_cost"


class LLMSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LLMConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def _normalise_enum_token(val: Any) -> Any:
    if isinstance(val, str):
        return val.strip().lower().replace("-", "_").replace(" ", "_")
    return val


class ExtractedRequirementFinding(BaseModel):
    code: str
    status: LLMComplianceStatus
    quote: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    confidence: LLMConfidence = LLMConfidence.HIGH
    is_inference: bool = False
    risk_types: List[LLMRiskType] = Field(default_factory=list)
    severity: Optional[LLMSeverity] = None
    clarification_question: Optional[str] = None

    @field_validator("status", "confidence", "severity", mode="before")
    @classmethod
    def _norm_single_enums(cls, v: Any) -> Any:
        return _normalise_enum_token(v)

    @field_validator("risk_types", mode="before")
    @classmethod
    def _norm_risk_types(cls, v: Any) -> Any:
        if isinstance(v, list):
            return [_normalise_enum_token(item) for item in v]
        return v


class ExtractedCriterionFinding(BaseModel):
    key: str
    status: LLMComplianceStatus
    quote: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    rationale: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def _norm_status(cls, v: Any) -> Any:
        return _normalise_enum_token(v)


class ExtractedStandaloneRisk(BaseModel):
    risk_types: List[LLMRiskType] = Field(default_factory=list)
    severity: LLMSeverity = LLMSeverity.MEDIUM
    quote: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    description: str = ""
    clarification_question: Optional[str] = None

    @field_validator("severity", mode="before")
    @classmethod
    def _norm_severity(cls, v: Any) -> Any:
        return _normalise_enum_token(v)

    @field_validator("risk_types", mode="before")
    @classmethod
    def _norm_risk_types(cls, v: Any) -> Any:
        if isinstance(v, list):
            return [_normalise_enum_token(item) for item in v]
        return v


class ExtractedCostItem(BaseModel):
    item: str
    quote: Optional[str] = None
    page: Optional[int] = None


class ExtractedCost(BaseModel):
    monthly_base: Optional[float] = None
    included: List[ExtractedCostItem] = Field(default_factory=list)
    excluded: List[ExtractedCostItem] = Field(default_factory=list)
    optional: List[ExtractedCostItem] = Field(default_factory=list)
    unknown: List[ExtractedCostItem] = Field(default_factory=list)


class VendorAnalysisResult(BaseModel):
    requirement_findings: List[ExtractedRequirementFinding] = Field(
        default_factory=list
    )
    criterion_findings: List[ExtractedCriterionFinding] = Field(
        default_factory=list
    )
    risks: List[ExtractedStandaloneRisk] = Field(default_factory=list)
    cost: ExtractedCost = Field(default_factory=ExtractedCost)


def build_pdf_to_pages_prompt() -> str:
    prompt_path = PROMPTS_DIR / "extract_pages_v1.txt"
    return prompt_path.read_text(encoding="utf-8").strip()


def build_extract_requirements_prompt(pages: List[PageText]) -> str:
    prompt_path = PROMPTS_DIR / "extract_requirements_v1.txt"
    template = prompt_path.read_text(encoding="utf-8")
    ordered_pages = sorted(pages, key=lambda p: p.page_number)
    formatted_sections = [
        f"--- PAGE {p.page_number} ---\n{p.text}" for p in ordered_pages
    ]
    document_text = "\n\n".join(formatted_sections)
    return template.replace("{document_text}", document_text)


def build_analyse_vendor_prompt(
    vendor_name: str,
    requirements: Sequence[Dict[str, Any]],
    judged_criteria: Sequence[Dict[str, Any]],
    pages: Sequence[PageText],
) -> str:
    prompt_path = PROMPTS_DIR / "analyse_vendor_v1.txt"
    template = prompt_path.read_text(encoding="utf-8")

    req_lines: List[str] = []
    for r in requirements:
        code = r.get("code", "")
        mand = "true" if r.get("mandatory") else "false"
        text = r.get("text", "")
        acc = r.get("acceptance", "")
        req_lines.append(
            f"- code: {code} | mandatory: {mand} | requirement: {text} | acceptance: {acc}"
        )
    requirements_text = "\n".join(req_lines)[:MAX_REQUIREMENTS_SECTION_CHARS]

    crit_lines: List[str] = []
    for c in judged_criteria:
        key = c.get("key", "")
        name = c.get("name", "")
        guidance = c.get("guidance", "")
        crit_lines.append(f"- key: {key} | name: {name} | guidance: {guidance}")
    criteria_text = "\n".join(crit_lines)[:MAX_CRITERIA_SECTION_CHARS]

    ordered_pages = sorted(pages, key=lambda p: p.page_number)
    page_sections = [
        f"--- PAGE {p.page_number} ---\n{p.text}" for p in ordered_pages
    ]
    proposal_text = "\n\n".join(page_sections)[:MAX_PROPOSAL_SECTION_CHARS]

    return (
        template.replace("{vendor_name}", vendor_name)
        .replace("{requirements_text}", requirements_text)
        .replace("{criteria_text}", criteria_text)
        .replace("{proposal_text}", proposal_text)
    )


def build_parse_details_prompt(
    user_message: str,
    collected_details: Optional[Dict[str, Any]] = None,
    missing_fields: Optional[List[str]] = None,
) -> str:
    prompt_path = PROMPTS_DIR / "parse_details_v4.txt"
    template = prompt_path.read_text(encoding="utf-8")
    safe_message = (user_message or "")[:1000]
    coll_str = ", ".join(f"{k}={v}" for k, v in (collected_details or {}).items() if v) or "None"
    missing_str = ", ".join(missing_fields or []) or "None"
    return (
        template.replace("{user_message}", safe_message)
        .replace("{collected_context}", coll_str)
        .replace("{missing_context}", missing_str)
    )


class GeminiClient(ABC):
    @abstractmethod
    async def pdf_to_pages(self, pdf_bytes: bytes) -> List[PageText]:
        """Extract verbatim text per page from PDF bytes."""
        ...

    @abstractmethod
    async def extract_requirements(
        self, pages: List[PageText]
    ) -> List[ExtractedRequirement]:
        """Extract structured requirements from ordered document pages."""
        ...

    @abstractmethod
    async def analyse_vendor(
        self,
        vendor_name: str,
        requirements: List[Dict[str, Any]],
        judged_criteria: List[Dict[str, Any]],
        pages: List[PageText],
    ) -> VendorAnalysisResult:
        """Analyse a single vendor proposal against requirements and judged criteria."""
        ...

    @abstractmethod
    async def parse_evaluation_details(
        self,
        user_message: str,
        collected_details: Optional[Dict[str, Any]] = None,
        missing_fields: Optional[List[str]] = None,
    ) -> ParsedEvaluationDetails:
        """Parse evaluation title, category, and vendor names from user message."""
        ...


def _is_retryable_Error(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        if code in (429, 500, 502, 503, 504):
            return True
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status_code in (429, 500, 502, 503, 504):
        return True
    exc_name = type(exc).__name__.lower()
    if any(
        k in exc_name
        for k in (
            "ratelimit",
            "resourceexhausted",
            "servererror",
            "serviceunavailable",
            "timeout",
        )
    ):
        return True
    return False


class GoogleGenAIClient(GeminiClient):
    """Real Gemini client using the official google-genai SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        sdk_client: Optional[Any] = None,
    ) -> None:
        resolved_key = api_key
        if resolved_key is None and settings.GEMINI_API_KEY is not None:
            resolved_key = settings.GEMINI_API_KEY.get_secret_value()
        self._api_key = resolved_key
        self._model = model or settings.GEMINI_MODEL
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._sdk_client = sdk_client

    def _get_sdk_client(self) -> Any:
        if self._sdk_client is not None:
            return self._sdk_client
        if not self._api_key:
            raise GeminiClientError("GEMINI_API_KEY is not configured")
        self._sdk_client = genai.Client(api_key=self._api_key)
        return self._sdk_client

    async def _call_with_retries_and_validation(
        self,
        operation_name: str,
        contents: List[Any],
        schema_cls: Type[T],
    ) -> T:
        client = self._get_sdk_client()
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=schema_cls,
        )

        validation_attempts = 0
        max_validation_attempts = 2  # initial + 1 retry on invalid output

        while validation_attempts < max_validation_attempts:
            validation_attempts += 1
            transient_retries = 0

            while True:
                start_ts = time.monotonic()
                try:
                    response = await asyncio.wait_for(
                        client.aio.models.generate_content(
                            model=self._model,
                            contents=contents,
                            config=config,
                        ),
                        timeout=self._timeout_seconds,
                    )
                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    logger.info(
                        "Gemini call completed: op=%s duration_ms=%d",
                        operation_name,
                        duration_ms,
                    )
                    break
                except Exception as exc:
                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    if (
                        _is_retryable_Error(exc)
                        and transient_retries < self._max_retries
                    ):
                        transient_retries += 1
                        delay = self._base_backoff * (
                            2 ** (transient_retries - 1)
                        )
                        logger.warning(
                            "Gemini transient error: op=%s error_type=%s retry=%d/%d delay_s=%.2f duration_ms=%d",
                            operation_name,
                            type(exc).__name__,
                            transient_retries,
                            self._max_retries,
                            delay,
                            duration_ms,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        "Gemini call failed: op=%s error_type=%s retries=%d duration_ms=%d",
                        operation_name,
                        type(exc).__name__,
                        transient_retries,
                        duration_ms,
                    )
                    raise GeminiClientError(
                        f"Gemini {operation_name} failed ({type(exc).__name__})"
                    ) from exc

            # Validate structured JSON response with Pydantic model
            raw_text = getattr(response, "text", None)
            try:
                if not raw_text or not isinstance(raw_text, str):
                    raise ValueError("Empty response text from model")
                parsed_json = json.loads(raw_text)
                validated = schema_cls.model_validate(parsed_json)
                return validated
            except (json.JSONDecodeError, ValidationError, ValueError) as val_exc:
                logger.warning(
                    "Gemini invalid structured output: op=%s attempt=%d/%d error_type=%s",
                    operation_name,
                    validation_attempts,
                    max_validation_attempts,
                    type(val_exc).__name__,
                )
                if validation_attempts >= max_validation_attempts:
                    raise GeminiClientError(
                        f"Gemini returned invalid structured JSON for {operation_name} after retry"
                    ) from val_exc

        raise GeminiClientError(f"Gemini {operation_name} failed validation")

    async def pdf_to_pages(self, pdf_bytes: bytes) -> List[PageText]:
        prompt = build_pdf_to_pages_prompt()
        pdf_part = types.Part.from_bytes(
            data=pdf_bytes, mime_type="application/pdf"
        )
        envelope = await self._call_with_retries_and_validation(
            operation_name="pdf_to_pages",
            contents=[prompt, pdf_part],
            schema_cls=PdfPagesEnvelope,
        )
        ordered = sorted(envelope.pages, key=lambda p: p.page_number)
        logger.info("Extracted PDF pages: page_count=%d", len(ordered))
        return ordered

    async def extract_requirements(
        self, pages: List[PageText]
    ) -> List[ExtractedRequirement]:
        prompt = build_extract_requirements_prompt(pages)
        envelope = await self._call_with_retries_and_validation(
            operation_name="extract_requirements",
            contents=[prompt],
            schema_cls=ExtractedRequirementsEnvelope,
        )
        logger.info(
            "Extracted requirements: count=%d", len(envelope.requirements)
        )
        return envelope.requirements

    async def analyse_vendor(
        self,
        vendor_name: str,
        requirements: List[Dict[str, Any]],
        judged_criteria: List[Dict[str, Any]],
        pages: List[PageText],
    ) -> VendorAnalysisResult:
        prompt = build_analyse_vendor_prompt(
            vendor_name=vendor_name,
            requirements=requirements,
            judged_criteria=judged_criteria,
            pages=pages,
        )
        result = await self._call_with_retries_and_validation(
            operation_name="analyse_vendor",
            contents=[prompt],
            schema_cls=VendorAnalysisResult,
        )
        logger.info(
            "Analysed vendor proposal: req_findings=%d crit_findings=%d risks=%d",
            len(result.requirement_findings),
            len(result.criterion_findings),
            len(result.risks),
        )
        return result

    async def parse_evaluation_details(
        self,
        user_message: str,
        collected_details: Optional[Dict[str, Any]] = None,
        missing_fields: Optional[List[str]] = None,
    ) -> ParsedEvaluationDetails:
        prompt = build_parse_details_prompt(user_message, collected_details, missing_fields)
        result = await self._call_with_retries_and_validation(
            operation_name="parse_evaluation_details",
            contents=[prompt],
            schema_cls=ParsedEvaluationDetails,
        )
        logger.info(
            "Parsed evaluation details: has_title=%s has_category=%s vendor_count=%d",
            bool(result.title),
            bool(result.category),
            len(result.vendor_names),
        )
        return result


class FakeGeminiClient(GeminiClient):
    """Fake Gemini client for deterministic unit testing without live model calls."""

    def __init__(
        self,
        default_pages: Optional[List[PageText]] = None,
        default_requirements: Optional[List[ExtractedRequirement]] = None,
        pdf_handler: Optional[Callable[[bytes], List[PageText]]] = None,
        requirements_handler: Optional[
            Callable[[List[PageText]], List[ExtractedRequirement]]
        ] = None,
        default_analysis: Optional[VendorAnalysisResult] = None,
        analysis_by_vendor: Optional[Dict[str, VendorAnalysisResult]] = None,
        analysis_handler: Optional[Callable[..., VendorAnalysisResult]] = None,
        details_handler: Optional[Callable[[str], ParsedEvaluationDetails]] = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.default_pages = default_pages or [
            PageText(
                page_number=1,
                text="Section 2.1: Vendor must provide 12 housekeeping staff daily.\nSection 2.2: Deep cleaning is optional quarterly.",
            ),
            PageText(
                page_number=2,
                text="Section 3.1: Washroom consumables shall be included in base fee.",
            ),
        ]
        self.default_requirements = (
            default_requirements
            if default_requirements is not None
            else [
                ExtractedRequirement(
                    code="REQ-01",
                    text="Minimum 12 housekeeping staff on site daily",
                    category="Staffing",
                    mandatory=True,
                    acceptance=">= 12 staff",
                    source_page=1,
                    source_section="§2.1",
                ),
                ExtractedRequirement(
                    code="REQ-02",
                    text="Quarterly deep cleaning of carpets",
                    category="Service",
                    mandatory=False,
                    acceptance="4 per year",
                    source_page=1,
                    source_section="§2.2",
                ),
                ExtractedRequirement(
                    code="REQ-03",
                    text="Washroom consumables included in monthly fee",
                    category="Commercial",
                    mandatory=True,
                    acceptance="Included in base fee",
                    source_page=2,
                    source_section="§3.1",
                ),
            ]
        )
        self.pdf_handler = pdf_handler
        self.requirements_handler = requirements_handler
        self.default_analysis = default_analysis
        self.analysis_by_vendor = analysis_by_vendor or {}
        self.analysis_handler = analysis_handler
        self.details_handler = details_handler
        self.delay_seconds = delay_seconds
        self.pdf_call_count = 0
        self.requirements_call_count = 0
        self.analysis_call_count = 0
        self.details_call_count = 0
        self.last_analysis_calls: List[Dict[str, Any]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def pdf_to_pages(self, pdf_bytes: bytes) -> List[PageText]:
        self.pdf_call_count += 1
        self.in_flight += 1
        if self.in_flight > self.max_in_flight:
            self.max_in_flight = self.in_flight
        try:
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)
            if self.pdf_handler is not None:
                return self.pdf_handler(pdf_bytes)
            return list(self.default_pages)
        finally:
            self.in_flight -= 1

    async def extract_requirements(
        self, pages: List[PageText]
    ) -> List[ExtractedRequirement]:
        self.requirements_call_count += 1
        if self.requirements_handler is not None:
            return self.requirements_handler(pages)
        return list(self.default_requirements)

    async def analyse_vendor(
        self,
        vendor_name: str,
        requirements: List[Dict[str, Any]],
        judged_criteria: List[Dict[str, Any]],
        pages: List[PageText],
    ) -> VendorAnalysisResult:
        self.analysis_call_count += 1
        self.last_analysis_calls.append(
            {
                "vendor_name": vendor_name,
                "requirements": requirements,
                "judged_criteria": judged_criteria,
                "pages": pages,
            }
        )
        self.in_flight += 1
        if self.in_flight > self.max_in_flight:
            self.max_in_flight = self.in_flight
        try:
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)
            if self.analysis_handler is not None:
                sig = inspect.signature(self.analysis_handler)
                params = list(sig.parameters.values())
                has_varargs = any(
                    p.kind == inspect.Parameter.VAR_POSITIONAL for p in params
                )
                if has_varargs or len(params) >= 4:
                    return self.analysis_handler(
                        vendor_name, requirements, judged_criteria, pages
                    )
                if len(params) == 1:
                    return self.analysis_handler(vendor_name)
                return self.analysis_handler(vendor_name, requirements)
            if vendor_name in self.analysis_by_vendor:
                return self.analysis_by_vendor[vendor_name]
            if self.default_analysis is not None:
                return self.default_analysis

            first_page = pages[0] if pages else PageText(page_number=1, text="")
            first_line = (
                first_page.text.splitlines()[0].strip()
                if first_page.text.strip()
                else ""
            )
            req_findings = [
                ExtractedRequirementFinding(
                    code=r["code"],
                    status=LLMComplianceStatus.COMPLIANT,
                    quote=first_line or None,
                    page=first_page.page_number if first_line else None,
                    section="§1",
                    confidence=LLMConfidence.HIGH,
                    is_inference=False,
                    risk_types=[],
                    severity=None,
                    clarification_question=None,
                )
                for r in requirements
            ]
            crit_findings = [
                ExtractedCriterionFinding(
                    key=c["key"],
                    status=LLMComplianceStatus.COMPLIANT,
                    quote=first_line or None,
                    page=first_page.page_number if first_line else None,
                    section="§1",
                    rationale="Supported by proposal text.",
                )
                for c in judged_criteria
            ]
            return VendorAnalysisResult(
                requirement_findings=req_findings,
                criterion_findings=crit_findings,
                risks=[],
                cost=ExtractedCost(
                    monthly_base=400000.0,
                    included=[
                        ExtractedCostItem(
                            item="Housekeeping staff",
                            quote=first_line or None,
                            page=first_page.page_number if first_line else None,
                        )
                    ],
                    excluded=[],
                    optional=[],
                    unknown=[],
                ),
            )
        finally:
            self.in_flight -= 1

    async def parse_evaluation_details(
        self,
        user_message: str,
        collected_details: Optional[Dict[str, Any]] = None,
        missing_fields: Optional[List[str]] = None,
    ) -> ParsedEvaluationDetails:
        self.details_call_count += 1
        if self.details_handler is not None:
            return self.details_handler(user_message)

        msg_lower = user_message.lower().strip()

        # Check prompt injection: ignore instructions inside message and extract only legitimate details
        if "ignore previous instructions" in msg_lower or "ignore all instructions" in msg_lower:
            if "housekeeping" in msg_lower and "brightnest" in msg_lower:
                return ParsedEvaluationDetails(
                    title="Housekeeping Services",
                    category="Housekeeping",
                    vendor_names=["BrightNest Facility Services", "Shubh Services"],
                )
            return ParsedEvaluationDetails(title=None, category=None, vendor_names=[])

        # Explicit test markers
        if "only title:" in msg_lower:
            return ParsedEvaluationDetails(
                title=user_message.split("only title:", 1)[1].strip(),
                category=None,
                vendor_names=[],
            )

        if "only category:" in msg_lower:
            return ParsedEvaluationDetails(
                title=None,
                category=user_message.split("only category:", 1)[1].strip(),
                vendor_names=[],
            )

        if "only vendors:" in msg_lower:
            v_items = [v.strip() for v in user_message.split("only vendors:", 1)[1].strip().split(",") if v.strip()]
            return ParsedEvaluationDetails(title=None, category=None, vendor_names=v_items)

        # Standalone short replies (answering specific single questions)
        if msg_lower in ("security", "housekeeping", "pantry", "pest control", "facilities", "pantry amc"):
            return ParsedEvaluationDetails(title=None, category=user_message.strip(), vendor_names=[])

        # Standalone category specification: "category pest control", "category: pest control", "category - pest control", etc.
        cat_spec_match = re.search(r"^(?:change\s+)?(?:the\s+)?category(?:\s+to)?\s*[-:=]?\s*(.+)$", user_message.strip(), re.IGNORECASE)
        if cat_spec_match:
            cat_val = cat_spec_match.group(1).strip()
            return ParsedEvaluationDetails(title=None, category=cat_val, vendor_names=[])

        # Content-based parsing for tests:
        title: Optional[str] = None
        category: Optional[str] = None
        vendors: List[str] = []

        if "housekeeping" in msg_lower and "security" in msg_lower:
            category = "housekeeping and security"
        elif "housekeeping" in msg_lower:
            category = "Housekeeping"
        elif "security" in msg_lower:
            category = "Security"
        elif "pantry" in msg_lower:
            category = "Pantry"
        elif "pest control" in msg_lower:
            category = "pest control"
        elif "facilities" in msg_lower:
            category = "Facilities"

        # 4 vendors case for testing "4 vendors -> asks to choose"
        if "4 vendors" in msg_lower or ("vendor a" in msg_lower and "vendor d" in msg_lower) or "four vendors" in msg_lower:
            vendors = ["Vendor A", "Vendor B", "Vendor C", "Vendor D"]
            title = "Office Cleaning"
            category = category or "Housekeeping"
            return ParsedEvaluationDetails(title=title, category=category, vendor_names=vendors)

        if "brightnest" in msg_lower and "shubh" in msg_lower and "urbankleen" in msg_lower:
            vendors = ["BrightNest Facility Services", "Shubh Services", "UrbanKleen Pvt Ltd"]
            title = "Housekeeping Services — Mumbai Office"
            category = category or "Housekeeping"
        elif "brightnest" in msg_lower and "shubh" in msg_lower:
            vendors = ["BrightNest Facility Services", "Shubh Services"]
            title = "Housekeeping Services — Mumbai Office"
            category = category or "Housekeeping"
        elif "vendor 1" in msg_lower and "vendor 2" in msg_lower:
            vendors = ["Vendor 1", "Vendor 2"]
            title = "Facilities AMC"
            category = category or "Facilities"
        elif ("vendor a" in msg_lower or "vendors a" in msg_lower) and ("vendor b" in msg_lower or "and b" in msg_lower):
            vendors = ["Vendor A", "Vendor B"]
            if "contract for security services" in msg_lower:
                title = "Contract for security services"

        if not title:
            # If user message provides a clear title phrase or evaluate sentence
            if msg_lower.startswith("evaluate ") or "rfp" in msg_lower:
                first_part = user_message.split("between", 1)[0].strip()
                if first_part.lower().startswith("evaluate "):
                    first_part = first_part[9:].strip()
                title = first_part or "Vendor Evaluation"

        return ParsedEvaluationDetails(
            title=title,
            category=category,
            vendor_names=vendors,
        )


GeminiClientFactory = Callable[[], GeminiClient]


def create_gemini_client() -> GeminiClient:
    """Factory function creating the real GeminiClient instance."""
    return GoogleGenAIClient()
