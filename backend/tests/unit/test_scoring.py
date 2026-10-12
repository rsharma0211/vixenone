from decimal import Decimal
import pytest

from app.services.scoring import (
    compute_criterion_points,
    compute_vendor_scores,
    round_half_up,
    status_to_score,
)


def test_status_to_score():
    assert status_to_score("Compliant") == Decimal("100")
    assert status_to_score("compliant") == Decimal("100")
    assert status_to_score("Partially compliant") == Decimal("50")
    assert status_to_score("partially_compliant") == Decimal("50")
    assert status_to_score("Non-compliant") == Decimal("0")
    assert status_to_score("non_compliant") == Decimal("0")
    assert status_to_score("Not evidenced") == Decimal("0")
    assert status_to_score("not_evidenced") == Decimal("0")

    with pytest.raises(ValueError):
        status_to_score("unknown_status")


def test_exact_decimal_arithmetic_and_display_rounding():
    # 1. BrightNest mandatory compliance: 83 * 35 / 100 = 29.05 -> round half up 1 dec = 29.1
    raw_bn_mand = compute_criterion_points(Decimal("83"), Decimal("35"))
    assert raw_bn_mand == Decimal("29.05")
    disp_bn_mand = round_half_up(raw_bn_mand, 1)
    assert disp_bn_mand == Decimal("29.1")

    # 2. UrbanKleen mandatory compliance: 67 * 35 / 100 = 23.45 -> round half up 1 dec = 23.5
    raw_uk_mand = compute_criterion_points(Decimal("67"), Decimal("35"))
    assert raw_uk_mand == Decimal("23.45")
    disp_uk_mand = round_half_up(raw_uk_mand, 1)
    assert disp_uk_mand == Decimal("23.5"), f"Expected 23.45 half-up to be 23.5, got {disp_uk_mand}"

    # Verify rounding half up to whole numbers for totals
    assert round_half_up(Decimal("64.05"), 0) == Decimal("64")
    assert round_half_up(Decimal("86.00"), 0) == Decimal("86")
    assert round_half_up(Decimal("57.95"), 0) == Decimal("58")


def test_compute_vendor_scores_exact_demo_fixtures():
    snapshot = [
        {"key": "mandatory_compliance", "weight": 35},
        {"key": "service_coverage", "weight": 20},
        {"key": "cost_comparability", "weight": 20},
        {"key": "sla_operational", "weight": 15},
        {"key": "unresolved_risks", "weight": 10},
    ]

    # BrightNest: 83, 65, 55, 50, 35
    bn_scores = {
        "mandatory_compliance": Decimal("83"),
        "service_coverage": Decimal("65"),
        "cost_comparability": Decimal("55"),
        "sla_operational": Decimal("50"),
        "unresolved_risks": Decimal("35"),
    }
    bn_res = compute_vendor_scores(bn_scores, snapshot)
    assert bn_res["incomplete"] is False
    assert bn_res["raw_total"] == Decimal("64.05")
    assert bn_res["display_total"] == 64
    assert bn_res["criteria_scores"]["mandatory_compliance"]["points"] == Decimal("29.1")
    assert bn_res["criteria_scores"]["mandatory_compliance"]["raw_points"] == Decimal("29.05")

    # Shubh: 100, 90, 70, 80, 70
    sh_scores = {
        "mandatory_compliance": Decimal("100"),
        "service_coverage": Decimal("90"),
        "cost_comparability": Decimal("70"),
        "sla_operational": Decimal("80"),
        "unresolved_risks": Decimal("70"),
    }
    sh_res = compute_vendor_scores(sh_scores, snapshot)
    assert sh_res["incomplete"] is False
    assert sh_res["raw_total"] == Decimal("86.00")
    assert sh_res["display_total"] == 86
    assert sh_res["criteria_scores"]["mandatory_compliance"]["points"] == Decimal("35.0")
    assert sh_res["criteria_scores"]["mandatory_compliance"]["raw_points"] == Decimal("35.00")

    # UrbanKleen: 67, 70, 60, 20, 55
    uk_scores = {
        "mandatory_compliance": Decimal("67"),
        "service_coverage": Decimal("70"),
        "cost_comparability": Decimal("60"),
        "sla_operational": Decimal("20"),
        "unresolved_risks": Decimal("55"),
    }
    uk_res = compute_vendor_scores(uk_scores, snapshot)
    assert uk_res["incomplete"] is False
    assert uk_res["raw_total"] == Decimal("57.95")
    assert uk_res["display_total"] == 58
    assert uk_res["criteria_scores"]["mandatory_compliance"]["points"] == Decimal("23.5")
    assert uk_res["criteria_scores"]["mandatory_compliance"]["raw_points"] == Decimal("23.45")


def test_missing_criterion_score_marks_incomplete():
    snapshot = [
        {"key": "mandatory_compliance", "weight": 35},
        {"key": "service_coverage", "weight": 20},
        {"key": "cost_comparability", "weight": 20},
        {"key": "sla_operational", "weight": 15},
        {"key": "unresolved_risks", "weight": 10},
    ]

    # Missing unresolved_risks
    scores = {
        "mandatory_compliance": Decimal("83"),
        "service_coverage": Decimal("65"),
        "cost_comparability": Decimal("55"),
        "sla_operational": Decimal("50"),
    }
    res = compute_vendor_scores(scores, snapshot)
    assert res["incomplete"] is True
    assert res["raw_total"] is None
    assert res["display_total"] is None
    cell = res["criteria_scores"]["unresolved_risks"]
    assert cell["score"] is None
    assert cell["points"] is None
    assert cell["raw_points"] is None
