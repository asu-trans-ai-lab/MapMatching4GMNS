"""Match verification — does a matched route pass the case's own thresholds?

Checks connectivity, direction, expected-route agreement, cross-engine agreement, coverage, and
unmatched points, and returns a graded verdict (never forces an ambiguous match into a binary
pass):  PASS · PASS_WITH_ENGINE_DISAGREEMENT · REVIEW_REQUIRED · FAIL.
Thresholds come from the case's expected.yml (per-case, not global).
"""
import csv
import os


def _link_topology(network_dir):
    """link_id -> (from_node, to_node), plus a normalized-id helper."""
    topo = {}
    with open(os.path.join(network_dir, "link.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            topo[str(r["link_id"])] = (str(r["from_node_id"]), str(r["to_node_id"]))
    return topo


def _is_connected(links, topo):
    """True if the link sequence forms a connected directed chain (to_node == next from_node)."""
    seq = [l for l in links if l in topo]
    if len(seq) < 2:
        return len(seq) == 1
    for i in range(len(seq) - 1):
        if topo[seq[i]][1] != topo[seq[i + 1]][0]:
            return False
    return True


def _jaccard(a, b):
    import re
    na = set(re.sub(r"[A-Za-z]+$", "", str(x)) for x in a)
    nb = set(re.sub(r"[A-Za-z]+$", "", str(x)) for x in b)
    if not na and not nb:
        return 1.0
    return len(na & nb) / max(1, len(na | nb))


def verify(*, hmm_links, geometric_links, trusted_links, expected, network_dir,
           trace_coverage=None, unmatched_points=0):
    """Return a verification dict + verdict. Engine-adaptive: skips HMM checks if it did not run."""
    topo = _link_topology(network_dir)
    exp = expected.get("expected_route_links", [])
    checks = {}

    # connectivity + direction of the trusted path
    checks["connected_path"] = _is_connected(trusted_links, topo)
    want_dir = str(expected.get("expected_direction", "")).upper()
    if want_dir:
        checks["direction"] = all(str(l).upper().endswith(want_dir) for l in trusted_links) if trusted_links else False

    # expected-route agreement per engine (only if that engine ran and expected is given)
    if exp:
        if geometric_links is not None:
            checks["geometric_expected_jaccard"] = round(_jaccard(geometric_links, exp), 3)
        if hmm_links is not None:
            checks["hmm_expected_jaccard"] = round(_jaccard(hmm_links, exp), 3)

    # cross-engine agreement (only if both ran)
    cross = None
    if hmm_links is not None and geometric_links is not None:
        cross = round(_jaccard(hmm_links, geometric_links), 3)
        checks["cross_engine_jaccard"] = cross
    if trace_coverage is not None:
        checks["trace_coverage"] = round(trace_coverage, 3)
    checks["unmatched_points"] = unmatched_points

    # ---- grade against per-case thresholds ----
    fails, warns = [], []
    if expected.get("expected_connected_path") and not checks["connected_path"]:
        fails.append("not_connected")
    if want_dir and checks.get("direction") is False:
        fails.append("wrong_direction")
    if "geometric_expected_jaccard" in checks and \
       checks["geometric_expected_jaccard"] < expected.get("minimum_geometric_expected_jaccard", 0):
        fails.append("geometric_below_expected")
    if "hmm_expected_jaccard" in checks and \
       checks["hmm_expected_jaccard"] < expected.get("minimum_hmm_expected_jaccard", 0):
        fails.append("hmm_below_expected")
    if trace_coverage is not None and trace_coverage < expected.get("minimum_trace_coverage", 0):
        fails.append("low_coverage")
    if unmatched_points > expected.get("maximum_unmatched_points", 1e9):
        fails.append("too_many_unmatched")
    if cross is not None and cross < expected.get("minimum_cross_engine_jaccard", 0):
        warns.append("engine_disagreement")

    if fails:
        verdict = "FAIL"
    elif warns:
        verdict = "PASS_WITH_ENGINE_DISAGREEMENT" if warns == ["engine_disagreement"] else "REVIEW_REQUIRED"
    else:
        verdict = "PASS"
    return {"verdict": verdict, "checks": checks, "failures": fails, "warnings": warns}
