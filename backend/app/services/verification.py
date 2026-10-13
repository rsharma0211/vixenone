import re
from typing import Dict, List, Optional, Sequence, Tuple

from app.llm.client import PageText

_SINGLE_QUOTES_RE = re.compile(r"[\u2018\u2019\u201a\u201b\u2032`]")
_DOUBLE_QUOTES_RE = re.compile(r"[\u201c\u201d\u201e\u201f\u2033\u00ab\u00bb]")
_DASHES_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")
_HYPHEN_LINEBREAK_RE = re.compile(r"-\s*[\r\n]+\s*")
_WHITESPACE_RE = re.compile(r"\s+")
_WORD_HYPHEN_RE = re.compile(r"(?<=\w)\s*-\s*(?=\w)")


def normalise_text_for_verification(text: str) -> str:
    """Normalise text for quote verification:
    - unify curly quotes and dashes
    - join hyphenated line breaks
    - collapse whitespace and line breaks
    - case-insensitive (lowercase)
    """
    if not text:
        return ""
    s = _SINGLE_QUOTES_RE.sub("'", text)
    s = _DOUBLE_QUOTES_RE.sub('"', s)
    s = _DASHES_RE.sub("-", s)
    s = _HYPHEN_LINEBREAK_RE.sub("", s)
    s = _WHITESPACE_RE.sub(" ", s)
    return s.strip().lower()


def _dehyphenate(norm_text: str) -> str:
    """Remove hyphens between word characters so hyphenated compound words
    split across line breaks (e.g. 'police-\\nverified' vs 'police-verified') also match.
    """
    return _WORD_HYPHEN_RE.sub("", norm_text)


def quote_matches_page(quote: str, page_text: str) -> bool:
    """Return True if normalised quote exists inside normalised page_text."""
    norm_quote = normalise_text_for_verification(quote)
    norm_page = normalise_text_for_verification(page_text)
    if not norm_quote or not norm_page:
        return False

    if norm_quote in norm_page:
        return True

    # Also check with outer quote marks stripped if model wrapped quote in quotes
    stripped_quote = norm_quote.strip("'\" ").strip()
    if stripped_quote and stripped_quote in norm_page:
        return True

    # Check dehyphenated variant (handles compound words split at line breaks)
    dehyp_page = _dehyphenate(norm_page)
    if _dehyphenate(norm_quote) in dehyp_page:
        return True
    if stripped_quote and _dehyphenate(stripped_quote) in dehyp_page:
        return True

    return False


def verify_quote_against_pages(
    status: Optional[str],
    quote: Optional[str],
    cited_page: Optional[int],
    pages: Sequence[PageText],
) -> Tuple[Optional[str], Optional[int], bool]:
    """Verify a finding's quote against a vendor's proposal pages.

    Rules:
    - Quote found on the cited page -> keep page, needs_review = False.
    - Found on another page of the same document -> correct the page, needs_review = False.
    - Not found -> needs_review = True (status kept, never upgraded).
    - Compliant or partial with no quote -> needs_review = True.
    - not_evidenced needs no quote -> needs_review = False when quote is absent.
    """
    norm_status = (status or "").strip().lower().replace("-", "_").replace(" ", "_")
    cleaned_quote = quote.strip() if quote and quote.strip() else None

    if cleaned_quote is None:
        if norm_status in ("not_evidenced", "notevidenced"):
            return None, None, False
        if norm_status in ("compliant", "partially_compliant", "partial"):
            return None, None, True
        # For non_compliant or standalone risk with no quote
        return None, None, True

    pages_by_num: Dict[int, str] = {p.page_number: p.text for p in pages}
    ordered_pages: List[PageText] = sorted(pages, key=lambda p: p.page_number)

    # 1. Check cited page first
    if cited_page is not None and cited_page in pages_by_num:
        if quote_matches_page(cleaned_quote, pages_by_num[cited_page]):
            return cleaned_quote, cited_page, False

    # 2. Check other pages of the same document in page order
    for p in ordered_pages:
        if p.page_number == cited_page:
            continue
        if quote_matches_page(cleaned_quote, p.text):
            return cleaned_quote, p.page_number, False

    # 3. Not found anywhere in the document -> needs_review = True
    kept_page = cited_page if (cited_page is not None and cited_page in pages_by_num) else None
    return cleaned_quote, kept_page, True
