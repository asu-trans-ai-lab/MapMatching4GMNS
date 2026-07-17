"""Self-demo / self-test harness for MapMatching4GMNS.

Common pipeline for every case (spec §1):
    evidence -> standard trace -> HMM match -> geometric match -> agreement -> trusted path
    -> verification -> GUI review export.
Engine-adaptive: geometric always runs; HMM runs when the native module (or trace2route.exe) is
available, else it is skipped and noted. Second execution self-validates against the case
baseline (`expected_route.csv`). Baselines are never overwritten unless explicitly confirmed.

CLI:  python -m mapmatching4gmns.selfdemo --case synthetic [--all] [--update-baseline --confirm-baseline-update]
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = {"synthetic": "examples/self_demo/00_synthetic"}   # more cases register here (TMC, i95, ...)


def _load_yml(path):
    """Minimal YAML: 'key: value' and 'key: [a, b, c]'. No deps."""
    d = {}
    for ln in open(path, encoding="utf-8"):
        ln = ln.split("#", 1)[0].rstrip()
        if not ln or ln.lstrip() != ln or ":" not in ln:
            continue
        k, v = ln.split(":", 1); k = k.strip(); v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            d[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        elif v.lower() in ("true", "false"):
            d[k] = v.lower() == "true"
        elif v:
            try:
                d[k] = float(v) if "." in v else int(v)
            except ValueError:
                d[k] = v.strip("'\"")
    return d


def _links(mp):
    return [str(x) for x in mp.matched_link_sequence] if mp else []


def _write_links(path, links):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["seq", "link_id"])
        for i, l in enumerate(links):
            w.writerow([i, l])


def run_case(case_id, repo_root, out_dir=None, update_baseline=False):
    import pandas as pd
    from . import adapters, engine_gmns_public as eg, engine_hmm_internal as eh, verify_match, gui_export
    case_dir = os.path.join(repo_root, CASES[case_id])
    cfg = _load_yml(os.path.join(case_dir, "expected.yml"))
    out = out_dir or os.path.join(case_dir, "case_output")
    os.makedirs(out, exist_ok=True)

    # --- evidence (adapter by case_type) ---
    ctype = cfg.get("case_type", "gps")
    if ctype in ("gps", "connected_vehicle"):
        trace = pd.read_csv(os.path.join(case_dir, "trace.csv"))
        ev = adapters.trace_to_evidence(trace, direction=cfg.get("expected_direction", "AB"),
                                        corridor_id=case_id)
    else:
        raise NotImplementedError(f"case_type {ctype}: use the {ctype} adapter (stub)")
    trace.to_csv(os.path.join(out, "normalized_trace.csv"), index=False)
    json.dump({"case_id": case_id, "case_type": ctype, "network": "network",
               "n_trace_points": len(trace)}, open(os.path.join(out, "input_manifest.json"), "w"), indent=2)

    gp = set(cfg.get("gp_types", ["1", "2", "3"]))
    base = pd.read_csv(os.path.join(case_dir, "link.csv"), low_memory=False)

    # --- geometric (always) ---
    p_geo = eg.match(ev, base, gp)
    geo_links = _links(p_geo)
    _write_links(os.path.join(out, "geometric_route.csv"), geo_links)

    # --- HMM (if native engine available) ---
    p_hmm = None
    if eh.available():
        try:
            p_hmm = eh.match(ev, case_dir)
        except Exception:
            p_hmm = None
    hmm_links = _links(p_hmm) if p_hmm else None
    _write_links(os.path.join(out, "hmm_route.csv"), hmm_links or [])

    # --- trusted path: prefer a connected HMM path, else geometric ---
    topo = verify_match._link_topology(case_dir)
    if hmm_links and verify_match._is_connected(hmm_links, topo):
        trusted = hmm_links; trusted_src = "hmm"
    else:
        trusted = geo_links; trusted_src = "geometric"
    _write_links(os.path.join(out, "trusted_route.csv"), trusted)

    # --- engine comparison ---
    cross = None
    if hmm_links is not None:
        cross = verify_match._jaccard(hmm_links, geo_links)
    with open(os.path.join(out, "engine_comparison.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "value"])
        w.writerow(["hmm_links", len(hmm_links) if hmm_links is not None else "n/a (native engine not built)"])
        w.writerow(["geometric_links", len(geo_links)])
        w.writerow(["cross_engine_jaccard", round(cross, 3) if cross is not None else "n/a"])
        w.writerow(["trusted_source", trusted_src])

    # --- verification ---
    ver = verify_match.verify(hmm_links=hmm_links, geometric_links=geo_links, trusted_links=trusted,
                              expected=cfg, network_dir=case_dir, trace_coverage=None, unmatched_points=0)
    with open(os.path.join(out, "match_verification.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["check", "value"])
        for k, v in ver["checks"].items():
            w.writerow([k, v])
        w.writerow(["verdict", ver["verdict"]])

    # --- baseline self-validation (2nd run): trusted vs expected_route.csv ---
    baseline_note = None
    exp_path = os.path.join(case_dir, "expected_route.csv")
    if os.path.exists(exp_path) and not update_baseline:
        exp = [str(r["link_id"]) for r in csv.DictReader(open(exp_path, encoding="utf-8-sig"))]
        baseline_note = {"baseline_jaccard": round(verify_match._jaccard(trusted, exp), 3),
                         "matches_baseline": verify_match._jaccard(trusted, exp) >= 0.95}

    summary = {"case_id": case_id, "verdict": ver["verdict"], "trusted_source": trusted_src,
               "engines": {"geometric": True, "hmm_native": eh.available()},
               "verification": ver, "baseline": baseline_note,
               "n_trusted_links": len(trusted)}
    json.dump(summary, open(os.path.join(out, "case_summary.json"), "w"), indent=2)

    # --- GUI review export ---
    import re
    link_geom = {}
    for _, lr in base.iterrows():
        pts = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+\.\d+)\s+(-?\d+\.\d+)", str(lr.get("geometry") or ""))]
        if pts:
            link_geom[str(lr["link_id"])] = pts
    gui_export.export(out, trace, {"hmm": hmm_links, "geometric": geo_links, "trusted": trusted},
                      case_id, ver["verdict"], link_geom=link_geom)

    passed = ver["verdict"] in ("PASS", "PASS_WITH_ENGINE_DISAGREEMENT")
    passfile = os.path.join(out, "SELF_DEMO_PASS.txt")
    if os.path.exists(passfile):
        os.remove(passfile)
    if passed:
        open(passfile, "w").write(f"{case_id}: {ver['verdict']}\n")
    return summary


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="mapmatching4gmns self-demo")
    ap.add_argument("--case", default=None); ap.add_argument("--all", action="store_true")
    ap.add_argument("--repo-root", default=os.path.abspath(os.path.join(HERE, "..")))
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--confirm-baseline-update", action="store_true")
    a = ap.parse_args(argv)
    if a.update_baseline and not a.confirm_baseline_update:
        print("refusing to update baseline without --confirm-baseline-update"); return 2
    cases = list(CASES) if a.all else [a.case or "synthetic"]
    results = []
    for c in cases:
        s = run_case(c, a.repo_root, update_baseline=a.update_baseline)
        results.append(s)
        print(f"[{c}] {s['verdict']}  trusted={s['n_trusted_links']} links ({s['trusted_source']}) "
              f"| engines: geometric=Y hmm={'Y' if s['engines']['hmm_native'] else 'skip'}")
    ok = all(r["verdict"] in ("PASS", "PASS_WITH_ENGINE_DISAGREEMENT") for r in results)
    print("SELF-DEMO", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
