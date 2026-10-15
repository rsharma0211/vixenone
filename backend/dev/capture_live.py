"""Live Gemini capture script for VixenOne demo evaluation packs.

Runs live Gemini extraction on Powai and extraction + analysis on Pantry.
Executes Story Checks against ground truth rules.
Freezes outputs to backend/dataset/frozen_evaluations.json.

Excluded from production Docker image via backend/.dockerignore.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List

from app.llm.client import (
    GoogleGenAIClient,
    PageText,
    create_gemini_client,
)
from app.schemas.criteria import BUILTIN_CRITERIA_DEFAULTS
from app.services.ingestion import extract_docx_pages
from app.services.scoring import (
    compute_cost_amounts,
    compute_raw_criterion_scores,
    deduplicate_clarifications,
)
from app.services.verification import verify_quote_against_pages
from app.services.worker import (
    _map_level_display,
    _map_risk_types_display,
    _map_status_display,
)

CRITERIA_SNAPSHOT = [
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


async def run_live_capture(dataset_dir: Path) -> Dict[str, Any]:
    if os.environ.get("RUN_GEMINI_LIVE") != "1":
        raise RuntimeError("RUN_GEMINI_LIVE=1 environment variable must be set to run live capture.")

    client = create_gemini_client()
    captured_data: Dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "powai": {},
        "pantry": {},
    }

    # ==========================================================================
    # POWAI — Security Services
    # ==========================================================================
    print("\n--- 1. POWAI LIVE EXTRACTION ---")
    powai_req_bytes = (dataset_dir / "requirements" / "05_Requirements_Powai_Security.pdf").read_bytes()
    powai_sec_bytes = (dataset_dir / "proposals" / "06_SecureShield_Proposal.pdf").read_bytes()
    powai_apex_bytes = (dataset_dir / "proposals" / "07_Apex_Proposal.docx").read_bytes()

    print("Extracting Powai document page text...")
    powai_req_pages = await client.pdf_to_pages(powai_req_bytes)
    powai_sec_pages = await client.pdf_to_pages(powai_sec_bytes)
    powai_apex_pages = extract_docx_pages(powai_apex_bytes)

    print("Extracting Powai requirements with Gemini...")
    powai_extracted_reqs = await client.extract_requirements(powai_req_pages)

    # STORY CHECK: Powai
    # 6 requirements, 4 mandatory, each with a source page.
    powai_total_reqs = len(powai_extracted_reqs)
    powai_mand_reqs = sum(1 for r in powai_extracted_reqs if r.mandatory)
    powai_missing_page = [r.code for r in powai_extracted_reqs if not r.source_page]

    print(f"Powai Story Check: {powai_total_reqs} reqs, {powai_mand_reqs} mandatory, missing page: {powai_missing_page}")
    for idx, r in enumerate(powai_extracted_reqs):
        print(f"  [{r.code or f'R{idx+1}'}] mand={r.mandatory} page={r.source_page} text={r.text[:60]}...")

    if powai_total_reqs != 6:
        raise RuntimeError(f"STORY CHECK FAILED: Powai expected 6 requirements, got {powai_total_reqs}")
    if powai_mand_reqs != 4:
        raise RuntimeError(f"STORY CHECK FAILED: Powai expected 4 mandatory requirements, got {powai_mand_reqs}")
    if powai_missing_page:
        raise RuntimeError(f"STORY CHECK FAILED: Powai requirements missing source page: {powai_missing_page}")

    captured_data["powai"] = {
        "pages": {
            "requirements": [p.model_dump() for p in powai_req_pages],
            "secureshield": [p.model_dump() for p in powai_sec_pages],
            "apex": [p.model_dump() for p in powai_apex_pages],
        },
        "requirements": [
            {
                "code": r.code or f"REQ-0{idx+1}",
                "text": r.text,
                "category": r.category,
                "mandatory": r.mandatory,
                "acceptance": r.acceptance,
                "source_page": r.source_page,
                "source_section": r.source_section,
                "position": idx,
            }
            for idx, r in enumerate(powai_extracted_reqs)
        ],
    }

    # ==========================================================================
    # PANTRY — Pantry & Cafeteria, BKC
    # ==========================================================================
    print("\n--- 2. PANTRY LIVE EXTRACTION & ANALYSIS ---")
    pantry_req_bytes = (dataset_dir / "requirements" / "08_Requirements_Pantry_BKC.pdf").read_bytes()
    pantry_fresh_bytes = (dataset_dir / "proposals" / "09_FreshBite_Proposal.docx").read_bytes()
    pantry_gourmet_bytes = (dataset_dir / "proposals" / "10_Gourmet_Proposal.pdf").read_bytes()

    print("Extracting Pantry document page text...")
    pantry_req_pages = await client.pdf_to_pages(pantry_req_bytes)
    pantry_fresh_pages = extract_docx_pages(pantry_fresh_bytes)
    pantry_gourmet_pages = await client.pdf_to_pages(pantry_gourmet_bytes)

    print("Extracting Pantry requirements with Gemini...")
    pantry_extracted_reqs = await client.extract_requirements(pantry_req_pages)

    # STORY CHECK: Pantry requirements
    # 5 requirements, 3 mandatory
    pantry_total_reqs = len(pantry_extracted_reqs)
    pantry_mand_reqs = sum(1 for r in pantry_extracted_reqs if r.mandatory)
    pantry_missing_page = [r.code for r in pantry_extracted_reqs if not r.source_page]

    print(f"Pantry Story Check (Reqs): {pantry_total_reqs} reqs, {pantry_mand_reqs} mandatory, missing page: {pantry_missing_page}")
    for idx, r in enumerate(pantry_extracted_reqs):
        print(f"  [{r.code or f'REQ-0{idx+1}'}] mand={r.mandatory} page={r.source_page} text={r.text[:60]}...")

    if pantry_total_reqs != 5:
        raise RuntimeError(f"STORY CHECK FAILED: Pantry expected 5 requirements, got {pantry_total_reqs}")
    if pantry_mand_reqs != 3:
        raise RuntimeError(f"STORY CHECK FAILED: Pantry expected 3 mandatory requirements, got {pantry_mand_reqs}")
    if pantry_missing_page:
        raise RuntimeError(f"STORY CHECK FAILED: Pantry requirements missing source page: {pantry_missing_page}")

    pantry_req_descriptors = [
        {
            "id": f"pantry-req-{idx+1}",
            "code": r.code or f"REQ-0{idx+1}",
            "text": r.text,
            "category": r.category,
            "mandatory": r.mandatory,
            "acceptance": r.acceptance,
            "source_page": r.source_page,
            "source_section": r.source_section,
            "position": idx,
        }
        for idx, r in enumerate(pantry_extracted_reqs)
    ]

    judged_criteria = [
        c for c in CRITERIA_SNAPSHOT if c["key"] in ("service_coverage", "sla_operational")
    ]

    print("Analysing FreshBite Caterers...")
    freshbite_res = await client.analyse_vendor(
        vendor_name="FreshBite Caterers",
        requirements=pantry_req_descriptors,
        judged_criteria=judged_criteria,
        pages=pantry_fresh_pages,
    )

    print("Analysing Gourmet Pantry Co...")
    gourmet_res = await client.analyse_vendor(
        vendor_name="Gourmet Pantry Co",
        requirements=pantry_req_descriptors,
        judged_criteria=judged_criteria,
        pages=pantry_gourmet_pages,
    )

    def process_vendor_analysis(vendor_name: str, res: Any, pages: List[PageText]) -> Dict[str, Any]:
        rf_by_code = {
            (rf.code or "").strip().lower(): rf
            for rf in res.requirement_findings
            if rf.code
        }
        mandatory_statuses: List[str] = []
        vendor_risk_items: List[Dict[str, Any]] = []
        vendor_questions: List[str] = []
        findings_out: List[Dict[str, Any]] = []

        # 1. Requirement findings
        for r_desc in pantry_req_descriptors:
            r_code = r_desc["code"]
            r_mand = r_desc["mandatory"]
            rf = rf_by_code.get(r_code.strip().lower())

            if rf is not None:
                status_display = _map_status_display(rf.status)
                raw_quote = rf.quote
                raw_page = rf.page
                raw_section = rf.section.strip() if rf.section and rf.section.strip() else None
                conf_display = _map_level_display(rf.confidence, default="High") or "High"
                is_inf = bool(rf.is_inference)
                risks_display = _map_risk_types_display(rf.risk_types)
                sev_display = _map_level_display(rf.severity, default="Medium" if risks_display else None)
                q = rf.clarification_question.strip() if rf.clarification_question and rf.clarification_question.strip() else None
            else:
                status_display = "Not evidenced"
                raw_quote = None
                raw_page = None
                raw_section = None
                conf_display = "Low"
                is_inf = True
                risks_display = []
                sev_display = None
                q = f"Please confirm compliance with {r_code}."

            v_quote, v_page, needs_rev = verify_quote_against_pages(
                status=status_display,
                quote=raw_quote,
                cited_page=raw_page,
                pages=pages,
            )

            if r_mand:
                mandatory_statuses.append(status_display)

            if risks_display:
                vendor_risk_items.append({"risk_types": risks_display, "severity": sev_display or "Medium"})
            if q:
                vendor_questions.append(q)

            findings_out.append({
                "code": r_code,
                "criterion_key": None,
                "status": status_display,
                "needs_review": needs_rev,
                "is_inference": is_inf,
                "confidence": conf_display,
                "evidence_quote": v_quote,
                "evidence_page": v_page,
                "evidence_section": raw_section,
                "risk_types": risks_display,
                "severity": sev_display,
                "clarification_question": q,
            })

        # 2. Judged criterion findings
        cf_by_key = {
            (cf.key or "").strip(): cf
            for cf in res.criterion_findings
            if cf.key
        }
        criterion_status_by_key: Dict[str, Any] = {}
        for jc in judged_criteria:
            j_key = jc["key"]
            cf = cf_by_key.get(j_key)
            if cf is not None:
                c_status = _map_status_display(cf.status)
                criterion_status_by_key[j_key] = c_status
                v_quote, v_page, c_needs_rev = verify_quote_against_pages(
                    status=c_status,
                    quote=cf.quote,
                    cited_page=cf.page,
                    pages=pages,
                )
                c_sec = cf.section.strip() if cf.section and cf.section.strip() else None
                findings_out.append({
                    "code": None,
                    "criterion_key": j_key,
                    "status": c_status,
                    "needs_review": c_needs_rev,
                    "is_inference": False,
                    "confidence": "High",
                    "evidence_quote": v_quote,
                    "evidence_page": v_page,
                    "evidence_section": c_sec,
                    "risk_types": [],
                    "severity": None,
                    "clarification_question": None,
                })
            else:
                criterion_status_by_key[j_key] = None

        # 3. Standalone risks
        for sr in getattr(res, "risks", []):
            sr_risks = _map_risk_types_display(sr.risk_types)
            sr_sev = _map_level_display(sr.severity, default="Medium") or "Medium"
            sr_quote, sr_page, sr_rev = verify_quote_against_pages(
                status="non_compliant" if sr.quote else "not_evidenced",
                quote=sr.quote,
                cited_page=sr.page,
                pages=pages,
            )
            sr_sec = sr.section.strip() if sr.section and sr.section.strip() else None
            sr_q = sr.clarification_question.strip() if sr.clarification_question and sr.clarification_question.strip() else None
            if sr_risks:
                vendor_risk_items.append({"risk_types": sr_risks, "severity": sr_sev})
            if sr_q:
                vendor_questions.append(sr_q)
            findings_out.append({
                "code": None,
                "criterion_key": None,
                "status": "Not evidenced",
                "needs_review": sr_rev,
                "is_inference": not bool(sr_quote),
                "confidence": "Medium",
                "evidence_quote": sr_quote,
                "evidence_page": sr_page,
                "evidence_section": sr_sec,
                "risk_types": sr_risks,
                "severity": sr_sev,
                "clarification_question": sr_q,
            })

        # 4. Costs
        raw_inc = [x.item.strip() for x in res.cost.included if x.item and x.item.strip()]
        raw_exc = [x.item.strip() for x in res.cost.excluded if x.item and x.item.strip()]
        raw_opt = [x.item.strip() for x in res.cost.optional if x.item and x.item.strip()]
        raw_unk = [x.item.strip() for x in res.cost.unknown if x.item and x.item.strip()]

        cost_calc = compute_cost_amounts(
            monthly_base=res.cost.monthly_base,
            unknown_items=raw_unk,
        )

        # 5. Raw scores
        raw_scores = compute_raw_criterion_scores(
            criteria_snapshot=CRITERIA_SNAPSHOT,
            mandatory_statuses=mandatory_statuses,
            criterion_findings_by_key=criterion_status_by_key,
            monthly_base=res.cost.monthly_base,
            unknown_items=raw_unk,
            findings_and_risks=vendor_risk_items,
        )

        # 6. Clarifications
        deduped_q = deduplicate_clarifications(vendor_questions)

        return {
            "vendor_name": vendor_name,
            "mandatory_statuses": mandatory_statuses,
            "findings": findings_out,
            "costs": {
                "monthly_base": cost_calc["monthly_base"],
                "gst_18": cost_calc["gst_18"],
                "monthly_total": cost_calc["monthly_total"],
                "included": raw_inc,
                "excluded": raw_exc,
                "optional": raw_opt,
                "unknown": cost_calc["unknown"],
            },
            "scores": raw_scores,
            "clarifications": deduped_q,
        }

    freshbite_data = process_vendor_analysis("FreshBite Caterers", freshbite_res, pantry_fresh_pages)
    gourmet_data = process_vendor_analysis("Gourmet Pantry Co", gourmet_res, pantry_gourmet_pages)

    # STORY CHECKS: Pantry Analysis
    # - FreshBite meets all 3 mandatory
    # - Gourmet has at least one mandatory not met or partly
    # - Monthly base 210000 / 185000
    # - Gourmet has at least one unknown cost item
    print("\n--- PANTRY STORY CHECKS ---")
    fb_mand_met = all(s == "Compliant" for s in freshbite_data["mandatory_statuses"])
    gourmet_mand_has_gap = any(s != "Compliant" for s in gourmet_data["mandatory_statuses"])
    fb_base = freshbite_data["costs"]["monthly_base"]
    gourmet_base = gourmet_data["costs"]["monthly_base"]
    gourmet_unknown_count = len(gourmet_data["costs"]["unknown"])

    print(f"FreshBite mandatory met (all 3): {fb_mand_met} (statuses: {freshbite_data['mandatory_statuses']})")
    print(f"Gourmet mandatory has gap: {gourmet_mand_has_gap} (statuses: {gourmet_data['mandatory_statuses']})")
    print(f"Monthly base fees: FreshBite={fb_base}, Gourmet={gourmet_base}")
    print(f"Gourmet unknown cost items: {gourmet_unknown_count} items: {gourmet_data['costs']['unknown']}")

    if not fb_mand_met:
        raise RuntimeError(f"STORY CHECK FAILED: FreshBite did not meet all 3 mandatory: {freshbite_data['mandatory_statuses']}")
    if not gourmet_mand_has_gap:
        raise RuntimeError(f"STORY CHECK FAILED: Gourmet was expected to have at least one mandatory gap: {gourmet_data['mandatory_statuses']}")
    if fb_base != 210000:
        raise RuntimeError(f"STORY CHECK FAILED: FreshBite monthly base expected 210000, got {fb_base}")
    if gourmet_base != 185000:
        raise RuntimeError(f"STORY CHECK FAILED: Gourmet monthly base expected 185000, got {gourmet_base}")
    if gourmet_unknown_count < 1:
        raise RuntimeError(f"STORY CHECK FAILED: Gourmet expected >=1 unknown cost item, got {gourmet_unknown_count}")

    captured_data["pantry"] = {
        "pages": {
            "requirements": [p.model_dump() for p in pantry_req_pages],
            "freshbite": [p.model_dump() for p in pantry_fresh_pages],
            "gourmet": [p.model_dump() for p in pantry_gourmet_pages],
        },
        "requirements": pantry_req_descriptors,
        "analysis": {
            "freshbite": freshbite_data,
            "gourmet": gourmet_data,
        },
    }

    def _json_default(obj: Any) -> Any:
        from decimal import Decimal
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    out_file = dataset_dir / "frozen_evaluations.json"
    out_file.write_text(json.dumps(captured_data, indent=2, default=_json_default))
    print(f"\nAll story checks PASSED. Frozen outputs written to {out_file}")
    return captured_data


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent / "dataset"
    asyncio.run(run_live_capture(base))
