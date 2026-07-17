"""GTFS transit routes -> trace.csv for trace2route (transit-on-arterials map matching).

The GTFS analog of tmc2trace.py. Each GTFS *shape* (a route's ordered geometry) becomes one
matching agent: its shape points become trace points, and o_node/d_node are snapped to the
nearest network node (first row only) -- exactly trace2route's expected trace contract.

Shapes are optionally clipped to a subarea bbox and thinned (GTFS shapes are dense: ~300 pts;
we keep every STRIDE-th point + endpoints, which is enough for most-likely-path matching and
keeps the trace small).

Inputs : GTFS shapes.txt/trips.txt/routes.txt, and a GMNS node.csv (lat/lon EPSG:4326).
Output : trace.csv (trace2route schema) + a shape->route lookup.
"""
import argparse
import csv
import os
from collections import defaultdict


def _nearest_node_fn(node_csv):
    xs, ys, ids = [], [], []
    with open(node_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                xs.append(float(r["x_coord"])); ys.append(float(r["y_coord"]))
                ids.append(int(r["node_id"]))
            except (KeyError, ValueError):
                continue
    try:
        import numpy as np
        from scipy.spatial import cKDTree
        tree = cKDTree(np.column_stack([xs, ys]))
        arr = np.array(ids)
        return lambda lon, lat: int(arr[tree.query([lon, lat])[1]])
    except Exception:
        def nearest(lon, lat):
            best, bd = None, 1e30
            for x, y, i in zip(xs, ys, ids):
                d = (x - lon) ** 2 + (y - lat) ** 2
                if d < bd:
                    bd, best = d, i
            return best
        return nearest


def build(gtfs_dir, node_csv, out_trace, *, bbox=None, stride=6, min_frac_in=0.5,
          route_types=None):
    """bbox=(xmin,xmax,ymin,ymax) or None; route_types=set of GTFS route_type ints or None."""
    # shape points
    shapes = defaultdict(list)
    with open(os.path.join(gtfs_dir, "shapes.txt"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                shapes[r["shape_id"]].append(
                    (int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
            except (KeyError, ValueError):
                continue
    for s in shapes:
        shapes[s].sort()

    # shape -> route metadata (route_type filter)
    shape_route = {}
    routes = {}
    with open(os.path.join(gtfs_dir, "routes.txt"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            routes[str(r["route_id"])] = (r.get("route_short_name", ""),
                                          r.get("route_long_name", ""),
                                          r.get("route_type", ""))
    with open(os.path.join(gtfs_dir, "trips.txt"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            sid = str(r.get("shape_id", ""))
            rid = str(r.get("route_id", ""))
            if sid and sid not in shape_route:
                shape_route[sid] = rid

    def in_bbox(lon, lat):
        return bbox is None or (bbox[0] <= lon <= bbox[1] and bbox[2] <= lat <= bbox[3])

    nearest = _nearest_node_fn(node_csv)
    rows = []
    lookup = []
    kept_shapes = 0
    for sid, seq in shapes.items():
        rid = shape_route.get(sid)
        rmeta = routes.get(rid, ("", "", ""))
        if route_types is not None:
            try:
                if int(rmeta[2]) not in route_types:
                    continue
            except (ValueError, TypeError):
                continue
        # bbox filter: keep shape only if enough points fall inside
        if bbox is not None:
            n_in = sum(1 for _, lon, lat in seq if in_bbox(lon, lat))
            if not seq or n_in / len(seq) < min_frac_in:
                continue
            seq = [(sq, lon, lat) for (sq, lon, lat) in seq if in_bbox(lon, lat)]
        if len(seq) < 2:
            continue
        # thin: keep endpoints + every STRIDE-th
        thin = [seq[0]] + seq[1:-1:max(1, stride)] + [seq[-1]]
        agent = f"{rmeta[0] or rid}__{sid}"
        corridor = (rmeta[1] or rmeta[0] or rid)
        geom = "LINESTRING (" + ", ".join(f"{lon} {lat}" for _, lon, lat in thin) + ")"
        for _, lon, lat in thin:
            rows.append([sid, corridor, rmeta[2], lat, lon, "connector", agent])
        kept_shapes += 1
        lookup.append({"agent_id": agent, "shape_id": sid, "route_id": rid,
                       "route_short_name": rmeta[0], "route_long_name": rmeta[1],
                       "route_type": rmeta[2], "n_trace_pts": len(thin)})

    # assign trace_no, road_sequence, o/d nodes (first row of each agent only)
    by_agent = defaultdict(list)
    for i, row in enumerate(rows):
        by_agent[row[6]].append(i)
    o_node = {a: "" for a in by_agent}
    d_node = {a: "" for a in by_agent}
    for a, idxs in by_agent.items():
        first, last = rows[idxs[0]], rows[idxs[-1]]
        o_node[a] = nearest(float(first[4]), float(first[3]))   # x=col4, y=col3
        d_node[a] = nearest(float(last[4]), float(last[3]))

    with open(out_trace, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["trace_id", "corridor_name", "road_order", "y_coord", "x_coord",
                    "blocked_link_type_code", "agent_id", "trace_no", "road_sequence",
                    "o_node_id", "d_node_id"])
        seq_ctr = defaultdict(int)
        for i, row in enumerate(rows):
            a = row[6]
            is_first = (i == by_agent[a][0])
            w.writerow(row + [i, seq_ctr[a],
                              o_node[a] if is_first else "",
                              d_node[a] if is_first else ""])
            seq_ctr[a] += 1

    lookup_csv = os.path.splitext(out_trace)[0] + "_lookup.csv"
    with open(lookup_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["agent_id", "shape_id", "route_id",
                                          "route_short_name", "route_long_name",
                                          "route_type", "n_trace_pts"])
        w.writeheader(); w.writerows(lookup)
    return {"shapes_kept": kept_shapes, "trace_points": len(rows),
            "trace_csv": out_trace, "lookup_csv": lookup_csv,
            "agents": list(by_agent.keys())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtfs", required=True)
    ap.add_argument("--node", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bbox", nargs=4, type=float, default=None,
                    help="xmin xmax ymin ymax")
    ap.add_argument("--stride", type=int, default=6)
    ap.add_argument("--route-types", nargs="*", type=int, default=None)
    a = ap.parse_args()
    bbox = tuple(a.bbox) if a.bbox else None
    rtypes = set(a.route_types) if a.route_types else None
    info = build(a.gtfs, a.node, a.out, bbox=bbox, stride=a.stride, route_types=rtypes)
    print(f"gtfs2trace: {info['shapes_kept']} shapes, {info['trace_points']} trace points -> {info['trace_csv']}")
