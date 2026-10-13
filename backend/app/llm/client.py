from abc import ABC, abstractmethod
import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

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


class ExtractedRequirementsEnvelope(BaseModel):
    requirements: List[ExtractedRequirement]


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
        for k in ("ratelimit", "resourceexhausted", "servererror", "serviceunavailable", "timeout")
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
                    if _is_retryable_Error(exc) and transient_retries < self._max_retries:
                        transient_retries += 1
                        delay = self._base_backoff * (2 ** (transient_retries - 1))
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
            except ( json.JSONDecodeError, ValidationError, ValueError) as val_exc:
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
        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
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
        self.delay_seconds = delay_seconds
        self.pdf_call_count = 0
        self.requirements_call_count = 0
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


GeminiClientFactory = Callable[[], GeminiClient]


def create_gemini_client() -> GeminiClient:
    """Factory function creating the real GeminiClient instance."""
    return GoogleGenAIClient()
