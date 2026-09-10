"""Self-demo / self-test harness for MapMatching4GMNS.

TMC, GTFS, and LRS exercise the native+geometric QA pipeline. The canonical I-95 case exercises
the strict mapmatcher4gmns adapter on all five GPS journeys. Engine availability is recorded
explicitly, and every case validates against a committed software regression baseline.

CLI:  python -m mapmatching4gmns.selfdemo --case tmc [--all]
"""
import csv
import json
import os
import sys

from . import verify_match

PACKAGE_DATA_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"
)
SOURCE_DATA_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "datasets"
))

# case_id -> (subdir under the packaged data, config yml name)
CASES = {"i95": ("i95", "expected.yml"),
         "tmc": ("tmc", "expected.yml"),
         "gtfs": ("gtfs", "expected.yml"),
         "lrs": ("lrs", "expected.yml")}


def _dataset_root(repo_root=None):
    """Locate the canonical fixtures in a source checkout or installed package."""
    candidates = []
    if repo_root:
        root = os.path.abspath(os.fspath(repo_root))
        candidates.extend([
            os.path.join(root, "datasets"),
            root,
        ])
    candidates.extend([PACKAGE_DATA_ROOT, SOURCE_DATA_ROOT])
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "tmc", "expected.yml")):
            return candidate
    raise FileNotFoundError(
        "validation datasets were not found; reinstall mapmatching4gmns or pass "
        "--repo-root pointing to a complete source checkout"
    )


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


def _select_trusted(hmm_links, geometric_links, expected, topology):
    """Prefer Native only when it passes topology, expected-route, and cross-engine gates."""
    if not hmm_links or not verify_match._is_connected(hmm_links, topology):
        return geometric_links, "geometric"

    expected_links = expected.get("expected_route_links", [])
    if expected_links:
        hmm_expected = verify_match._jaccard(hmm_links, expected_links)
        min_trusted = expected.get("minimum_trusted_expected_jaccard", 0.95)
        if hmm_expected < min_trusted:
            return geometric_links, "geometric"

    min_cross = expected.get("minimum_cross_engine_jaccard")
    if min_cross is not None:
        cross = verify_match._jaccard(hmm_links, geometric_links)
        if cross < min_cross:
            return geometric_links, "geometric"

    return hmm_links, "hmm"


def _apply_baseline_gate(verification, baseline):
    """A curated fixture baseline mismatch is a failed regression, not a warning."""
    if baseline is not None and not baseline.get("matches_baseline", False):
        failures = verification.setdefault("failures", [])
        if "baseline_mismatch" not in failures:
            failures.append("baseline_mismatch")
        verification["verdict"] = "FAIL"
    return verification


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


def _read_expected_routes(path):
    with open(path, encoding="utf-8-sig", newline="") as source:
        return {
            str(row["journey_id"]): [link.strip() for link in row["link_ids"].split(",")
                                     if link.strip()]
            for row in csv.DictReader(source)
        }


def _run_i95_case(case_dir, out, cfg, update_baseline=False):
    """Run the canonical five-journey I-95 GPS regression through Engine 3."""
    if update_baseline:
        raise ValueError("the I-95 route baseline must be reviewed and edited explicitly")

    import pandas as pd
    from . import api as public_api
    from . import engine_hmm_internal as native_engine
    from . import mapmatcher4gmns_adapter as third_engine
    from .adapters.gps import trace_to_evidence

    gps_path = os.path.join(case_dir, cfg.get("trace_file", "gps.csv"))
    expected_path = os.path.join(
        case_dir, cfg.get("expected_routes_file", "expected_routes.csv")
    )
    gps = pd.read_csv(gps_path, dtype={"journey_id": str})
    links = pd.read_csv(
        os.path.join(case_dir, "link.csv"), dtype=str, keep_default_na=False
    )
    expected = _read_expected_routes(expected_path)
    topology = verify_match._link_topology(case_dir)
    known_links = set(links["link_id"])
    gp_types = set(links["link_type"])

    gps.to_csv(os.path.join(out, "normalized_trace.csv"), index=False)
    with open(os.path.join(out, "input_manifest.json"), "w", encoding="utf-8") as target:
        json.dump({
            "case_id": "i95",
            "case_type": "i95_gps_batch",
            "trace_file": os.path.basename(gps_path),
            "n_evidence_points": int(len(gps)),
            "n_journeys": int(gps["journey_id"].nunique()),
        }, target, indent=2)

    failures = []
    observed_ids = set(gps["journey_id"].dropna().astype(str))
    if observed_ids != set(expected):
        failures.append("journey_set_mismatch")
    if len(gps) != int(cfg.get("expected_points", len(gps))):
        failures.append("point_count_mismatch")
    if len(observed_ids) != int(cfg.get("expected_journeys", len(observed_ids))):
        failures.append("journey_count_mismatch")

    route_rows = []
    journey_rows = []
    matched_journeys = 0
    for journey_id, group in gps.groupby("journey_id", sort=True):
        journey_id = str(journey_id)
        try:
            evidence = trace_to_evidence(group, corridor_id=journey_id)
            path = public_api.match(
                evidence,
                network_dir=case_dir,
                base_link_df=links,
                gp_types=gp_types,
                engine="mapmatcher4gmns",
            )
            route = [str(link) for link in path.matched_link_sequence]
            unknown = [link for link in route if link not in known_links]
            connected = bool(route) and verify_match._is_connected(route, topology)
            baseline_match = route == expected.get(journey_id, [])
            if unknown:
                failures.append(f"unknown_links:{journey_id}")
            if not connected:
                failures.append(f"disconnected_route:{journey_id}")
            if not baseline_match:
                failures.append(f"baseline_mismatch:{journey_id}")
            if route and not unknown and connected:
                matched_journeys += 1
            for sequence_no, link_id in enumerate(route):
                route_rows.append({
                    "journey_id": journey_id,
                    "sequence_no": sequence_no,
                    "link_id": link_id,
                })
            journey_rows.append({
                "journey_id": journey_id,
                "input_points": int(len(group)),
                "matched_links": len(route),
                "links_known": not unknown,
                "connected": connected,
                "matches_baseline": baseline_match,
                "error": "",
            })
        except Exception as exc:
            failures.append(f"engine_error:{journey_id}")
            journey_rows.append({
                "journey_id": journey_id,
                "input_points": int(len(group)),
                "matched_links": 0,
                "links_known": False,
                "connected": False,
                "matches_baseline": False,
                "error": str(exc),
            })

    route_fields = ["journey_id", "sequence_no", "link_id"]
    with open(os.path.join(out, "mapmatcher_routes.csv"), "w", newline="",
              encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=route_fields)
        writer.writeheader()
        writer.writerows(route_rows)
    journey_fields = ["journey_id", "input_points", "matched_links", "links_known",
                      "connected", "matches_baseline", "error"]
    with open(os.path.join(out, "journey_verification.csv"), "w", newline="",
              encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=journey_fields)
        writer.writeheader()
        writer.writerows(journey_rows)

    failures = sorted(set(failures))
    checks = {
        "input_points": int(len(gps)),
        "input_journeys": int(len(observed_ids)),
        "matched_journeys": int(matched_journeys),
        "all_links_known": all(row["links_known"] for row in journey_rows),
        "all_routes_connected": all(row["connected"] for row in journey_rows),
        "all_routes_match_baseline": all(row["matches_baseline"] for row in journey_rows),
    }
    verdict = "PASS" if not failures else "FAIL"
    verification = {
        "checks": checks,
        "failures": failures,
        "warnings": [],
        "verdict": verdict,
    }
    with open(os.path.join(out, "match_verification.csv"), "w", newline="",
              encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["check", "value"])
        for key, value in checks.items():
            writer.writerow([key, value])
        writer.writerow(["failures", "|".join(failures)])
        writer.writerow(["verdict", verdict])

    third_available = third_engine.available() and not third_engine.is_known_broken()[0]
    summary = {
        "case_id": "i95",
        "verdict": verdict,
        "trusted_source": "mapmatcher4gmns",
        "engines": {
            "geometric": True,
            "hmm_native": native_engine.available(),
            "mapmatcher4gmns": third_available,
        },
        "engines_run": {"mapmatcher4gmns": True},
        "verification": verification,
        "baseline": {"matches_baseline": checks["all_routes_match_baseline"]},
        "n_journeys": int(len(observed_ids)),
        "n_trusted_links": len(route_rows),
        "journeys": journey_rows,
    }
    with open(os.path.join(out, "case_summary.json"), "w", encoding="utf-8") as target:
        json.dump(summary, target, indent=2)

    passfile = os.path.join(out, "SELF_DEMO_PASS.txt")
    if os.path.exists(passfile):
        os.remove(passfile)
    if verdict == "PASS":
        with open(passfile, "w", encoding="utf-8") as target:
            target.write("i95: PASS\n")
    return summary


def run_case(case_id, repo_root=None, out_dir=None, update_baseline=False):
    import pandas as pd
    from . import adapters, engine_hmm_internal as eh, gui_export
    from .adapters import tmc as tmc_adapter, gtfs as gtfs_adapter, lrs as lrs_adapter
    from .mapmatch_corridor_to_gmns import match_corridor
    subdir, yml = CASES[case_id]
    case_dir = os.path.join(_dataset_root(repo_root), subdir)
    cfg = _load_yml(os.path.join(case_dir, yml))
    out = os.path.abspath(os.fspath(out_dir)) if out_dir else os.path.join(
        os.getcwd(), "self_demo_report", case_id
    )
    os.makedirs(out, exist_ok=True)

    # --- evidence (adapter by case_type) ---
    ctype = cfg.get("case_type", "gps")
    if ctype == "i95_gps_batch":
        return _run_i95_case(case_dir, out, cfg, update_baseline=update_baseline)
    if ctype == "gps":
        trace = pd.read_csv(os.path.join(case_dir, "trace.csv"))
        ev = adapters.trace_to_evidence(trace, direction=cfg.get("expected_direction", "AB"),
                                        corridor_id=case_id)
    elif ctype == "tmc":
        ev = tmc_adapter.to_evidence(os.path.join(case_dir, "TMC_Identification.csv"),
                                     cfg.get("road"), cfg.get("direction"))
        # a "trace" view for the dashboard: the ordered TMC endpoints
        trace = ev.reference_points.rename(columns={"longitude": "x_coord", "latitude": "y_coord"})
    elif ctype == "gtfs":
        ev = gtfs_adapter.to_evidence(os.path.join(case_dir, "gtfs"), route_id=cfg.get("route_id"),
                                      direction=cfg.get("direction", "AB"), corridor_id=case_id)
        trace = ev.reference_points.rename(columns={"longitude": "x_coord", "latitude": "y_coord"})
    elif ctype == "lrs":
        ev = lrs_adapter.to_evidence(os.path.join(case_dir, "route.csv"),
                                     direction=cfg.get("direction", "AB"), corridor_id=case_id)
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

    # --- trusted path: Native must pass topology, expected-route, and cross-engine gates ---
    topo = verify_match._link_topology(case_dir)
    trusted, trusted_src = _select_trusted(hmm_links, geo_links, cfg, topo)
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
    # --- TMC-specific outputs + verification (crosswalk, milepost, coverage, gateways) ---
    if ctype == "tmc":
        tmc_checks, tmc_fails = _tmc_outputs(out, sidecar, case_dir, cfg, topo, trusted)
        ver["checks"].update(tmc_checks)
        if tmc_fails:
            ver["failures"] = ver.get("failures", []) + tmc_fails
            ver["verdict"] = "FAIL"

    # --- LRS event projection (lrs): map event measure-ranges onto matched links ---
    if ctype == "lrs":
        events = lrs_adapter.read_events(os.path.join(case_dir, "events.csv"))
        proj = lrs_adapter.project_events(events, sidecar)
        with open(os.path.join(out, "lrs_event_crosswalk.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["event_id", "attribute", "value", "begin_measure",
                                              "end_measure", "link_ids", "n_links", "covered"])
            w.writeheader(); w.writerows(proj)
        cov = sum(1 for p in proj if p["covered"]) / len(proj) if proj else 1.0
        ver["checks"]["lrs_event_coverage"] = round(cov, 3)
        if cov < cfg.get("minimum_lrs_event_coverage", 0):
            ver["failures"] = ver.get("failures", []) + ["low_lrs_event_coverage"]; ver["verdict"] = "FAIL"

    # --- baseline self-validation (2nd run): trusted vs expected_route.csv ---
    baseline_note = None
    exp_path = os.path.join(case_dir, "expected_route.csv")
    if os.path.exists(exp_path) and not update_baseline:
        exp = [str(r["link_id"]) for r in csv.DictReader(open(exp_path, encoding="utf-8-sig"))]
        baseline_note = {"baseline_jaccard": round(verify_match._jaccard(trusted, exp), 3),
                         "matches_baseline": verify_match._jaccard(trusted, exp) >= 0.95}
    _apply_baseline_gate(ver, baseline_note)

    # Write the final verification after source-specific and baseline gates have run.
    with open(os.path.join(out, "match_verification.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["check", "value"])
        for k, v in ver["checks"].items():
            w.writerow([k, v])
        w.writerow(["failures", "|".join(ver.get("failures", []))])
        w.writerow(["warnings", "|".join(ver.get("warnings", []))])
        w.writerow(["verdict", ver["verdict"]])

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
    ap.add_argument("--repo-root", default=None,
                    help="optional source checkout; installed package data is used by default")
    ap.add_argument("--out-dir", default=os.path.abspath("self_demo_report"),
                    help="output root (one subdirectory per case)")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--confirm-baseline-update", action="store_true")
    a = ap.parse_args(argv)
    if a.update_baseline and not a.confirm_baseline_update:
        print("refusing to update baseline without --confirm-baseline-update"); return 2
    if a.update_baseline and not a.repo_root:
        print("refusing to update packaged baselines; pass --repo-root for a source checkout"); return 2
    cases = list(CASES) if a.all else [a.case or "tmc"]
    results = []
    for c in cases:
        case_out = os.path.join(os.path.abspath(a.out_dir), c)
        s = run_case(c, a.repo_root, out_dir=case_out, update_baseline=a.update_baseline)
        results.append(s)
        engines_run = s.get("engines_run") or {
            "native": s["engines"].get("hmm_native", False),
            "geometric": s["engines"].get("geometric", False),
        }
        engine_text = ",".join(name for name, ran in engines_run.items() if ran) or "none"
        print(f"[{c}] {s['verdict']}  trusted={s['n_trusted_links']} links ({s['trusted_source']}) "
              f"| engines run: {engine_text} "
              f"| output={case_out}")
    ok = all(r["verdict"] in ("PASS", "PASS_WITH_ENGINE_DISAGREEMENT") for r in results)
    print("SELF-DEMO", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
