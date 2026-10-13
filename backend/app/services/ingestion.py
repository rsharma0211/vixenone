import io
from typing import List
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.llm.client import PageText


class DocumentExtractionError(Exception):
    """Raised when local document extraction fails."""

    pass


def extract_docx_pages(docx_bytes: bytes) -> List[PageText]:
    """Convert DOCX bytes into a single page (page_number=1) in reading order.

    - Body elements (paragraphs and tables) are read in exact document order.
    - Headings (style starting with 'Heading') are formatted as '## <heading>'.
    - Tables are flattened row by row with cell texts joined by ' | '.
    """
    try:
        doc = docx.Document(io.BytesIO(docx_bytes))
    except Exception as exc:
        raise DocumentExtractionError("Could not read DOCX file") from exc

    lines: List[str] = []
    for child in doc.element.body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style_name = (
                para.style.name.lower()
                if para.style and para.style.name
                else ""
            )
            if style_name.startswith("heading"):
                lines.append(f"## {text}")
            else:
                lines.append(text)
        elif tag == "tbl":
            table = Table(child, doc)
            for row in table.rows:
                cells = [
                    " ".join(cell.text.strip().splitlines())
                    for cell in row.cells
                ]
                if any(cells):
                    lines.append(" | ".join(cells))

    full_text = "\n".join(lines)
    return [PageText(page_number=1, text=full_text)]
