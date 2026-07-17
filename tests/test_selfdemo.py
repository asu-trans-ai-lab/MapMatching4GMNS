"""CI test: the synthetic golden case must self-demo PASS (geometric engine minimum)."""
import os
from mapmatching4gmns.selfdemo import run_case

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_synthetic_self_demo_pass():
    s = run_case("synthetic", ROOT)
    assert s["verdict"] in ("PASS", "PASS_WITH_ENGINE_DISAGREEMENT"), s
    assert s["verification"]["checks"]["connected_path"] is True
    assert s["verification"]["checks"]["geometric_expected_jaccard"] >= 0.90
    assert s["baseline"]["matches_baseline"] is True


def test_tmc_self_demo_pass():
    s = run_case("tmc", ROOT)
    assert s["verdict"] in ("PASS", "PASS_WITH_ENGINE_DISAGREEMENT"), s
    c = s["verification"]["checks"]
    assert c["milepost_monotonic"] and c["sequence_preserved"]
    assert c["tmc_coverage"] >= 0.90 and c["gateways_traversed"]
    assert s["baseline"]["matches_baseline"] is True


def test_i95_trip_self_demo_pass():
    s = run_case("i95_trip", ROOT)
    assert s["verdict"] in ("PASS", "PASS_WITH_ENGINE_DISAGREEMENT"), s
    assert s["verification"]["checks"]["connected_path"] is True


def test_i95_cv_self_demo_pass():
    s = run_case("i95_cv", ROOT)
    assert s["verdict"] in ("PASS", "PASS_WITH_ENGINE_DISAGREEMENT", "REVIEW_REQUIRED"), s
    assert s["verification"]["checks"]["thinning_stability"] >= 0.6
