import io
from unittest.mock import patch
import uuid
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage import get_storage
import asyncio

client = TestClient(app)


def fake_token(uid: str, email: str = "doc_user@vixenone.app"):
    return {"uid": uid, "email": email, "name": "Doc User"}


def make_valid_pdf_bytes(page_count: int = 1) -> bytes:
    """Construct a minimal valid PDF with given number of pages."""
    kids = " ".join(f"{i+3} 0 R" for i in range(page_count))
    obj_defs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {page_count} >>\nendobj\n".encode(),
    ]
    for i in range(page_count):
        obj_defs.append(
            f"{i+3} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n".encode()
        )

    header = b"%PDF-1.4\n"
    body = b"".join(obj_defs)
    xref_offset = len(header) + len(body)
    xref = f"xref\n0 {len(obj_defs)+1}\n0000000000 65535 f \n".encode()
    trailer = f"trailer\n<< /Size {len(obj_defs)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return header + body + xref + trailer


def make_valid_docx_bytes(pages: int = None) -> bytes:
    """Construct a minimal in-memory DOCX zip package with word/document.xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/></w:body></w:document>')
        if pages is not None:
            z.writestr("docProps/app.xml", f'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Pages>{pages}</Pages></Properties>')
    return buf.getvalue()


def test_upload_rejects_wrong_type():
    uid = f"uid-doc-type-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}
        ev = client.post("/api/evaluations", headers=auth, json={"title": "Doc RFP", "category": "Facilities", "vendor_names": ["A", "B"]}).json()
        eval_id = ev["id"]

        # Plain text
        files = {"file": ("notes.txt", b"Just some plain text notes", "text/plain")}
        r = client.post(f"/api/evaluations/{eval_id}/documents", headers=auth, files=files, data={"kind": "requirements"})
        assert r.status_code == 422
        assert "Unsupported document format" in r.json()["detail"]


def test_upload_rejects_renamed_txt_as_pdf():
    uid = f"uid-doc-fake-pdf-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}
        ev = client.post("/api/evaluations", headers=auth, json={"title": "Doc RFP", "category": "Facilities", "vendor_names": ["A", "B"]}).json()
        eval_id = ev["id"]

        # Renamed .txt as .pdf (does not start with %PDF-)
        files = {"file": ("report.pdf", b"Hello world, I am actually a text file!", "application/pdf")}
        r = client.post(f"/api/evaluations/{eval_id}/documents", headers=auth, files=files, data={"kind": "requirements"})
        assert r.status_code == 422
        assert "Unsupported document format" in r.json()["detail"]


def test_upload_rejects_plain_zip_as_docx():
    uid = f"uid-doc-fake-docx-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}
        ev = client.post("/api/evaluations", headers=auth, json={"title": "Doc RFP", "category": "Facilities", "vendor_names": ["A", "B"]}).json()
        eval_id = ev["id"]

        # Zip file without word/document.xml
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("data.txt", "Some random zip data")
        plain_zip = buf.getvalue()

        files = {"file": ("proposal.docx", plain_zip, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        v_id = ev["vendors"][0]["id"]
        r = client.post(f"/api/evaluations/{eval_id}/documents", headers=auth, files=files, data={"kind": "proposal", "vendor_id": v_id})
        assert r.status_code == 422
        assert "word/document.xml" in r.json()["detail"]


def test_upload_rejects_pdf_over_30_pages():
    uid = f"uid-doc-pdf-over30-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}
        ev = client.post("/api/evaluations", headers=auth, json={"title": "Doc RFP", "category": "Facilities", "vendor_names": ["A", "B"]}).json()
        eval_id = ev["id"]

        pdf_31_pages = make_valid_pdf_bytes(page_count=31)
        files = {"file": ("huge.pdf", pdf_31_pages, "application/pdf")}
        r = client.post(f"/api/evaluations/{eval_id}/documents", headers=auth, files=files, data={"kind": "requirements"})
        assert r.status_code == 422
        assert "PDF exceeds maximum limit of 30 pages" in r.json()["detail"]


def test_upload_valid_pdf_counts_pages():
    uid = f"uid-doc-pdf-ok-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}
        ev = client.post("/api/evaluations", headers=auth, json={"title": "Doc RFP", "category": "Facilities", "vendor_names": ["A", "B"]}).json()
        eval_id = ev["id"]

        pdf_5_pages = make_valid_pdf_bytes(page_count=5)
        files = {"file": ("valid.pdf", pdf_5_pages, "application/pdf")}
        r = client.post(f"/api/evaluations/{eval_id}/documents", headers=auth, files=files, data={"kind": "requirements"})
        assert r.status_code == 200
        data = r.json()
        assert data["page_count"] == 5
        assert data["kind"] == "requirements"
        assert data["status"] == "uploaded"


def test_upload_valid_docx_extracts_page_count():
    uid = f"uid-doc-docx-ok-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}
        ev = client.post("/api/evaluations", headers=auth, json={"title": "Doc RFP", "category": "Facilities", "vendor_names": ["A", "B"]}).json()
        eval_id = ev["id"]
        v_id = ev["vendors"][0]["id"]

        # DOCX with Pages=7 in app.xml
        docx_bytes = make_valid_docx_bytes(pages=7)
        files = {"file": ("valid.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        r = client.post(f"/api/evaluations/{eval_id}/documents", headers=auth, files=files, data={"kind": "proposal", "vendor_id": v_id})
        assert r.status_code == 200
        data = r.json()
        assert data["page_count"] == 7
        assert data["kind"] == "proposal"


def test_reupload_replaces_row_and_removes_old_file():
    uid = f"uid-doc-reup-{uuid.uuid4().hex}"
    with patch("firebase_admin.auth.verify_id_token", return_value=fake_token(uid)):
        auth = {"Authorization": "Bearer token"}
        ev = client.post("/api/evaluations", headers=auth, json={"title": "Doc RFP", "category": "Facilities", "vendor_names": ["A", "B"]}).json()
        eval_id = ev["id"]

        pdf1 = make_valid_pdf_bytes(page_count=2)
        r1 = client.post(
            f"/api/evaluations/{eval_id}/documents",
            headers=auth,
            files={"file": ("v1.pdf", pdf1, "application/pdf")},
            data={"kind": "requirements"},
        )
        assert r1.status_code == 200
        key1 = r1.json()["storage_key"]
        doc1_id = r1.json()["id"]

        storage = get_storage()
        assert asyncio.run(storage.exists(key1)) is True

        # Re-upload requirements document
        pdf2 = make_valid_pdf_bytes(page_count=4)
        r2 = client.post(
            f"/api/evaluations/{eval_id}/documents",
            headers=auth,
            files={"file": ("v2.pdf", pdf2, "application/pdf")},
            data={"kind": "requirements"},
        )
        assert r2.status_code == 200
        key2 = r2.json()["storage_key"]
        doc2_id = r2.json()["id"]

        assert doc1_id != doc2_id
        # Old file should be deleted from storage
        assert asyncio.run(storage.exists(key1)) is False
        # New file exists
        assert asyncio.run(storage.exists(key2)) is True

        # In evaluation detail, only 1 document is present
        detail = client.get(f"/api/evaluations/{eval_id}", headers=auth).json()
        assert len(detail["documents"]) == 1
        assert detail["documents"][0]["id"] == doc2_id
