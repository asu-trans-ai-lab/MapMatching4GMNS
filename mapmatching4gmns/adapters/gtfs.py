"""gtfs evidence adapter — a transit route's shape -> standard corridor evidence.

A GTFS *shape* (the ordered geometry a route follows) is the natural corridor: its points are the
ordered reference the matchers snap onto the road network (transit-on-roads map matching). A shape
is just a clean, ordered point sequence, so this reuses the GPS evidence builder.

Datasets: any open GTFS feed. GTFS is an open specification and agency feeds are generally openly
licensed (e.g. via the Mobility Database / transit.land), so a real feed can be used directly; the
bundled self-demo fixture in examples/self_demo/03_gtfs is synthetic and self-contained.
"""
import csv
import os
from collections import defaultdict


def _load_shapes(gtfs_dir):
    shapes = defaultdict(list)
    with open(os.path.join(gtfs_dir, "shapes.txt"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                shapes[str(r["shape_id"])].append(
                    (int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
            except (KeyError, ValueError):
                continue
    for s in shapes:
        shapes[s].sort()
    return shapes


def _route_shapes(gtfs_dir):
    route_shapes = defaultdict(set)
    with open(os.path.join(gtfs_dir, "trips.txt"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            route_shapes[str(r.get("route_id"))].add(str(r.get("shape_id", "")))
    return route_shapes


def shape_for_route(gtfs_dir, route_id=None):
    """Return (shape_id, [(seq,lon,lat), ...]) — the representative (longest) shape for a route."""
    shapes = _load_shapes(gtfs_dir)
    if route_id is not None:
        cand = [s for s in _route_shapes(gtfs_dir).get(str(route_id), set()) if s in shapes]
    else:
        cand = list(shapes)
    if not cand:
        raise ValueError(f"no GTFS shape found for route_id={route_id} in {gtfs_dir}")
    sid = max(cand, key=lambda s: len(shapes[s]))     # most detailed shape = representative
    return sid, shapes[sid]


def to_evidence(gtfs_dir, route_id=None, direction="AB", corridor_id=None, stride=1):
    """GTFS route shape -> CorridorEvidence (reference_points + segments) via the GPS builder."""
    import pandas as pd
    from .gps import trace_to_evidence
    sid, seq = shape_for_route(gtfs_dir, route_id)
    if stride > 1 and len(seq) > 2:
        seq = [seq[0]] + seq[1:-1:stride] + [seq[-1]]
    df = pd.DataFrame({"x_coord": [lon for _, lon, _ in seq],
                       "y_coord": [lat for _, _, lat in seq]})
    return trace_to_evidence(df, direction=direction, corridor_id=corridor_id or f"gtfs_{route_id or sid}")
