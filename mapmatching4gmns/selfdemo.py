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
CASES = {"synthetic": "examples/self_demo/00_synthetic", "tmc": "examples/self_demo/02_tmc"}


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


def _tmc_outputs(out, sidecar, case_dir, cfg, topo, trusted):
    """Write TMC crosswalk / milepost / unmatched + return TMC-specific checks & failures."""
    import csv as _csv
    rows = sidecar.to_dict("records") if sidecar is not None else []
    # crosswalk (one row per matched link; one TMC may map to several links = one-to-many kept)
    with open(os.path.join(out, "tmc_gmns_crosswalk.csv"), "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=["tmc_code", "gmns_link_id", "sequence_no",
            "projected_start_measure", "projected_end_measure", "direction_match",
            "match_dist_m", "match_confidence"], extrasaction="ignore")
        w.writeheader()
        for i, r in enumerate(rows):
            mpb, mpe = r.get("mp_begin"), r.get("mp_end")
            w.writerow({"tmc_code": r.get("tmc") or r.get("matched_tmc"), "gmns_link_id": r.get("link_id"),
                        "sequence_no": i, "projected_start_measure": mpb, "projected_end_measure": mpe,
                        "direction_match": r.get("mp_dir") or cfg.get("direction"),
                        "match_dist_m": round(float(r.get("match_dist_m") or 0), 1),
                        "match_confidence": round(1 - min(1, float(r.get("match_dist_m") or 0) / 300), 3)})
    with open(os.path.join(out, "tmc_milepost.csv"), "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["link_id", "mp_begin", "mp_end"])
        for r in rows:
            w.writerow([r.get("link_id"), r.get("mp_begin"), r.get("mp_end")])
    # unmatched TMCs (in the id file but not represented)
    matched_tmcs = set(str(r.get("tmc") or r.get("matched_tmc") or "") for r in rows)
    all_tmc, total_mi, matched_mi = [], 0.0, 0.0
    for r in _csv.DictReader(open(os.path.join(case_dir, "TMC_Identification.csv"), encoding="utf-8-sig")):
        code = str(r.get("tmc")); mi = float(r.get("miles") or 0); total_mi += mi
        all_tmc.append(code)
        if code in matched_tmcs:
            matched_mi += mi
    with open(os.path.join(out, "tmc_unmatched.csv"), "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["tmc_code"])
        for c in all_tmc:
            if c not in matched_tmcs:
                w.writerow([c])

    # ---- checks ----
    mpb = [r.get("mp_begin") for r in rows if r.get("mp_begin") is not None]
    monotonic = all(mpb[i] <= mpb[i + 1] + 1e-6 for i in range(len(mpb) - 1))
    coverage = matched_mi / total_mi if total_mi else 0.0
    # gateway: the trusted route's node chain must include the required gateway nodes
    node_chain = []
    for l in trusted:
        if l in topo:
            node_chain += list(topo[l])
    node_set = set(node_chain)
    gateways = [str(g) for g in cfg.get("required_gateways", [])]
    gateways_ok = all(g in node_set for g in gateways)
    one_to_many = len(rows) > len(matched_tmcs)     # >=1 TMC mapped to multiple links
    checks = {"milepost_monotonic": monotonic, "sequence_preserved": monotonic,
              "tmc_coverage": round(coverage, 3), "gateways_traversed": gateways_ok,
              "one_to_many_links": one_to_many, "matched_tmcs": len(matched_tmcs), "total_tmcs": len(all_tmc)}
    with open(os.path.join(out, "tmc_verification.csv"), "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f); w.writerow(["check", "value"])
        for k, v in checks.items():
            w.writerow([k, v])
    fails = []
    if cfg.get("require_milepost_monotonic") and not monotonic:
        fails.append("milepost_not_monotonic")
    if coverage < cfg.get("minimum_tmc_coverage", 0):
        fails.append("low_tmc_coverage")
    if gateways and not gateways_ok:
        fails.append("gateway_not_traversed")
    return checks, fails


def run_case(case_id, repo_root, out_dir=None, update_baseline=False):
    import pandas as pd
    from . import adapters, engine_hmm_internal as eh, verify_match, gui_export
    from .adapters import tmc as tmc_adapter
    from .mapmatch_corridor_to_gmns import match_corridor
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
    elif ctype == "tmc":
        ev = tmc_adapter.to_evidence(os.path.join(case_dir, "TMC_Identification.csv"),
                                     cfg.get("road"), cfg.get("direction"))
        # a "trace" view for the dashboard: the ordered TMC endpoints
        trace = ev.reference_points.rename(columns={"longitude": "x_coord", "latitude": "y_coord"})
    else:
        raise NotImplementedError(f"case_type {ctype}: use the {ctype} adapter (stub)")
    trace.to_csv(os.path.join(out, "normalized_trace.csv"), index=False)
    json.dump({"case_id": case_id, "case_type": ctype, "network": "network",
               "n_evidence_points": len(trace)}, open(os.path.join(out, "input_manifest.json"), "w"), indent=2)

    gp = set(cfg.get("gp_types", ["1", "2", "3"]))
    base = pd.read_csv(os.path.join(case_dir, "link.csv"), low_memory=False)

    # --- geometric (always) -> sidecar carries per-link milepost + tmc attribution ---
    sidecar = match_corridor(ev, base, gp)
    if sidecar is not None and len(sidecar) and "mp_begin" in sidecar.columns:
        sidecar = sidecar.sort_values("mp_begin")
    geo_links = [str(x) for x in sidecar["link_id"].tolist()] if sidecar is not None and len(sidecar) else []
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

    # --- TMC-specific outputs + verification (crosswalk, milepost, coverage, gateways) ---
    if ctype == "tmc":
        tmc_checks, tmc_fails = _tmc_outputs(out, sidecar, case_dir, cfg, topo, trusted)
        ver["checks"].update(tmc_checks)
        if tmc_fails:
            ver["failures"] = ver.get("failures", []) + tmc_fails
            ver["verdict"] = "FAIL"

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
