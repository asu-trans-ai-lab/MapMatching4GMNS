"""CI test: the synthetic golden case must self-demo PASS (geometric engine minimum)."""
import csv
import os
from mapmatching4gmns.selfdemo import run_case

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _set_decision(review_csv, decision, replacement=""):
    rows = list(csv.DictReader(open(review_csv, encoding="utf-8-sig")))
    rows[0]["reviewer_decision"] = decision
    rows[0]["replacement_link_ids"] = replacement
    with open(review_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


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


# --- Milestone 4: GUI review contract + apply-review ---
NET = os.path.join(ROOT, "examples", "self_demo", "00_synthetic")


def _run_synth(tmp_path):
    out = str(tmp_path / "case_output")
    run_case("synthetic", ROOT, out_dir=out)
    return out


def test_apply_review_accept_geometric(tmp_path):
    from mapmatching4gmns.apply_review import apply_review
    out = _run_synth(tmp_path)
    # the geometric route the reviewer will accept
    geo = [r["link_id"] for r in csv.DictReader(open(os.path.join(out, "geometric_route.csv"), encoding="utf-8-sig"))]
    _set_decision(os.path.join(out, "match_review.csv"), "ACCEPT_GEOMETRIC")
    s = apply_review(out, network_dir=NET)
    assert s["n_applied"] == 1 and s["n_rejected"] == 0
    reviewed = [r["link_id"] for r in csv.DictReader(open(os.path.join(out, "reviewed_route.csv"), encoding="utf-8-sig"))]
    assert reviewed == geo
    assert os.path.exists(os.path.join(out, "match_review_resolved.csv"))


def test_apply_review_replace_path_validates(tmp_path):
    from mapmatching4gmns.apply_review import apply_review
    out = _run_synth(tmp_path)
    # a real connected mainline chain from the synthetic network
    _set_decision(os.path.join(out, "match_review.csv"), "REPLACE_PATH", "1001AB;1002AB;1003AB")
    s = apply_review(out, network_dir=NET)
    assert s["n_applied"] == 1 and s["n_rejected"] == 0
    reviewed = [r["link_id"] for r in csv.DictReader(open(os.path.join(out, "reviewed_route.csv"), encoding="utf-8-sig"))]
    assert reviewed == ["1001AB", "1002AB", "1003AB"]


def test_apply_review_rejects_unknown_links_and_empty_replace(tmp_path):
    from mapmatching4gmns.apply_review import apply_review
    out = _run_synth(tmp_path)
    _set_decision(os.path.join(out, "match_review.csv"), "REPLACE_PATH", "9999XX")  # not in network
    s = apply_review(out, network_dir=NET)
    assert s["n_rejected"] == 1 and s["rows"][0]["status"] == "REJECTED"
    _set_decision(os.path.join(out, "match_review.csv"), "REPLACE_PATH", "")         # missing links
    assert apply_review(out, network_dir=NET)["n_rejected"] == 1
