"""I-95 evidence adapter — trip-path and connected-vehicle streams.

Two evidence streams (spec §3):
  A. trip-path — lower-frequency, longer trajectories.
  B. connected-vehicle (CV) — denser but noisier: duplicates, stationary points, lane-level
     lateral variation, time gaps, partial coverage. Cleaned before matching.

Restricted-data boundary: the real I-95 records (INRIX/RITIS/VDOT) are LOCAL-ONLY and never
committed. `portal_to_network` reads a local GUI4GMNS I-95 portal (network.geojson) into GMNS for
the local research version; the public CI fixture in examples/self_demo/01_i95 is sanitized.
"""
from .gps import trace_to_evidence, _hav_mi


def trip_to_evidence(trip_df, direction="AB", corridor_id="i95_trip"):
    """Trip-path points -> standard evidence (points are already sparse & clean)."""
    return trace_to_evidence(trip_df, direction=direction, corridor_id=corridor_id)


def clean_cv(cv_df, min_step_m=5.0):
    """Drop stationary / duplicate CV points (consecutive points closer than min_step_m, or
    speed ~0), keeping temporal order. Returns a cleaned copy."""
    import pandas as pd
    rows = cv_df.to_dict("records")
    out = []
    last = None
    for r in rows:
        try:
            p = (float(r["x_coord"]), float(r["y_coord"]))
        except (KeyError, ValueError):
            continue
        spd = float(r.get("speed_mph", 1) or 0)
        if last is not None and (_hav_mi(last, p) * 1609.34 < min_step_m or spd <= 0.1):
            continue          # stationary / duplicate -> drop
        out.append(r); last = p
    return pd.DataFrame(out) if out else cv_df.iloc[0:0]


def cv_to_evidence(cv_df, direction="AB", corridor_id="i95_cv", min_step_m=5.0):
    """Connected-vehicle points -> cleaned -> standard evidence."""
    return trace_to_evidence(clean_cv(cv_df, min_step_m), direction=direction, corridor_id=corridor_id)


def thin(df, keep_every=2):
    """Trajectory thinning: keep every k-th point (+ endpoints) — for stability testing."""
    n = len(df)
    idx = sorted(set(list(range(0, n, keep_every)) + [n - 1]))
    return df.iloc[idx].reset_index(drop=True)


def portal_to_network(portal_dir, out_dir):
    """LOCAL research version only: read a GUI4GMNS I-95 portal network.geojson -> GMNS
    node.csv/link.csv. Not used by the public fixture; keeps restricted data local."""
    import json
    import os
    import csv as _csv
    gj = json.load(open(os.path.join(portal_dir, "network.geojson"), encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    nodes = {}; links = []; nid = [0]

    def node(x, y):
        key = (round(x, 6), round(y, 6))
        if key not in nodes:
            nid[0] += 1; nodes[key] = nid[0]
        return nodes[key]

    for i, ft in enumerate(gj.get("features", [])):
        g = ft.get("geometry") or {}
        if g.get("type") != "LineString":
            continue
        cs = g["coordinates"]
        a = node(cs[0][0], cs[0][1]); b = node(cs[-1][0], cs[-1][1])
        pr = ft.get("properties", {})
        wkt = "LINESTRING (" + ", ".join(f"{c[0]} {c[1]}" for c in cs) + ")"
        links.append([pr.get("link_id", i + 1), a, b, pr.get("link_type", 1),
                      pr.get("lanes", 2), pr.get("free_speed", 60), wkt])
    with open(os.path.join(out_dir, "node.csv"), "w", newline="") as f:
        w = _csv.writer(f); w.writerow(["node_id", "zone_id", "x_coord", "y_coord"])
        for (x, y), n in nodes.items():
            w.writerow([n, 0, x, y])
    with open(os.path.join(out_dir, "link.csv"), "w", newline="") as f:
        w = _csv.writer(f); w.writerow(["link_id", "from_node_id", "to_node_id", "link_type",
                                        "lanes", "free_speed", "geometry"]); w.writerows(links)
    return len(nodes), len(links)


def to_evidence(*args, **kwargs):
    """Default = trip-path stream."""
    return trip_to_evidence(*args, **kwargs)
