from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Sequence, Union

from app.services.verification import normalise_text_for_verification

MISSING_BASE_UNKNOWN_LABEL = "Monthly base price not stated"


def status_to_score(status: str) -> Decimal:
    """Map compliance status to a raw score between 0 and 100.

    Compliant: 100
    Partially compliant: 50
    Non-compliant: 0
    Not evidenced: 0
    """
    normalized = status.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized == "compliant":
        return Decimal("100")
    if normalized in ("partially_compliant", "partial"):
        return Decimal("50")
    if normalized in ("non_compliant", "noncompliant"):
        return Decimal("0")
    if normalized in ("not_evidenced", "notevidenced"):
        return Decimal("0")
    raise ValueError(f"Unknown compliance status: {status}")


def round_half_up(val: Decimal, places: int = 1) -> Decimal:
    """Round a Decimal using ROUND_HALF_UP rule.

    places=1: round to 1 decimal place (e.g. 23.45 -> 23.5, 29.05 -> 29.1)
    places=0: round to whole number (e.g. 64.05 -> 64, 57.95 -> 58)
    """
    if places <= 0:
        exp = Decimal("1")
    else:
        exp = Decimal("10") ** (-places)
    return val.quantize(exp, rounding=ROUND_HALF_UP)


def compute_criterion_points(raw_score: Decimal, weight: Decimal) -> Decimal:
    """Compute exact unrounded points for a criterion."""
    return (raw_score * weight) / Decimal("100")


def compute_mandatory_compliance_score(mandatory_statuses: Sequence[str]) -> Decimal:
    """mandatory_compliance = average status score over mandatory requirements (none mandatory -> 100)."""
    if not mandatory_statuses:
        return Decimal("100")
    total = sum((status_to_score(s) for s in mandatory_statuses), Decimal("0"))
    avg = total / Decimal(len(mandatory_statuses))
    quantized = avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return quantized.normalize() if quantized == quantized.to_integral() else quantized


def compute_judged_criterion_score(finding_status: Optional[str]) -> Decimal:
    """service_coverage, sla_operational and every custom key = status score of that criterion finding (missing -> 0)."""
    if finding_status is None or not str(finding_status).strip():
        return Decimal("0")
    return status_to_score(str(finding_status))


def compute_cost_comparability_score(
    monthly_base: Optional[Any] = None,
    unknown_count: Union[int, Sequence[Any]] = 0,
    *,
    base_missing: Optional[bool] = None,
    unknown_items: Optional[Sequence[Any]] = None,
) -> Decimal:
    """cost_comparability = 100 - 40 if base missing - 15 per extracted unknown item; floor 0."""
    is_base_missing = (
        base_missing if base_missing is not None else (monthly_base is None)
    )
    if unknown_items is not None:
        count = len(unknown_items)
    elif isinstance(unknown_count, (int, float, Decimal)):
        count = max(0, int(unknown_count))
    elif isinstance(unknown_count, (list, tuple, set, Sequence)):
        count = len(unknown_count)
    else:
        count = 0

    deduction = (Decimal("40") if is_base_missing else Decimal("0")) + (
        Decimal("15") * Decimal(count)
    )
    return max(Decimal("0"), Decimal("100") - deduction)


def compute_unresolved_risks_score(findings_and_risks: Sequence[Any]) -> Decimal:
    """unresolved_risks = 100 - (high 20, medium 10, low 5) per finding or risk with any risk type; floor 0."""
    severity_weights = {
        "high": Decimal("20"),
        "medium": Decimal("10"),
        "low": Decimal("5"),
    }
    deduction = Decimal("0")
    for item in findings_and_risks:
        if isinstance(item, dict):
            risk_types = item.get("risk_types") or []
            severity = item.get("severity")
        else:
            risk_types = getattr(item, "risk_types", None) or []
            severity = getattr(item, "severity", None)

        if not risk_types:
            continue

        sev_str = (
            getattr(severity, "value", severity) if severity is not None else ""
        )
        norm_sev = str(sev_str).strip().lower()
        deduction += severity_weights.get(norm_sev, Decimal("0"))

    return max(Decimal("0"), Decimal("100") - deduction)


def compute_raw_criterion_scores(
    criteria_snapshot: Sequence[Dict[str, Any]],
    mandatory_statuses: Sequence[str],
    criterion_findings_by_key: Dict[str, Optional[str]],
    monthly_base: Optional[Any],
    unknown_items: Sequence[Any],
    findings_and_risks: Sequence[Any],
) -> Dict[str, Decimal]:
    """Compute a raw 0-100 score for every snapshot key for one vendor."""
    scores: Dict[str, Decimal] = {}
    for item in criteria_snapshot:
        key = item["key"]
        if key == "mandatory_compliance":
            scores[key] = compute_mandatory_compliance_score(mandatory_statuses)
        elif key == "cost_comparability":
            scores[key] = compute_cost_comparability_score(
                monthly_base=monthly_base,
                unknown_count=unknown_items,
            )
        elif key == "unresolved_risks":
            scores[key] = compute_unresolved_risks_score(findings_and_risks)
        else:
            scores[key] = compute_judged_criterion_score(
                criterion_findings_by_key.get(key)
            )
    return scores


def compute_cost_amounts(
    monthly_base: Optional[Any],
    unknown_items: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Compute exact Decimal GST (18%) and monthly_total from monthly_base.

    Base null -> gst and total null, and add 'Monthly base price not stated' to unknown.
    """
    unknown_list: List[str] = [
        str(u).strip() for u in (unknown_items or []) if u and str(u).strip()
    ]
    if monthly_base is None:
        if MISSING_BASE_UNKNOWN_LABEL not in unknown_list:
            unknown_list.append(MISSING_BASE_UNKNOWN_LABEL)
        return {
            "monthly_base": None,
            "gst_18": None,
            "monthly_total": None,
            "unknown": unknown_list,
        }

    base_dec = Decimal(str(monthly_base)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    gst_dec = (base_dec * Decimal("0.18")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_dec = (base_dec + gst_dec).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "monthly_base": base_dec,
        "gst_18": gst_dec,
        "monthly_total": total_dec,
        "unknown": unknown_list,
    }


def deduplicate_clarifications(questions: Sequence[Optional[str]]) -> List[str]:
    """Return non-empty clarification questions deduplicated on normalised text in order."""
    seen: set[str] = set()
    result: List[str] = []
    for q in questions:
        if not q or not q.strip():
            continue
        trimmed = q.strip()
        norm = normalise_text_for_verification(trimmed).rstrip(".?!:; ")
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(trimmed)
    return result


def compute_recommendation(
    vendors_summary: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute deterministic recommendation from vendor summaries.

    Each vendor dict in vendors_summary contains:
        - id (or vendor_id): str
        - name: str
        - exact_total (or raw_score): Decimal | float | None
        - mandatory_failures: int
        - mandatory_not_evidenced: int
        - mandatory_needs_review: int

    Returns:
        {
            "state": "recommended" | "insufficient",
            "vendor_id": str | None,
            "reasons": List[str],
        }
    """
    analysed_vendors: List[Dict[str, Any]] = []
    for v in vendors_summary:
        vid = str(v.get("vendor_id") or v.get("id") or "")
        name = str(v.get("name") or vid)
        raw_tot = (
            v.get("exact_total")
            if v.get("exact_total") is not None
            else v.get("raw_score")
        )
        if raw_tot is None:
            continue
        analysed_vendors.append(
            {
                "vendor_id": vid,
                "name": name,
                "exact_total": Decimal(str(raw_tot)),
                "mandatory_failures": int(v.get("mandatory_failures") or 0),
                "mandatory_not_evidenced": int(
                    v.get("mandatory_not_evidenced") or 0
                ),
                "mandatory_needs_review": int(
                    v.get("mandatory_needs_review") or 0
                ),
            }
        )

    if len(analysed_vendors) < 2:
        return {
            "state": "insufficient",
            "vendor_id": None,
            "reasons": ["At least 2 analysed vendors are required for a recommendation."],
        }

    eligible = [v for v in analysed_vendors if v["mandatory_failures"] == 0]

    # Collect per-vendor issue reasons
    vendor_issue_reasons: List[str] = []
    for v in analysed_vendors:
        vname = v["name"]
        mf = v["mandatory_failures"]
        mne = v["mandatory_not_evidenced"]
        mnr = v["mandatory_needs_review"]
        if mf > 0:
            noun = "mandatory requirement not met" if mf == 1 else "mandatory requirements not met"
            vendor_issue_reasons.append(f"{vname}: {mf} {noun}.")
        if mne > 0:
            noun = (
                "mandatory requirement without evidence"
                if mne == 1
                else "mandatory requirements without evidence"
            )
            vendor_issue_reasons.append(f"{vname}: {mne} {noun}.")
        if mnr > 0:
            noun = (
                "mandatory requirement needs review"
                if mnr == 1
                else "mandatory requirements need review"
            )
            vendor_issue_reasons.append(f"{vname}: {mnr} {noun}.")

    if not eligible:
        return {
            "state": "insufficient",
            "vendor_id": None,
            "reasons": vendor_issue_reasons
            or ["All vendors have mandatory requirements not met."],
        }

    max_total = max(v["exact_total"] for v in eligible)
    top_eligible = [v for v in eligible if v["exact_total"] == max_total]

    if len(top_eligible) > 1:
        tied_names = ", ".join(v["name"] for v in top_eligible)
        tie_rounded = int(round_half_up(max_total, 0))
        reasons = [
            f"Tie on total score ({tie_rounded}) between eligible vendors: {tied_names}."
        ] + vendor_issue_reasons
        return {
            "state": "insufficient",
            "vendor_id": None,
            "reasons": reasons,
        }

    top_vendor = top_eligible[0]
    if (
        top_vendor["mandatory_not_evidenced"] > 0
        or top_vendor["mandatory_needs_review"] > 0
    ):
        top_reasons: List[str] = []
        vname = top_vendor["name"]
        mne = top_vendor["mandatory_not_evidenced"]
        mnr = top_vendor["mandatory_needs_review"]
        if mne > 0:
            noun = (
                "mandatory requirement without evidence"
                if mne == 1
                else "mandatory requirements without evidence"
            )
            top_reasons.append(f"{vname}: {mne} {noun}.")
        if mnr > 0:
            noun = (
                "mandatory requirement needs review"
                if mnr == 1
                else "mandatory requirements need review"
            )
            top_reasons.append(f"{vname}: {mnr} {noun}.")
        for r in vendor_issue_reasons:
            if r not in top_reasons:
                top_reasons.append(r)
        return {
            "state": "insufficient",
            "vendor_id": None,
            "reasons": top_reasons,
        }

    # Clean recommendation for top_vendor
    top_rounded = int(round_half_up(top_vendor["exact_total"], 0))
    rec_reasons: List[str] = [
        f"Highest total score ({top_rounded}) and all mandatory requirements met."
    ]
    for v in analysed_vendors:
        if v["vendor_id"] == top_vendor["vendor_id"]:
            continue
        if v["mandatory_failures"] > 0:
            mf = v["mandatory_failures"]
            noun = "mandatory requirement not met" if mf == 1 else "mandatory requirements not met"
            rec_reasons.append(f"{v['name']}: {mf} {noun}.")

    return {
        "state": "recommended",
        "vendor_id": top_vendor["vendor_id"],
        "reasons": rec_reasons,
    }


def compute_vendor_scores(
    raw_scores: Dict[str, Optional[Decimal]],
    criteria_snapshot: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute exact and display points and total for a single vendor across snapshot criteria.

    Returns:
        {
            "criteria_scores": {
                criterion_key: {
                    "score": Decimal | None,
                    "points": Decimal | None (display rounded 1 dec),
                    "raw_points": Decimal | None (exact)
                }
            },
            "raw_total": Decimal | None (exact unrounded),
            "display_total": int | None (whole number),
            "incomplete": bool
        }
    """
    result: Dict[str, Any] = {
        "criteria_scores": {},
        "raw_total": None,
        "display_total": None,
        "incomplete": False,
    }

    raw_points_list: List[Decimal] = []
    has_missing = False

    for item in criteria_snapshot:
        key = item["key"]
        weight = Decimal(str(item["weight"]))
        raw_score = raw_scores.get(key)

        if raw_score is None:
            has_missing = True
            result["criteria_scores"][key] = {
                "score": None,
                "points": None,
                "raw_points": None,
            }
        else:
            raw_score_dec = Decimal(str(raw_score))
            exact_points = compute_criterion_points(raw_score_dec, weight)
            display_points = round_half_up(exact_points, 1)
            raw_points_list.append(exact_points)

            result["criteria_scores"][key] = {
                "score": raw_score_dec,
                "points": display_points,
                "raw_points": exact_points,
            }

    if has_missing:
        result["incomplete"] = True
        result["raw_total"] = None
        result["display_total"] = None
    else:
        raw_total = sum(raw_points_list, Decimal("0"))
        result["incomplete"] = False
        result["raw_total"] = raw_total
        result["display_total"] = int(round_half_up(raw_total, 0))

    return result
