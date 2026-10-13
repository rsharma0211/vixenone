import io
from typing import Optional, Tuple
import xml.etree.ElementTree as ET
import zipfile
from fastapi import HTTPException, status
import pdfplumber

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 30


def validate_document_content(
    content: bytes, filename: str
) -> Tuple[str, str, Optional[int]]:
    """Validate document content by signature and internal structure (not by file extension).

    Returns:
        (detected_type, mime_type, page_count)

    Raises:
        HTTPException(422) if invalid, corrupted, unsupported, oversized, or exceeding page limits.
    """
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File exceeds maximum size of 10 MB ({len(content)} bytes)",
        )

    page_count: Optional[int] = None

    # 1. Check for PDF signature
    if content.startswith(b"%PDF-"):
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                page_count = len(pdf.pages)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid or corrupted PDF file: {exc}",
            )

        if page_count > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"PDF exceeds maximum limit of {MAX_PDF_PAGES} pages (found {page_count})",
            )

        return "pdf", "application/pdf", page_count

    # 2. Check for DOCX (must be a valid ZIP archive containing word/document.xml)
    if content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                namelist = z.namelist()
                if "word/document.xml" not in namelist:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Invalid DOCX file: zip archive does not contain Word main document part (word/document.xml)",
                    )

                # Attempt to extract page count from docProps/app.xml
                page_count = None
                if "docProps/app.xml" in namelist:
                    try:
                        app_xml = z.read("docProps/app.xml")
                        root = ET.fromstring(app_xml)
                        for elem in root.iter():
                            if elem.tag.endswith("Pages") and elem.text and elem.text.strip().isdigit():
                                page_count = int(elem.text.strip())
                                break
                    except Exception:
                        page_count = None

                return (
                    "docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    page_count,
                )
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid DOCX file: file is not a valid zip archive",
            )

    # If it is neither a valid PDF nor a valid DOCX Word package:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unsupported document format. Only valid PDF and DOCX files are accepted.",
    )
