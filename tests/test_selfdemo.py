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
