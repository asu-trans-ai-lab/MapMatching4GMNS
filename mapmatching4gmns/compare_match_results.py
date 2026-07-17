"""QA agent -- compare two engines' MatchedPath results and cross-check them.

A single map matcher can silently be wrong; two independent engines catch each other. This
module computes agreement on link sequence, direction, milepost range, and subarea gateways,
then classifies the pair. Map matching becomes a quality-control mechanism, not just
preprocessing.
"""

import re

HIGH = "high_confidence_match"
OK = "acceptable_match"
REVIEW = "needs_manual_review"
FAILED = "failed_match"


def _norm_link_id(lid):
    """Normalize a link_id for cross-engine comparison. Engines differ in id representation:
    the geometric engine keeps the full GMNS id ('193912AB'), while trace2route emits only
    the numeric core ('193912', dropping the AB/BA direction suffix). Strip a trailing
    letter suffix so the two are comparable -- otherwise identical matches read as total
    disagreement. (Losing the suffix means AB/BA are merged; direction is checked separately
    via start/end node.)"""
    return re.sub(r"[A-Za-z]+$", "", str(lid))


def _seq_agreement(a, b):
    """Ordered-overlap of two link sequences: |intersection| / |union| (Jaccard) plus the
    longest common ordered run fraction. Link ids are normalized first."""
    a = [_norm_link_id(x) for x in a]
    b = [_norm_link_id(x) for x in b]
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0, 1.0
    jac = len(sa & sb) / max(1, len(sa | sb))
    # longest common contiguous run (order-sensitive)
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            best = max(best, k)
    run = best / max(1, max(len(a), len(b)))
    return round(jac, 3), round(run, 3)


def compare(path_a, path_b, *, mp_tol=1.0, gateway_required=False):
    """Compare two MatchedPath. Returns a dict with agreement metrics + a verdict."""
    if path_a is None or path_b is None:
        present = path_a or path_b
        return {"verdict": REVIEW if present else FAILED,
                "reason": "only one engine returned a path" if present else "no path from either engine",
                "engines": [p.source_engine for p in (path_a, path_b) if p]}

    jac, run = _seq_agreement(path_a.matched_link_sequence, path_b.matched_link_sequence)
    # also report RAW (un-normalized) agreement for transparency: if raw << normalized, the
    # engines match the same physical links but differ in id representation (direction suffix).
    sa_raw, sb_raw = set(map(str, path_a.matched_link_sequence)), set(map(str, path_b.matched_link_sequence))
    jac_raw = round(len(sa_raw & sb_raw) / max(1, len(sa_raw | sb_raw)), 3) if (sa_raw or sb_raw) else 1.0

    # direction agreement: compare start/end nodes if both present, else milepost order sign
    dir_ok = None
    if None not in (path_a.start_node_id, path_a.end_node_id, path_b.start_node_id, path_b.end_node_id):
        dir_ok = (path_a.start_node_id == path_b.start_node_id and
                  path_a.end_node_id == path_b.end_node_id)

    # milepost-range agreement
    mp_ok = None
    if None not in (path_a.start_milepost, path_a.end_milepost,
                    path_b.start_milepost, path_b.end_milepost):
        mp_ok = (abs(path_a.start_milepost - path_b.start_milepost) <= mp_tol and
                 abs(path_a.end_milepost - path_b.end_milepost) <= mp_tol)

    # subarea gateway agreement
    gw_ok = None
    if None not in (path_a.subarea_origin_gateway, path_b.subarea_origin_gateway):
        gw_ok = (path_a.subarea_origin_gateway == path_b.subarea_origin_gateway and
                 path_a.subarea_destination_gateway == path_b.subarea_destination_gateway)

    flags = []
    if jac < 0.5:
        flags.append("link_sequence_disagreement")
    if dir_ok is False:
        flags.append("direction_mismatch")
    if mp_ok is False:
        flags.append("milepost_mismatch")
    if gw_ok is False:
        flags.append("gateway_od_mismatch")
    if gateway_required and gw_ok is None:
        flags.append("gateway_not_determined")

    if not flags and jac >= 0.8 and run >= 0.6:
        verdict = HIGH
    elif not flags and jac >= 0.5:
        verdict = OK
    elif "direction_mismatch" in flags or "gateway_od_mismatch" in flags or jac < 0.3:
        verdict = REVIEW
    else:
        verdict = OK if jac >= 0.5 else REVIEW

    if jac_raw < jac - 0.1:
        flags.append("link_id_representation_differs")   # same links, different id form
    return {"verdict": verdict, "flags": flags,
            "link_jaccard": jac, "link_jaccard_raw": jac_raw, "link_common_run": run,
            "direction_agree": dir_ok, "milepost_agree": mp_ok, "gateway_agree": gw_ok,
            "engines": [path_a.source_engine, path_b.source_engine],
            "trajectory_id": path_a.trajectory_id}
