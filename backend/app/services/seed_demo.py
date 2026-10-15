import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast
import uuid
import pdfplumber
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.company import Location
from app.models.evaluation import (
    AnalysisJob,
    Clarification,
    CostBreakdown,
    CriterionScore,
    Document,
    DocumentPage,
    Evaluation,
    Finding,
    Requirement,
    Vendor,
)
from app.models.user import User
from app.repositories.company_repo import CompanyRepository
from app.repositories.criteria_repo import CriteriaRepository
from app.schemas.criteria import BUILTIN_CRITERIA_DEFAULTS
from app.services.document_validator import validate_document_content
from app.services.ingestion import extract_docx_pages
from app.services.storage import StorageService, get_storage

DEMO_EMAIL = "demo@vixenone.app"
DEMO_COMPANY_NAME = "Northbridge Properties Pvt Ltd"
DEMO_LOCATIONS = [
    ("Andheri East Office", "Mumbai", 0),
    ("Powai Campus", "Mumbai", 1),
    ("BKC Office", "Mumbai", 2),
    ("Thane Warehouse", "Thane", 3),
]


async def seed_demo_data(
    session: Optional[AsyncSession] = None,
    storage: Optional[StorageService] = None,
    dataset_dir: Optional[Path] = None,
) -> None:
    """Seed complete demo dataset for demo user idempotently."""
    close_session = False
    if session is None:
        session = async_session()
        close_session = True

    try:
        # Find demo user
        stmt = select(User).where(User.email == DEMO_EMAIL).order_by(User.created_at)
        res = await session.execute(stmt)
        users = list(res.scalars().all())
        if not users:
            print(f"User {DEMO_EMAIL} not found, skipping demo seed.")
            return

        user = users[0]
        user_id = user.id

        # 1. Ensure company exists and set demo company name
        company = await CompanyRepository.get_or_create_for_user(session, user)
        company.name = DEMO_COMPANY_NAME
        company.updated_at = func.now()
        await session.flush()

        # 2. Ensure built-in criteria exist
        await CriteriaRepository.get_or_create_builtins(session, user_id)

        # 3. Clean existing demo evaluations for demo user
        await session.execute(
            delete(Evaluation)
            .where(Evaluation.user_id == user_id)
            .execution_options(synchronize_session=False)
        )
        await session.flush()

        # 4. Upsert demo locations by name (case-insensitive) in order
        demo_lower_names = {name.lower() for name, _, _ in DEMO_LOCATIONS}
        existing_locs_stmt = select(Location).where(Location.company_id == company.id)
        existing_locs = list((await session.execute(existing_locs_stmt)).scalars().all())
        for loc in existing_locs:
            if loc.name.strip().lower() not in demo_lower_names:
                await session.delete(loc)
        await session.flush()

        loc_by_name = {}
        for loc_name, loc_city, pos in DEMO_LOCATIONS:
            loc_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.location.{loc_name.lower()}")
            loc_by_id_stmt = select(Location).where(Location.id == loc_id)
            loc_by_id = (await session.execute(loc_by_id_stmt)).scalar_one_or_none()

            if loc_by_id is not None:
                loc_obj = loc_by_id
                loc_obj.company_id = company.id
                loc_obj.name = loc_name
                loc_obj.city = loc_city
                loc_obj.position = pos
                loc_obj.updated_at = func.now()
            else:
                loc_obj = Location(
                    id=loc_id,
                    company_id=company.id,
                    name=loc_name,
                    city=loc_city,
                    position=pos,
                )
                session.add(loc_obj)
            loc_by_name[loc_name] = loc_obj
        await session.commit()

        # Build Criteria Snapshot for eval-1
        criteria_snapshot = [
            {
                "key": "mandatory_compliance",
                "kind": "builtin",
                "name": BUILTIN_CRITERIA_DEFAULTS["mandatory_compliance"]["name"],
                "guidance": BUILTIN_CRITERIA_DEFAULTS["mandatory_compliance"]["guidance"],
                "weight": 35,
            },
            {
                "key": "service_coverage",
                "kind": "builtin",
                "name": BUILTIN_CRITERIA_DEFAULTS["service_coverage"]["name"],
                "guidance": BUILTIN_CRITERIA_DEFAULTS["service_coverage"]["guidance"],
                "weight": 20,
            },
            {
                "key": "cost_comparability",
                "kind": "builtin",
                "name": BUILTIN_CRITERIA_DEFAULTS["cost_comparability"]["name"],
                "guidance": BUILTIN_CRITERIA_DEFAULTS["cost_comparability"]["guidance"],
                "weight": 20,
            },
            {
                "key": "sla_operational",
                "kind": "builtin",
                "name": BUILTIN_CRITERIA_DEFAULTS["sla_operational"]["name"],
                "guidance": BUILTIN_CRITERIA_DEFAULTS["sla_operational"]["guidance"],
                "weight": 15,
            },
            {
                "key": "unresolved_risks",
                "kind": "builtin",
                "name": BUILTIN_CRITERIA_DEFAULTS["unresolved_risks"]["name"],
                "guidance": BUILTIN_CRITERIA_DEFAULTS["unresolved_risks"]["guidance"],
                "weight": 10,
            },
        ]

        # Evaluation 1: Analysed (Housekeeping -> Andheri East Office)
        eval_1 = Evaluation(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            user_id=user_id,
            location_id=loc_by_name["Andheri East Office"].id,
            title="Housekeeping Services — Andheri East Office, FY 2026–27",
            category="Facilities / Housekeeping",
            status="analysed",
            criteria_snapshot=criteria_snapshot,
            created_at=datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 12, 10, 4, 30, tzinfo=timezone.utc),
        )
        session.add(eval_1)
        await session.flush()

        # Vendors for eval-1
        v_brightnest = Vendor(
            id=uuid.UUID("22222222-1111-1111-1111-111111111111"),
            evaluation_id=eval_1.id,
            name="BrightNest Facility Services",
            position=0,
        )
        v_shubh = Vendor(
            id=uuid.UUID("22222222-2222-1111-1111-111111111111"),
            evaluation_id=eval_1.id,
            name="Shubh Housekeeping Pvt Ltd",
            position=1,
        )
        v_urbankleen = Vendor(
            id=uuid.UUID("22222222-3333-1111-1111-111111111111"),
            evaluation_id=eval_1.id,
            name="UrbanKleen Services",
            position=2,
        )
        session.add_all([v_brightnest, v_shubh, v_urbankleen])
        await session.flush()

        # Upload test-pack files into storage and seed documents with real sizes, page counts, and DocumentPage rows
        storage_service = storage or get_storage()
        dataset_base = dataset_dir or settings.dataset_path

        doc_configs = [
            {
                "key": "doc_rfp",
                "id": uuid.UUID("33333333-0000-1111-1111-111111111111"),
                "vendor_id": None,
                "kind": "requirements",
                "filename": "RFP_Housekeeping_Andheri.pdf",
                "dataset_rel": Path("requirements/01_Requirements_Andheri_Housekeeping.pdf"),
            },
            {
                "key": "doc_brightnest",
                "id": uuid.UUID("33333333-1111-1111-1111-111111111111"),
                "vendor_id": v_brightnest.id,
                "kind": "proposal",
                "filename": "BrightNest_Proposal.pdf",
                "dataset_rel": Path("proposals/02_BrightNest_Proposal.pdf"),
            },
            {
                "key": "doc_shubh",
                "id": uuid.UUID("33333333-2222-1111-1111-111111111111"),
                "vendor_id": v_shubh.id,
                "kind": "proposal",
                "filename": "Shubh_Proposal.docx",
                "dataset_rel": Path("proposals/03_Shubh_Proposal.docx"),
            },
            {
                "key": "doc_urbankleen",
                "id": uuid.UUID("33333333-3333-1111-1111-111111111111"),
                "vendor_id": v_urbankleen.id,
                "kind": "proposal",
                "filename": "UrbanKleen_Proposal.pdf",
                "dataset_rel": Path("proposals/04_UrbanKleen_Proposal.pdf"),
            },
        ]

        seeded_docs: Dict[str, Document] = {}
        for cfg in doc_configs:
            rel_path: Path = cast(Path, cfg["dataset_rel"])
            file_path = dataset_base / rel_path
            filename = str(cfg["filename"])
            if not file_path.is_file():
                raise RuntimeError(
                    f"Dataset file missing for seeded document: {file_path}. Cannot seed documents without real files."
                )

            content = file_path.read_bytes()
            storage_key = f"evaluations/{eval_1.id}/{filename}"
            await storage_service.save(storage_key, content)

            detected_type, mime, page_count = validate_document_content(
                content, filename
            )
            doc_obj = Document(
                id=cast(uuid.UUID, cfg["id"]),
                evaluation_id=eval_1.id,
                vendor_id=cast(Optional[uuid.UUID], cfg["vendor_id"]),
                kind=str(cfg["kind"]),
                filename=filename,
                mime=mime,
                size_bytes=len(content),
                storage_key=storage_key,
                page_count=page_count or 1,
                status="ready",
            )
            session.add(doc_obj)
            seeded_docs[str(cfg["key"])] = doc_obj

            if detected_type == "pdf":
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    for page_idx, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text() or ""
                        session.add(
                            DocumentPage(
                                id=uuid.uuid4(),
                                document_id=doc_obj.id,
                                page_number=page_idx,
                                text=text,
                            )
                        )
            else:
                docx_pages = extract_docx_pages(content)
                for dp in docx_pages:
                    session.add(
                        DocumentPage(
                            id=uuid.uuid4(),
                            document_id=doc_obj.id,
                            page_number=dp.page_number,
                            text=dp.text,
                        )
                    )

        await session.flush()
        doc_rfp = seeded_docs["doc_rfp"]
        doc_brightnest = seeded_docs["doc_brightnest"]
        doc_shubh = seeded_docs["doc_shubh"]
        doc_urbankleen = seeded_docs["doc_urbankleen"]

        # 8 Requirements
        req_defs = [
            ("req-01", "REQ-01", "Minimum 12 housekeeping staff on site, Mon–Sat, 8 am–8 pm", "Staffing", True, "≥12 staff per shift", 3, "§2.1", 0),
            ("req-02", "REQ-02", "Washroom cleaning every 2 hours with checklist", "Service", True, "Every ≤2 h, checklist provided", 3, "§2.3", 1),
            ("req-03", "REQ-03", "Washroom consumables included in monthly fee", "Commercial", True, "Priced within base fee", 5, "§4.1", 2),
            ("req-04", "REQ-04", "Quarterly deep cleaning of carpets and upholstery", "Service", False, "4 per year", 4, "§2.6", 3),
            ("req-05", "REQ-05", "On-site supervisor during all shifts", "Staffing", True, "Supervisor per shift", 3, "§2.2", 4),
            ("req-06", "REQ-06", "Ad-hoc cleaning response within 2 hours", "SLA", False, "Response ≤2 h stated", 4, "§3.1", 5),
            ("req-07", "REQ-07", "Monthly pest control", "Service", False, "12 treatments per year", 4, "§2.8", 6),
            ("req-08", "REQ-08", "Police verification and PF/ESIC compliance", "Compliance", True, "Certificates provided", 6, "§5.2", 7),
        ]
        req_map = {}
        for short_id, code, text, cat, mand, acc, p, sec, pos in req_defs:
            r_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.req.{code}")
            req_obj = Requirement(
                id=r_id,
                evaluation_id=eval_1.id,
                code=code,
                text=text,
                category=cat,
                mandatory=mand,
                acceptance=acc,
                source_document_id=doc_rfp.id,
                source_page=p,
                source_section=sec,
                position=pos,
                origin="extracted",
            )
            session.add(req_obj)
            req_map[code] = req_obj
        await session.flush()

        # 24 Findings
        findings_data: List[Tuple[Any, ...]] = [
            # REQ-01
            (req_map["REQ-01"], v_brightnest, "Compliant", False, False, "High", "BrightNest commits to deploying 12 trained housekeeping operatives across the operational window 8:00 AM to 8:00 PM, Monday through Saturday.", doc_brightnest, 2, "§2.1 Staffing Schedule", [], None, None),
            (req_map["REQ-01"], v_shubh, "Compliant", False, False, "High", "A dedicated team of 14 housekeeping personnel (12 primary + 2 relievers) will be stationed on-site from 08:00 to 20:00, Mon–Sat.", doc_shubh, 3, "§1.2 Manpower Deployment", [], None, None),
            (req_map["REQ-01"], v_urbankleen, "Not evidenced", True, True, "Low", "UrbanKleen will provide adequate manpower as required to maintain premier cleanliness. Shift sizes fluctuate based on client footfall.", doc_urbankleen, 3, "§2.0 Manpower Scope", ["Ambiguity", "Contradiction"], "Medium", "Please confirm the exact number of staff deployed per shift."),

            # REQ-02
            (req_map["REQ-02"], v_brightnest, "Compliant", False, False, "High", "Washroom sanitation will occur on a strict 2-hour cadence with QR-verified digital checklists.", doc_brightnest, 3, "§2.4 Restroom SLA", [], None, None),
            (req_map["REQ-02"], v_shubh, "Compliant", False, False, "High", "Restroom checks and sanitisation are scheduled every 90 to 120 minutes with physical sign-off cards.", doc_shubh, 4, "§2.1 Washroom Protocols", [], None, None),
            (req_map["REQ-02"], v_urbankleen, "Partially compliant", False, False, "High", "Restroom maintenance conducted three times daily: morning, midday, and evening.", doc_urbankleen, 4, "§2.3 Restroom Schedule", [], None, None),

            # REQ-03
            (req_map["REQ-03"], v_brightnest, "Non-compliant", False, False, "High", "Washroom consumables (tissue, hand wash, air freshener) are not included and will be billed at actuals.", doc_brightnest, 4, "§3.2 Exclusions", ["Exclusion", "Unknown cost"], "High", "Please provide a fixed monthly rate for washroom consumables, or confirm a cap on billing at actuals."),
            (req_map["REQ-03"], v_shubh, "Compliant", False, False, "High", "All standard washroom consumables (Kimberly-Clark or equivalent soap, rolls, sanitisers) are fully inclusive in the monthly billing.", doc_shubh, 5, "§3.1 Consumables Guarantee", [], None, None),
            (req_map["REQ-03"], v_urbankleen, "Not evidenced", False, True, "Low", None, None, None, None, [], None, "Please clarify whether washroom consumables are included in the base fee or billed separately."),

            # REQ-04
            (req_map["REQ-04"], v_brightnest, "Non-compliant", False, False, "High", "Carpet extraction and upholstery shampooing are excluded from routine scope and available on billable work orders.", doc_brightnest, 4, "§3.2 Exclusions", ["Exclusion"], "Medium", None),
            (req_map["REQ-04"], v_shubh, "Compliant", False, False, "High", "Quarterly deep extraction cleaning of all carpeted workspaces and fabric chairs included at no additional charge.", doc_shubh, 6, "§2.8 Periodic Deep Cleans", [], None, None),
            (req_map["REQ-04"], v_urbankleen, "Partially compliant", False, False, "High", "Deep carpet shampooing is optional at ₹18,000 per quarter.", doc_urbankleen, 5, "§4.2 Optional Add-ons", [], None, None),

            # REQ-05
            (req_map["REQ-05"], v_brightnest, "Compliant", False, False, "High", "One dedicated full-time site supervisor will oversee housekeeping operations throughout each active shift.", doc_brightnest, 2, "§2.2 Supervisory Structure", [], None, None),
            (req_map["REQ-05"], v_shubh, "Compliant", False, False, "High", "24×7 on-site supervisory presence ensures compliance with client quality matrices.", doc_shubh, 3, "§1.3 Supervision", [], None, None),
            (req_map["REQ-05"], v_urbankleen, "Compliant", False, False, "High", "A shift supervisor is assigned to the facility during all working hours.", doc_urbankleen, 2, "§1.4 Management", [], None, None),

            # REQ-06
            (req_map["REQ-06"], v_brightnest, "Not evidenced", False, True, "Low", None, None, None, None, [], None, "Please confirm SLA response time for emergency/ad-hoc cleaning spills."),
            (req_map["REQ-06"], v_shubh, "Compliant", False, False, "High", "Immediate incident and spill response guaranteed within 45 to 90 minutes of dispatch call.", doc_shubh, 5, "§3.4 Incident Response SLA", [], None, None),
            (req_map["REQ-06"], v_urbankleen, "Not evidenced", False, True, "Low", None, None, None, None, [], None, "Please confirm SLA response time for ad-hoc requests."),

            # REQ-07
            (req_map["REQ-07"], v_brightnest, "Partially compliant", False, False, "Medium", "Pest control services available on request through our licensed pest management affiliate; rate card provided upon survey.", doc_brightnest, 5, "§3.5 Allied Services", ["Unknown cost"], "Medium", "Please quote a fixed monthly price for pest control."),
            (req_map["REQ-07"], v_shubh, "Compliant", False, False, "High", "Monthly herbal pest management and gel baiting included in base proposal pricing.", doc_shubh, 6, "§2.9 Pest Control Program", [], None, None),
            (req_map["REQ-07"], v_urbankleen, "Compliant", False, False, "High", "Monthly general disinfection and pest mitigation treatments included in the contract.", doc_urbankleen, 4, "§2.5 Pest Control", [], None, None),

            # REQ-08
            (req_map["REQ-08"], v_brightnest, "Compliant", False, False, "High", "100% police verification records and statutory PF/ESIC compliance challans submitted monthly.", doc_brightnest, 6, "§5.1 Statutory Compliance", [], None, None),
            (req_map["REQ-08"], v_shubh, "Compliant", False, False, "High", "Full compliance with central and state labour acts; background verification dossier provided per staff member.", doc_shubh, 7, "§5.2 Compliance Certifications", [], None, None),
            (req_map["REQ-08"], v_urbankleen, "Compliant", False, False, "High", "All deployed personnel are police-verified with active PF and ESIC registrations.", doc_urbankleen, 6, "§5.1 Statutory Obligations", [], None, None),
        ]

        for req_obj, vendor_obj, stat, n_rev, is_inf, conf, qte, doc_obj, pg, ev_sec, risks, sev, clarif_q in findings_data:
            finding = Finding(
                id=uuid.uuid4(),
                evaluation_id=eval_1.id,
                vendor_id=vendor_obj.id,
                requirement_id=req_obj.id,
                criterion_key=None,
                status=stat,
                needs_review=n_rev,
                is_inference=is_inf,
                confidence=conf,
                evidence_quote=qte,
                evidence_document_id=doc_obj.id if doc_obj else None,
                evidence_page=pg,
                evidence_section=ev_sec,
                risk_types=risks,
                severity=sev,
                clarification_question=clarif_q,
            )
            session.add(finding)

        # Raw Criterion Scores (exactly as requested)
        raw_scores_data = [
            # Mandatory compliance
            (v_brightnest.id, "mandatory_compliance", 83),
            (v_shubh.id, "mandatory_compliance", 100),
            (v_urbankleen.id, "mandatory_compliance", 67),

            # Service coverage
            (v_brightnest.id, "service_coverage", 65),
            (v_shubh.id, "service_coverage", 90),
            (v_urbankleen.id, "service_coverage", 70),

            # Cost comparability
            (v_brightnest.id, "cost_comparability", 55),
            (v_shubh.id, "cost_comparability", 70),
            (v_urbankleen.id, "cost_comparability", 60),

            # SLA / operational
            (v_brightnest.id, "sla_operational", 50),
            (v_shubh.id, "sla_operational", 80),
            (v_urbankleen.id, "sla_operational", 20),

            # Unresolved risks
            (v_brightnest.id, "unresolved_risks", 35),
            (v_shubh.id, "unresolved_risks", 70),
            (v_urbankleen.id, "unresolved_risks", 55),
        ]

        for v_id, ckey, sc in raw_scores_data:
            cs = CriterionScore(
                id=uuid.uuid4(),
                evaluation_id=eval_1.id,
                vendor_id=v_id,
                criterion_key=ckey,
                score=sc,
            )
            session.add(cs)

        # Cost Breakdowns
        cb_brightnest = CostBreakdown(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            vendor_id=v_brightnest.id,
            monthly_base=385000,
            gst_18=69300,
            monthly_total=454300,
            included=["Staffing", "supervisor"],
            excluded=["Consumables", "deep cleaning"],
            optional=[],
            unknown=['Pest control "on request"', "consumables at actuals"],
        )
        cb_shubh = CostBreakdown(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            vendor_id=v_shubh.id,
            monthly_base=460000,
            gst_18=82800,
            monthly_total=542800,
            included=["Staffing", "24×7 supervisor", "consumables", "deep cleaning", "pest control"],
            excluded=[],
            optional=[],
            unknown=[],
        )
        cb_urbankleen = CostBreakdown(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            vendor_id=v_urbankleen.id,
            monthly_base=410000,
            gst_18=73800,
            monthly_total=483800,
            included=["Staffing", "pest control"],
            excluded=[],
            optional=["Deep cleaning ₹18,000/quarter"],
            unknown=["Weekend coverage"],
        )
        session.add_all([cb_brightnest, cb_shubh, cb_urbankleen])

        # Clarifications (4 unanswered total across user)
        # BrightNest: 2 questions
        session.add(Clarification(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            vendor_id=v_brightnest.id,
            question="Please provide a fixed monthly rate for washroom consumables, or confirm a cap on billing at actuals.",
            answered=False,
        ))
        session.add(Clarification(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            vendor_id=v_brightnest.id,
            question="Please quote a fixed monthly price for pest control.",
            answered=False,
        ))
        # UrbanKleen: 2 questions
        session.add(Clarification(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            vendor_id=v_urbankleen.id,
            question="Please confirm the exact number of staff deployed per shift.",
            answered=False,
        ))
        session.add(Clarification(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            vendor_id=v_urbankleen.id,
            question="Please confirm whether Sunday and holiday coverage is included.",
            answered=False,
        ))

        # Job for eval-1
        session.add(AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=eval_1.id,
            kind="analyse",
            status="done",
            step_label="Complete",
            started_at=datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 10, 12, 10, 4, 30, tzinfo=timezone.utc),
        ))

        # Load frozen outputs
        frozen_fixtures_path = dataset_base / "frozen_evaluations.json"
        if not frozen_fixtures_path.is_file():
            raise RuntimeError(
                f"Frozen evaluations fixture missing: {frozen_fixtures_path}. Run live capture first."
            )
        with open(frozen_fixtures_path, "r", encoding="utf-8") as f:
            frozen_data = json.load(f)

        # Evaluation 2: Requirements review (Security -> Powai Campus)
        eval_2 = Evaluation(
            id=uuid.UUID("11111111-2222-1111-1111-111111111111"),
            user_id=user_id,
            location_id=loc_by_name["Powai Campus"].id,
            title="Security Services — Powai Campus",
            category="Facilities / Security",
            status="requirements_review",
            criteria_snapshot=None,
            created_at=datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 10, 8, 30, 0, tzinfo=timezone.utc),
        )
        session.add(eval_2)
        await session.flush()

        v_secureshield = Vendor(
            id=uuid.UUID("22222222-1111-2222-1111-111111111111"),
            evaluation_id=eval_2.id,
            name="SecureShield Guards",
            position=0,
        )
        v_apex = Vendor(
            id=uuid.UUID("22222222-2222-2222-1111-111111111111"),
            evaluation_id=eval_2.id,
            name="Apex Patrol Services",
            position=1,
        )
        session.add_all([v_secureshield, v_apex])
        await session.flush()

        powai_docs_cfg = [
            ("doc_rfp_powai", uuid.UUID("33333333-0000-2222-1111-111111111111"), None, "requirements", "RFP_Security_Powai.pdf", Path("requirements/05_Requirements_Powai_Security.pdf"), "requirements"),
            ("doc_secureshield", uuid.UUID("33333333-1111-2222-1111-111111111111"), v_secureshield.id, "proposal", "SecureShield_Proposal.pdf", Path("proposals/06_SecureShield_Proposal.pdf"), "secureshield"),
            ("doc_apex", uuid.UUID("33333333-2222-2222-1111-111111111111"), v_apex.id, "proposal", "Apex_Proposal.docx", Path("proposals/07_Apex_Proposal.docx"), "apex"),
        ]
        powai_docs: Dict[str, Document] = {}
        for key, doc_id, doc_vendor_id, kind, filename, rel_path, page_key in powai_docs_cfg:
            content = (dataset_base / rel_path).read_bytes()
            storage_key = f"evaluations/{eval_2.id}/{filename}"
            await storage_service.save(storage_key, content)
            _, mime, page_count = validate_document_content(content, filename)
            doc_obj = Document(
                id=doc_id,
                evaluation_id=eval_2.id,
                vendor_id=doc_vendor_id,
                kind=kind,
                filename=filename,
                mime=mime,
                size_bytes=len(content),
                storage_key=storage_key,
                page_count=page_count or 1,
                status="ready",
            )
            session.add(doc_obj)
            powai_docs[key] = doc_obj
            for p in frozen_data["powai"]["pages"][page_key]:
                session.add(
                    DocumentPage(
                        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.page.{doc_id}.{p['page_number']}"),
                        document_id=doc_id,
                        page_number=p["page_number"],
                        text=p["text"],
                    )
                )
        await session.flush()

        doc_rfp_powai = powai_docs["doc_rfp_powai"]
        for r in frozen_data["powai"]["requirements"]:
            session.add(
                Requirement(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval2.req.{r['code']}"),
                    evaluation_id=eval_2.id,
                    code=r["code"],
                    text=r["text"],
                    category=r["category"],
                    mandatory=r["mandatory"],
                    acceptance=r["acceptance"],
                    source_document_id=doc_rfp_powai.id,
                    source_page=r["source_page"],
                    source_section=r["source_section"],
                    position=r["position"],
                    origin="extracted",
                )
            )

        # Powai: exactly one completed extraction job, no analysis results
        session.add(AnalysisJob(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "vixenone.eval2.job.extract"),
            evaluation_id=eval_2.id,
            kind="extract_requirements",
            status="done",
            step_label="Complete",
            started_at=datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 10, 10, 8, 1, 30, tzinfo=timezone.utc),
        ))

        # Evaluation 3: Stale (Pantry -> BKC Office)
        eval_3 = Evaluation(
            id=uuid.UUID("11111111-3333-1111-1111-111111111111"),
            user_id=user_id,
            location_id=loc_by_name["BKC Office"].id,
            title="Pantry & Cafeteria — BKC Office",
            category="Facilities / Housekeeping",
            status="stale",
            criteria_snapshot=criteria_snapshot,
            created_at=datetime(2026, 10, 8, 9, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 8, 9, 21, 15, tzinfo=timezone.utc),
        )
        session.add(eval_3)
        await session.flush()

        v_freshbite = Vendor(
            id=uuid.UUID("22222222-1111-3333-1111-111111111111"),
            evaluation_id=eval_3.id,
            name="FreshBite Caterers",
            position=0,
        )
        v_gourmet = Vendor(
            id=uuid.UUID("22222222-2222-3333-1111-111111111111"),
            evaluation_id=eval_3.id,
            name="Gourmet Pantry Co",
            position=1,
        )
        session.add_all([v_freshbite, v_gourmet])
        await session.flush()

        pantry_docs_cfg = [
            ("doc_rfp_pantry", uuid.UUID("33333333-0000-3333-1111-111111111111"), None, "requirements", "RFP_Pantry_BKC.pdf", Path("requirements/08_Requirements_Pantry_BKC.pdf"), "requirements"),
            ("doc_freshbite", uuid.UUID("33333333-1111-3333-1111-111111111111"), v_freshbite.id, "proposal", "FreshBite_Proposal.docx", Path("proposals/09_FreshBite_Proposal.docx"), "freshbite"),
            ("doc_gourmet", uuid.UUID("33333333-2222-3333-1111-111111111111"), v_gourmet.id, "proposal", "Gourmet_Proposal.pdf", Path("proposals/10_Gourmet_Proposal.pdf"), "gourmet"),
        ]
        pantry_docs: Dict[str, Document] = {}
        for key, doc_id, doc_vendor_id, kind, filename, rel_path, page_key in pantry_docs_cfg:
            content = (dataset_base / rel_path).read_bytes()
            storage_key = f"evaluations/{eval_3.id}/{filename}"
            await storage_service.save(storage_key, content)
            _, mime, page_count = validate_document_content(content, filename)
            doc_obj = Document(
                id=doc_id,
                evaluation_id=eval_3.id,
                vendor_id=doc_vendor_id,
                kind=kind,
                filename=filename,
                mime=mime,
                size_bytes=len(content),
                storage_key=storage_key,
                page_count=page_count or 1,
                status="ready",
            )
            session.add(doc_obj)
            pantry_docs[key] = doc_obj
            for p in frozen_data["pantry"]["pages"][page_key]:
                session.add(
                    DocumentPage(
                        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.page.{doc_id}.{p['page_number']}"),
                        document_id=doc_id,
                        page_number=p["page_number"],
                        text=p["text"],
                    )
                )
        await session.flush()

        doc_rfp_pantry = pantry_docs["doc_rfp_pantry"]
        pantry_req_map: Dict[str, Requirement] = {}
        for r in frozen_data["pantry"]["requirements"]:
            code = r["code"]
            # REQ-02 text changed to "up to 175 staff" and marked user-origin
            if code == "REQ-02":
                text = "Breakfast and lunch Monday to Friday for up to 175 staff (mandatory)."
                origin = "user"
            else:
                text = r["text"]
                origin = "extracted"

            r_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval3.req.{code}")
            req_obj = Requirement(
                id=r_id,
                evaluation_id=eval_3.id,
                code=code,
                text=text,
                category=r["category"],
                mandatory=r["mandatory"],
                acceptance=r["acceptance"],
                source_document_id=doc_rfp_pantry.id,
                source_page=r["source_page"],
                source_section=r["source_section"],
                position=r["position"],
                origin=origin,
            )
            session.add(req_obj)
            pantry_req_map[code] = req_obj
        await session.flush()

        # Pantry completed jobs only (no fake running/failed jobs)
        session.add(AnalysisJob(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "vixenone.eval3.job.extract"),
            evaluation_id=eval_3.id,
            kind="extract_requirements",
            status="done",
            step_label="Complete",
            started_at=datetime(2026, 10, 8, 9, 0, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 10, 8, 9, 1, 15, tzinfo=timezone.utc),
        ))
        session.add(AnalysisJob(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "vixenone.eval3.job.analyse"),
            evaluation_id=eval_3.id,
            kind="analyse",
            status="done",
            step_label="Complete",
            started_at=datetime(2026, 10, 8, 9, 5, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 10, 8, 9, 8, 30, tzinfo=timezone.utc),
        ))

        # Pantry analysis results
        pantry_analysis = frozen_data["pantry"]["analysis"]
        for v_obj, v_key, doc_key in [
            (v_freshbite, "freshbite", "doc_freshbite"),
            (v_gourmet, "gourmet", "doc_gourmet"),
        ]:
            v_data = pantry_analysis[v_key]
            v_doc = pantry_docs[doc_key]

            for f_idx, f in enumerate(v_data["findings"]):
                r_obj = pantry_req_map.get(f["code"]) if f.get("code") else None
                finding_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval3.finding.{v_key}.{f_idx}")
                session.add(
                    Finding(
                        id=finding_id,
                        evaluation_id=eval_3.id,
                        vendor_id=v_obj.id,
                        requirement_id=r_obj.id if r_obj else None,
                        criterion_key=f.get("criterion_key"),
                        status=f["status"],
                        needs_review=f["needs_review"],
                        is_inference=f["is_inference"],
                        confidence=f["confidence"],
                        evidence_quote=f["evidence_quote"],
                        evidence_document_id=v_doc.id if f["evidence_quote"] else None,
                        evidence_page=f["evidence_page"],
                        evidence_section=f["evidence_section"],
                        risk_types=f["risk_types"],
                        severity=f["severity"],
                        clarification_question=f["clarification_question"],
                    )
                )

            costs_data = v_data["costs"]
            session.add(
                CostBreakdown(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval3.cost.{v_key}"),
                    evaluation_id=eval_3.id,
                    vendor_id=v_obj.id,
                    monthly_base=costs_data["monthly_base"],
                    gst_18=costs_data["gst_18"],
                    monthly_total=costs_data["monthly_total"],
                    included=costs_data["included"],
                    excluded=costs_data["excluded"],
                    optional=costs_data["optional"],
                    unknown=costs_data["unknown"],
                )
            )

            for c_key, c_score in v_data["scores"].items():
                session.add(
                    CriterionScore(
                        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval3.score.{v_key}.{c_key}"),
                        evaluation_id=eval_3.id,
                        vendor_id=v_obj.id,
                        criterion_key=c_key,
                        score=c_score,
                    )
                )

            for q_idx, q_text in enumerate(v_data["clarifications"]):
                session.add(
                    Clarification(
                        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval3.clarif.{v_key}.{q_idx}"),
                        evaluation_id=eval_3.id,
                        vendor_id=v_obj.id,
                        question=q_text,
                        answered=False,
                    )
                )

        # Evaluation 4: Draft (Pest Control -> Thane Warehouse)
        eval_4 = Evaluation(
            id=uuid.UUID("11111111-4444-1111-1111-111111111111"),
            user_id=user_id,
            location_id=loc_by_name["Thane Warehouse"].id,
            title="Pest Control AMC — Thane Warehouse",
            category="Facilities / Housekeeping",
            status="draft",
            criteria_snapshot=None,
            created_at=datetime(2026, 10, 5, 14, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 5, 14, 0, 0, tzinfo=timezone.utc),
        )
        session.add(eval_4)
        await session.flush()

        v_termiguard = Vendor(
            id=uuid.UUID("22222222-1111-4444-1111-111111111111"),
            evaluation_id=eval_4.id,
            name="TermiGuard AMC",
            position=0,
        )
        v_safeclean = Vendor(
            id=uuid.UUID("22222222-2222-4444-1111-111111111111"),
            evaluation_id=eval_4.id,
            name="SafeClean Disinfection",
            position=1,
        )
        session.add_all([v_termiguard, v_safeclean])
        await session.flush()

        # Thane: documents uploaded (not read), no requirements, no jobs, status draft
        thane_docs_cfg = [
            ("doc_rfp_thane", uuid.UUID("33333333-0000-4444-1111-111111111111"), None, "requirements", "RFP_PestControl_Thane.pdf", Path("requirements/11_Requirements_Thane_PestControl.pdf")),
            ("doc_termiguard", uuid.UUID("33333333-1111-4444-1111-111111111111"), v_termiguard.id, "proposal", "TermiGuard_Proposal.pdf", Path("proposals/12_TermiGuard_Proposal.pdf")),
            ("doc_safeclean", uuid.UUID("33333333-2222-4444-1111-111111111111"), v_safeclean.id, "proposal", "SafeClean_Proposal.docx", Path("proposals/13_SafeClean_Proposal.docx")),
        ]
        for key, doc_id, doc_vendor_id, kind, filename, rel_path in thane_docs_cfg:
            content = (dataset_base / rel_path).read_bytes()
            storage_key = f"evaluations/{eval_4.id}/{filename}"
            await storage_service.save(storage_key, content)
            _, mime, page_count = validate_document_content(content, filename)
            session.add(
                Document(
                    id=doc_id,
                    evaluation_id=eval_4.id,
                    vendor_id=doc_vendor_id,
                    kind=kind,
                    filename=filename,
                    mime=mime,
                    size_bytes=len(content),
                    storage_key=storage_key,
                    page_count=page_count or 1,
                    status="uploaded",
                )
            )

        await session.commit()
        print("Demo evaluations, vendors, findings, scores, costs, and jobs seeded successfully.")
    finally:
        if close_session:
            await session.close()
