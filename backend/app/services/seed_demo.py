from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import uuid
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.criteria import EvaluationCriterion
from app.models.evaluation import (
    AnalysisJob,
    Clarification,
    CostBreakdown,
    CriterionScore,
    Document,
    Evaluation,
    Finding,
    Requirement,
    Vendor,
)
from app.models.user import User
from app.repositories.criteria_repo import CriteriaRepository
from app.schemas.criteria import BUILTIN_CRITERIA_DEFAULTS, CriterionKind

DEMO_EMAIL = "demo@vixenone.app"


async def seed_demo_data(session: Optional[AsyncSession] = None) -> None:
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
        for extra in users[1:]:
            await session.delete(extra)
        await session.flush()

        user_id = user.id

        # 1. Ensure built-in criteria exist
        await CriteriaRepository.get_or_create_builtins(session, user_id)

        # 2. Clean existing demo evaluations for demo user
        existing_evals_stmt = select(Evaluation).where(Evaluation.user_id == user_id)
        existing_evals = (await session.execute(existing_evals_stmt)).scalars().all()
        for e in existing_evals:
            await session.delete(e)
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

        # Evaluation 1: Analysed
        eval_1 = Evaluation(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            user_id=user_id,
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

        # Documents for eval-1
        doc_rfp = Document(
            id=uuid.UUID("33333333-0000-1111-1111-111111111111"),
            evaluation_id=eval_1.id,
            vendor_id=None,
            kind="requirements",
            filename="RFP_Housekeeping_Andheri.pdf",
            mime="application/pdf",
            size_bytes=245000,
            storage_key=f"evaluations/{eval_1.id}/RFP_Housekeeping_Andheri.pdf",
            page_count=6,
            status="ready",
        )
        doc_brightnest = Document(
            id=uuid.UUID("33333333-1111-1111-1111-111111111111"),
            evaluation_id=eval_1.id,
            vendor_id=v_brightnest.id,
            kind="proposal",
            filename="BrightNest_Proposal.pdf",
            mime="application/pdf",
            size_bytes=512000,
            storage_key=f"evaluations/{eval_1.id}/BrightNest_Proposal.pdf",
            page_count=8,
            status="ready",
        )
        doc_shubh = Document(
            id=uuid.UUID("33333333-2222-1111-1111-111111111111"),
            evaluation_id=eval_1.id,
            vendor_id=v_shubh.id,
            kind="proposal",
            filename="Shubh_Proposal.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=420000,
            storage_key=f"evaluations/{eval_1.id}/Shubh_Proposal.docx",
            page_count=10,
            status="ready",
        )
        doc_urbankleen = Document(
            id=uuid.UUID("33333333-3333-1111-1111-111111111111"),
            evaluation_id=eval_1.id,
            vendor_id=v_urbankleen.id,
            kind="proposal",
            filename="UrbanKleen_Proposal.pdf",
            mime="application/pdf",
            size_bytes=610000,
            storage_key=f"evaluations/{eval_1.id}/UrbanKleen_Proposal.pdf",
            page_count=9,
            status="ready",
        )
        session.add_all([doc_rfp, doc_brightnest, doc_shubh, doc_urbankleen])
        await session.flush()

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
        findings_data = [
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

        for req_obj, vendor_obj, stat, n_rev, is_inf, conf, qte, doc_obj, pg, sec, risks, sev, clarif_q in findings_data:
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
                evidence_section=sec,
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

        # Evaluation 2: Requirements review
        eval_2 = Evaluation(
            id=uuid.UUID("11111111-2222-1111-1111-111111111111"),
            user_id=user_id,
            title="Security Services — Powai Campus",
            category="Facilities / Security",
            status="requirements_review",
            criteria_snapshot=None,
            created_at=datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 10, 8, 30, 0, tzinfo=timezone.utc),
        )
        session.add(eval_2)
        await session.flush()
        session.add(Vendor(id=uuid.uuid4(), evaluation_id=eval_2.id, name="SecureShield Guards", position=0))
        session.add(Vendor(id=uuid.uuid4(), evaluation_id=eval_2.id, name="Apex Patrol Services", position=1))

        eval_2_req_defs = [
            ("REQ-01", "Security coverage", True, "Trained guards on duty 24×7 at all three campus gates.", "Duty roster shows continuous cover at each gate.", 0),
            ("REQ-02", "Compliance", True, "Agency holds a valid private security agency licence for Maharashtra.", "Copy of current licence attached.", 1),
            ("REQ-03", "Supervision", True, "One security supervisor on site for every shift.", "Supervisor named in the shift roster.", 2),
            ("REQ-04", "Operations", True, "Visitor log maintained at reception for every entry and exit.", "Register or digital log described.", 3),
            ("REQ-05", "Training", False, "Guards complete fire-safety training within 30 days of deployment.", "Training plan with timeline.", 4),
            ("REQ-06", "Reporting", False, "Monthly incident report shared with the facilities manager.", "Report format and schedule stated.", 5),
        ]
        for code, cat, mand, text, acc, pos in eval_2_req_defs:
            session.add(
                Requirement(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval2.req.{code}"),
                    evaluation_id=eval_2.id,
                    code=code,
                    text=text,
                    category=cat,
                    mandatory=mand,
                    acceptance=acc,
                    source_document_id=None,
                    source_page=None,
                    source_section=None,
                    position=pos,
                    origin="extracted",
                )
            )

        session.add(AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=eval_2.id,
            kind="analyse",
            status="analysing",
            step_label="Reading proposal — page 9 of 16",
            started_at=datetime(2026, 10, 12, 11, 15, 0, tzinfo=timezone.utc),
        ))

        # Evaluation 3: Stale
        eval_3 = Evaluation(
            id=uuid.UUID("11111111-3333-1111-1111-111111111111"),
            user_id=user_id,
            title="Pantry & Cafeteria — BKC Office",
            category="Facilities / Housekeeping",
            status="stale",
            criteria_snapshot=None,
            created_at=datetime(2026, 10, 8, 9, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 8, 9, 21, 15, tzinfo=timezone.utc),
        )
        session.add(eval_3)
        await session.flush()
        session.add(Vendor(id=uuid.uuid4(), evaluation_id=eval_3.id, name="FreshBite Caterers", position=0))
        session.add(Vendor(id=uuid.uuid4(), evaluation_id=eval_3.id, name="Gourmet Pantry Co", position=1))

        eval_3_req_defs = [
            ("REQ-01", "Compliance", True, "Caterer holds a valid FSSAI licence.", "Copy of current licence attached.", 0),
            ("REQ-02", "Service coverage", True, "Breakfast and lunch served Monday to Friday for up to 150 staff.", "Meal schedule and capacity stated.", 1),
            ("REQ-03", "Hygiene", True, "Daily kitchen hygiene checklist signed by the supervisor.", "Checklist format described.", 2),
            ("REQ-04", "Operations", False, "Weekly menu shared every Friday.", "Menu process stated.", 3),
            ("REQ-05", "Service coverage", False, "Pantry tea and coffee stations refilled twice daily.", "Refill schedule stated.", 4),
        ]
        for code, cat, mand, text, acc, pos in eval_3_req_defs:
            session.add(
                Requirement(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"vixenone.eval3.req.{code}"),
                    evaluation_id=eval_3.id,
                    code=code,
                    text=text,
                    category=cat,
                    mandatory=mand,
                    acceptance=acc,
                    source_document_id=None,
                    source_page=None,
                    source_section=None,
                    position=pos,
                    origin="extracted",
                )
            )

        session.add(AnalysisJob(
            id=uuid.uuid4(),
            evaluation_id=eval_3.id,
            kind="extract_requirements",
            status="failed",
            step_label="Failed during extraction",
            error_message="PDF extraction failed: Corrupted document header on cafeteria_rates.pdf",
            started_at=datetime(2026, 10, 8, 9, 20, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 10, 8, 9, 21, 15, tzinfo=timezone.utc),
        ))

        # Evaluation 4: Draft
        eval_4 = Evaluation(
            id=uuid.UUID("11111111-4444-1111-1111-111111111111"),
            user_id=user_id,
            title="Pest Control AMC — Thane Warehouse",
            category="Facilities / Housekeeping",
            status="draft",
            criteria_snapshot=None,
            created_at=datetime(2026, 10, 5, 14, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 10, 5, 14, 0, 0, tzinfo=timezone.utc),
        )
        session.add(eval_4)
        await session.flush()
        session.add(Vendor(id=uuid.uuid4(), evaluation_id=eval_4.id, name="TermiGuard AMC", position=0))
        session.add(Vendor(id=uuid.uuid4(), evaluation_id=eval_4.id, name="SafeClean Disinfection", position=1))

        await session.commit()
        print("Demo evaluations, vendors, findings, scores, costs, and jobs seeded successfully.")
    finally:
        if close_session:
            await session.close()
