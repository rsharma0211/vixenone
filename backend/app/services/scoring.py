from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple


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
        raw_total = sum(raw_points_list) if raw_points_list else Decimal("0")
        result["incomplete"] = False
        result["raw_total"] = raw_total
        result["display_total"] = int(round_half_up(raw_total, 0))

    return result
