"""apply-review — regenerate a corrected match result from a human-filled `match_review.csv`.

The review contract (`match_review.csv`) is written by the GUI review export with
`review_status=OPEN`. A reviewer fills `reviewer_decision` (and `replacement_link_ids` when the
decision is `REPLACE_PATH`), then `apply-review` reads those decisions, validates them against the
network, and writes the corrected route — WITHOUT editing the GMNS network. This is the
visual-review responsibility (a reproducible human-in-the-loop correction), not network editing.

Decisions (per row):
  ACCEPT_TRUSTED / ACCEPT_HMM / ACCEPT_GEOMETRIC  -> take that engine's link set for the row
  REPLACE_PATH        -> take `replacement_link_ids` (validated against the network topology)
  INSUFFICIENT_EVIDENCE -> accept no route; flag the row for more data

Outputs (in the case_output dir):
  reviewed_route.csv          - the corrected link sequence(s): review_id, trace_id, seq, link_id
  match_review_resolved.csv   - the input review rows + resolved review_status + applied_link_ids + apply_note
  review_applied.json         - per-row summary + counts
"""
import csv
import json
import os

DECISIONS = {"ACCEPT_TRUSTED", "ACCEPT_HMM", "ACCEPT_GEOMETRIC", "REPLACE_PATH", "INSUFFICIENT_EVIDENCE"}
_SRC_COL = {"ACCEPT_TRUSTED": "trusted_link_ids", "ACCEPT_HMM": "hmm_link_ids",
            "ACCEPT_GEOMETRIC": "geometric_link_ids"}


def _split(s):
    """Parse a ';'- or ','-delimited link id list."""
    return [x.strip() for x in str(s or "").replace(",", ";").split(";") if x.strip()]


def _resolve_row(r, topo):
    """Return (status, route_or_None, note) for one review row. `topo` may be None (no network)."""
    from .verify_match import _is_connected
    decision = (r.get("reviewer_decision") or "").strip().upper()
    if not decision:
        return "OPEN", None, "no reviewer_decision"
    if decision not in DECISIONS:
        return "REJECTED", None, f"unknown decision {decision!r}; allowed: {'|'.join(sorted(DECISIONS))}"
    if decision == "INSUFFICIENT_EVIDENCE":
        return "APPLIED", [], "flagged: insufficient evidence, no route accepted"
    if decision == "REPLACE_PATH":
        route = _split(r.get("replacement_link_ids"))
        if not route:
            return "REJECTED", None, "REPLACE_PATH requires replacement_link_ids"
        if topo is not None:
            missing = [l for l in route if l not in topo]
            if missing:
                return "REJECTED", None, f"replacement links not in network: {','.join(missing)}"
            if not _is_connected(route, topo):
                return "APPLIED", route, "warning: replacement path is not a fully connected chain"
        return "APPLIED", route, "replacement path accepted"
    # ACCEPT_* — take the recorded link set for that engine
    route = _split(r.get(_SRC_COL[decision]))
    if not route:
        return "REJECTED", None, f"{decision}: source link set is empty in the review record"
    return "APPLIED", route, f"{decision.lower()} accepted"


def apply_review(case_output_dir, review_csv=None, network_dir=None):
    """Apply reviewer decisions in `match_review.csv`; write corrected outputs. Returns a summary."""
    topo = None
    if network_dir:
        from .verify_match import _link_topology
        topo = _link_topology(network_dir)
    review_csv = review_csv or os.path.join(case_output_dir, "match_review.csv")
    if not os.path.exists(review_csv):
        raise FileNotFoundError(review_csv)
    rows = list(csv.DictReader(open(review_csv, encoding="utf-8-sig")))
    if not rows:
        raise ValueError(f"empty review file: {review_csv}")

    resolved, summary_rows = [], []
    for r in rows:
        status, route, note = _resolve_row(r, topo)
        rr = dict(r)
        rr["review_status"] = status
        rr["applied_link_ids"] = ";".join(route) if route else ""
        rr["apply_note"] = note
        resolved.append(rr)
        summary_rows.append({"review_id": r.get("review_id"), "trace_id": r.get("trace_id"),
                             "decision": (r.get("reviewer_decision") or "").strip().upper(),
                             "status": status, "n_links": len(route) if route else 0, "note": note})

    # reviewed_route.csv — every APPLIED route, expanded (supports many traces per file)
    reviewed_links = 0
    with open(os.path.join(case_output_dir, "reviewed_route.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["review_id", "trace_id", "seq", "link_id"])
        for rr in resolved:
            if rr["review_status"] == "APPLIED" and rr["applied_link_ids"]:
                for i, l in enumerate(rr["applied_link_ids"].split(";")):
                    w.writerow([rr.get("review_id"), rr.get("trace_id"), i, l]); reviewed_links += 1

    # match_review_resolved.csv — input rows + resolution columns (input file left untouched)
    fields = list(rows[0].keys())
    for c in ("applied_link_ids", "apply_note"):
        if c not in fields:
            fields.append(c)
    with open(os.path.join(case_output_dir, "match_review_resolved.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader()
        w.writerows(resolved)

    summary = {"case_output": case_output_dir, "review_csv": review_csv,
               "network_validated": topo is not None,
               "n_rows": len(rows),
               "n_applied": sum(1 for s in summary_rows if s["status"] == "APPLIED"),
               "n_rejected": sum(1 for s in summary_rows if s["status"] == "REJECTED"),
               "n_open": sum(1 for s in summary_rows if s["status"] == "OPEN"),
               "n_reviewed_links": reviewed_links, "rows": summary_rows}
    json.dump(summary, open(os.path.join(case_output_dir, "review_applied.json"), "w"), indent=2)
    return summary


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="mapmatching4gmns apply-review")
    ap.add_argument("case_output", help="case_output/ dir containing match_review.csv")
    ap.add_argument("--review", default=None,
                    help="path to the review csv (default: <case_output>/match_review.csv)")
    ap.add_argument("--network", default=None,
                    help="GMNS network dir — enables REPLACE_PATH link validation + connectivity check")
    a = ap.parse_args(argv)
    s = apply_review(a.case_output, review_csv=a.review, network_dir=a.network)
    print(f"apply-review: {s['n_applied']} applied, {s['n_rejected']} rejected, {s['n_open']} open "
          f"-> reviewed_route.csv ({s['n_reviewed_links']} links)"
          f"{'' if s['network_validated'] else '  [no --network: REPLACE_PATH not validated]'}")
    for row in s["rows"]:
        if row["status"] != "APPLIED":
            print(f"  [{row['status']}] review {row['review_id']}: {row['note']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
