"""Installed-wheel data and dual-engine regression tests."""
import csv
import os
from pathlib import Path
import mapmatching4gmns as mm
import pytest
from mapmatching4gmns import engine_hmm_internal
from mapmatching4gmns import verify_match
from mapmatching4gmns.selfdemo import (
    _apply_baseline_gate,
    _dataset_root,
    _select_trusted,
    run_case,
)

FIXTURES = _dataset_root()


def _set_decision(review_csv, decision, replacement=""):
    rows = list(csv.DictReader(open(review_csv, encoding="utf-8-sig")))
    rows[0]["reviewer_decision"] = decision
    rows[0]["replacement_link_ids"] = replacement
    with open(review_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def test_packaged_validation_data_present():
    assert os.path.isfile(os.path.join(FIXTURES, "tmc", "expected.yml"))
    assert os.path.isfile(os.path.join(FIXTURES, "i95", "gps.csv"))


def test_native_engine_is_packaged():
    native = engine_hmm_internal.native_module()
    assert native is not None
    assert native.__version__ == mm.__version__


def test_native_failure_raises_without_exiting(tmp_path):
    native = engine_hmm_internal.native_module()
    original_cwd = os.getcwd()
    with pytest.raises(RuntimeError, match="fatal input or output error"):
        native.run_in_dir(str(tmp_path))
    assert os.getcwd() == original_cwd


def _rewrite_csv(source, destination, line_ending):
    with open(source, encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        rows = list(reader)
        fields = reader.fieldnames
    with open(destination, "w", encoding="utf-8", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fields, lineterminator=line_ending)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_native_i95_line_endings(line_ending, tmp_path):
    source = Path(FIXTURES) / "i95"
    _rewrite_csv(source / "node.csv", tmp_path / "node.csv", line_ending)
    _rewrite_csv(source / "link.csv", tmp_path / "link.csv", line_ending)

    journey_id = "39f0065e877ddec9"
    with open(source / "gps.csv", encoding="utf-8-sig", newline="") as src:
        journey_rows = [row for row in csv.DictReader(src)
                        if row["journey_id"] == journey_id]
    nodes = engine_hmm_internal._read_nodes(tmp_path / "node.csv")
    origin = engine_hmm_internal._nearest_node(
        nodes, float(journey_rows[0]["longitude"]), float(journey_rows[0]["latitude"])
    )
    destination = engine_hmm_internal._nearest_node(
        nodes, float(journey_rows[-1]["longitude"]), float(journey_rows[-1]["latitude"])
    )
    trace_fields = ["agent_id", "x_coord", "y_coord", "trace_no", "trace_id",
                    "o_node_id", "d_node_id"]
    with open(tmp_path / "trace.csv", "w", encoding="utf-8", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=trace_fields, lineterminator=line_ending)
        writer.writeheader()
        for index, row in enumerate(journey_rows):
            writer.writerow({
                "agent_id": journey_id,
                "x_coord": row["longitude"],
                "y_coord": row["latitude"],
                "trace_no": index,
                "trace_id": index,
                "o_node_id": origin if index == 0 else "",
                "d_node_id": destination if index == 0 else "",
            })

    native = engine_hmm_internal.native_module()
    rows = native.run_in_dir(str(tmp_path))
    links = [str(row["link_id"]) for row in rows if row.get("link_id")]
    assert links == ["82", "62", "118", "119", "131", "101",
                     "102", "105", "27", "128", "129", "87"]


def test_bad_native_path_is_not_trusted_and_fails_gates():
    network = os.path.join(FIXTURES, "i95")
    geometric = ["21", "42", "111", "49", "112", "113", "65", "119", "131",
                 "101", "102", "105", "27", "128", "129", "87", "23"]
    native = ["21"]
    expected = {
        "expected_connected_path": True,
        "expected_direction": "AB",
        "expected_route_links": geometric,
        "minimum_geometric_expected_jaccard": 0.9,
        "minimum_hmm_expected_jaccard": 0.9,
        "minimum_cross_engine_jaccard": 0.8,
    }
    topology = verify_match._link_topology(network)
    trusted, source = _select_trusted(native, geometric, expected, topology)
    assert trusted == geometric
    assert source == "geometric"

    verification = verify_match.verify(
        hmm_links=native,
        geometric_links=geometric,
        trusted_links=trusted,
        expected=expected,
        network_dir=network,
    )
    _apply_baseline_gate(verification, {"matches_baseline": False})
    assert verification["verdict"] == "FAIL"
    assert {"hmm_below_expected", "cross_engine_below_expected", "baseline_mismatch"} \
        <= set(verification["failures"])


def test_tmc_self_demo_pass(tmp_path):
    s = run_case("tmc", out_dir=tmp_path / "tmc")
    assert s["verdict"] == "PASS", s
    c = s["verification"]["checks"]
    assert c["milepost_monotonic"] and c["sequence_preserved"]
    assert c["tmc_coverage"] >= 0.90 and c["gateways_traversed"]
    assert s["baseline"]["matches_baseline"] is True


def test_i95_self_demo_pass(tmp_path):
    output = tmp_path / "i95"
    s = run_case("i95", out_dir=output)
    assert s["verdict"] == "PASS", s
    checks = s["verification"]["checks"]
    assert checks["input_points"] == 467
    assert checks["input_journeys"] == checks["matched_journeys"] == 5
    assert checks["all_links_known"] is True
    assert checks["all_routes_connected"] is True
    assert checks["all_routes_match_baseline"] is True
    assert s["baseline"]["matches_baseline"] is True
    assert s["trusted_source"] == "mapmatcher4gmns"
    assert os.path.isfile(output / "mapmatcher_routes.csv")
    assert os.path.isfile(output / "journey_verification.csv")


def test_gtfs_self_demo_pass(tmp_path):
    s = run_case("gtfs", out_dir=tmp_path / "gtfs")
    assert s["verdict"] == "PASS", s
    assert s["verification"]["checks"]["connected_path"] is True
    assert s["verification"]["checks"]["geometric_expected_jaccard"] >= 0.80
    assert s["baseline"]["matches_baseline"] is True


def test_lrs_self_demo_pass(tmp_path):
    s = run_case("lrs", out_dir=tmp_path / "lrs")
    assert s["verdict"] == "PASS", s
    assert s["verification"]["checks"]["connected_path"] is True
    assert s["verification"]["checks"]["lrs_event_coverage"] == 1.0
    assert s["baseline"]["matches_baseline"] is True


# --- Milestone 4: GUI review contract + apply-review ---
NET = os.path.join(FIXTURES, "tmc")


def _run_tmc(tmp_path):
    out = str(tmp_path / "case_output")
    run_case("tmc", out_dir=out)
    return out


def test_apply_review_accept_geometric(tmp_path):
    from mapmatching4gmns.apply_review import apply_review
    out = _run_tmc(tmp_path)
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
    out = _run_tmc(tmp_path)
    # a real connected mainline chain from the TMC fixture network
    _set_decision(os.path.join(out, "match_review.csv"), "REPLACE_PATH", "1001AB;1002AB;1003AB")
    s = apply_review(out, network_dir=NET)
    assert s["n_applied"] == 1 and s["n_rejected"] == 0
    reviewed = [r["link_id"] for r in csv.DictReader(open(os.path.join(out, "reviewed_route.csv"), encoding="utf-8-sig"))]
    assert reviewed == ["1001AB", "1002AB", "1003AB"]


def test_apply_review_rejects_unknown_links_and_empty_replace(tmp_path):
    from mapmatching4gmns.apply_review import apply_review
    out = _run_tmc(tmp_path)
    _set_decision(os.path.join(out, "match_review.csv"), "REPLACE_PATH", "9999XX")  # not in network
    s = apply_review(out, network_dir=NET)
    assert s["n_rejected"] == 1 and s["rows"][0]["status"] == "REJECTED"
    _set_decision(os.path.join(out, "match_review.csv"), "REPLACE_PATH", "")         # missing links
    assert apply_review(out, network_dir=NET)["n_rejected"] == 1
