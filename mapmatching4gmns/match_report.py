"""Dual-engine orchestrator + QA report.

dual_match runs both engines on the same corridor evidence, compares them, resolves a
trusted result, and returns a QA record. Engine 1 (internal HMM) is used when available;
otherwise the run degrades gracefully to Engine 2 alone (flagged single-engine).
"""
import csv
import json
import os

from . import engine_gmns_public as eg
from . import engine_hmm_internal as eh
from .compare_match_results import compare
from .resolve_conflicts import resolve


def dual_match(evidence, base_link_df, gp_types, *, network_dir=None, exe_path=None,
               chain=None, prefer="engine_hmm"):
    """Run both engines on `evidence`, compare, resolve. `network_dir` (node.csv+link.csv)
    is required for Engine 1 (HMM). Returns a QA record dict."""
    p_gmns = eg.match(evidence, base_link_df, gp_types, chain=chain)
    p_hmm = None
    if network_dir and eh.available(exe_path):
        p_hmm = eh.match(evidence, network_dir, exe_path=exe_path)
    cmp = compare(p_hmm, p_gmns)
    res = resolve(p_hmm, p_gmns, cmp, prefer=prefer)
    return {"trajectory_id": evidence.corridor_id,
            "engine_hmm_available": p_hmm is not None,
            "comparison": cmp, "resolution": {k: (v.matched_path_id if hasattr(v, "matched_path_id") else v)
                                              for k, v in res.items()},
            "paths": {"engine_gmns": p_gmns.as_row() if p_gmns else None,
                      "engine_hmm": p_hmm.as_row() if p_hmm else None},
            "trusted": res["trusted_path"].as_row() if res["trusted_path"] else None}


def format_report(rec):
    c = rec["comparison"]
    lines = [f"dual-engine match: {rec['trajectory_id']}"]
    lines.append(f"  Engine 1 (HMM): {'ran' if rec['engine_hmm_available'] else 'unavailable -> single-engine'}")
    lines.append(f"  verdict: {c['verdict'].upper()}"
                 + (f"  flags: {', '.join(c.get('flags', []))}" if c.get("flags") else ""))
    if "link_jaccard" in c:
        lines.append(f"  link agreement: jaccard {c['link_jaccard']} / common-run {c['link_common_run']}"
                     f" | direction {c['direction_agree']} | milepost {c['milepost_agree']}")
    lines.append(f"  -> {rec['resolution'].get('trust')}: {rec['resolution'].get('note', '')}")
    return "\n".join(lines)


def write_records(records, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "dual_match_qa.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    # flat verdict table
    with open(os.path.join(out_dir, "dual_match_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trajectory_id", "engine_hmm_ran", "verdict", "flags",
                    "link_jaccard", "trust"])
        for r in records:
            c = r["comparison"]
            w.writerow([r["trajectory_id"], r["engine_hmm_available"], c.get("verdict"),
                        "|".join(c.get("flags", [])), c.get("link_jaccard"),
                        r["resolution"].get("trust")])
    return out_dir
