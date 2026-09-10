"""Engine 1 -- internal native map matcher (MapMatching4GMNS, C++ trace2route).

Algorithm: a most-likely **connected-path** search (time-geographic least-generalized-cost path;
Tang et al. 2015) -- NOT a Hidden Markov Model. The module name and the `hmm` engine keyword are
legacy labels kept for back-compat; prefer "native".

Wraps Zhou's MapMatching4GMNS engine: the packaged C++ extension finds the most-likely path
(node sequence) through a GMNS network given a GPS/point trace. (Distinct
from Yajun Liu's `mapmatcher4gmns` PyPI package -- a *separate* HMM matcher, TrackIt/GoTrackIt
lineage, wrapped separately in mapmatcher4gmns_adapter.)
It is the stronger engine and is INTERNAL. Supported platform wheels install it as
`mapmatching4gmns._native`; the geometric engine remains available for diagnostic fallback.

Data flow (the packaged extension reads/writes from a temporary working directory):
    node.csv, link.csv, trace.csv  ->  _native  ->  route.csv (matched links), agent.csv

For corridor/TMC evidence the "trace" is the ordered reference points; the origin/destination
nodes are the network nodes nearest the first/last point (trace2route needs o_node_id/d_node_id).
"""
import csv
import math
import os
import tempfile

from .match_schema import MatchedPath

NAME = "engine_hmm"


def native_module():
    """Return the in-package, cross-platform pybind module, or None."""
    try:
        from . import _native as _m
        return _m
    except ImportError:
        return None


def available():
    """Return whether the in-package native engine is importable."""
    return native_module() is not None


def match_batch(evidences, network_dir, *, agent_ids=None, buffer_deg=0.05, n_threads=1):
    """BATCH match: clip the network ONCE to the union bbox of all corridors, write every
    corridor as one agent in a single trace.csv, run the engine ONCE (one network load),
    and split the result by agent. This is the mapmatcher4gmns "load once, match many"
    pattern -- it avoids re-reading the network per corridor (the T1 batch overhead).

    n_threads: agents-across-threads parallelism for the native module (T4). Only takes effect
    when the module was built with OpenMP; otherwise the batch still runs, just
    single-threaded. Set explicitly via the CORRIDOR2GMNS_MM_THREADS env for the native call.

    evidences: list of CorridorEvidence (best grouped by locale so the union bbox stays a
    subarea; a statewide union will be huge/slow). Returns {agent_id: MatchedPath}."""
    native = native_module()
    if native is None:
        return {}
    node_csv = os.path.join(network_dir, "node.csv")
    link_csv = os.path.join(network_dir, "link.csv")
    if not (os.path.exists(node_csv) and os.path.exists(link_csv)):
        return {}
    evs = [ev for ev in evidences if ev.reference_points is not None and len(ev.reference_points) >= 2]
    if not evs:
        return {}
    ids = agent_ids or [ev.corridor_id for ev in evs]

    lons, lats = [], []
    for ev in evs:
        lons += list(ev.reference_points.longitude.astype(float))
        lats += list(ev.reference_points.latitude.astype(float))
    bbox = (min(lons) - buffer_deg, min(lats) - buffer_deg,
            max(lons) + buffer_deg, max(lats) + buffer_deg)

    with tempfile.TemporaryDirectory() as run:
        kept = _clip_network(node_csv, link_csv, bbox, run)      # ONE clip for all corridors
        if len(kept) < 2:
            return {}
        nodes = _read_nodes(os.path.join(run, "node.csv"))
        od = {}
        with open(os.path.join(run, "trace.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["agent_id", "x_coord", "y_coord", "trace_no", "trace_id",
                        "o_node_id", "d_node_id"])
            for ev, aid in zip(evs, ids):
                pts = ev.reference_points
                o = _nearest_node(nodes, float(pts.iloc[0].longitude), float(pts.iloc[0].latitude))
                d = _nearest_node(nodes, float(pts.iloc[-1].longitude), float(pts.iloc[-1].latitude))
                od[str(aid)] = (o, d)
                for i, p in enumerate(pts.itertuples()):
                    w.writerow([aid, p.longitude, p.latitude, i, i,
                                o if i == 0 else "", d if i == 0 else ""])

        rows = None
        if native is not None:
            prev = os.environ.get("CORRIDOR2GMNS_MM_THREADS")
            if n_threads and n_threads > 1:
                os.environ["CORRIDOR2GMNS_MM_THREADS"] = str(int(n_threads))
            try:
                rows = native.run_in_dir(run)
            except Exception:
                rows = None
            finally:
                if prev is None:
                    os.environ.pop("CORRIDOR2GMNS_MM_THREADS", None)
                else:
                    os.environ["CORRIDOR2GMNS_MM_THREADS"] = prev
        if rows is None:
            return {}

    by_agent = {}
    for r in rows:
        a = str(r.get("agent_id", ""))
        lid = r.get("link_id")
        if not a or lid in (None, ""):
            continue
        by_agent.setdefault(a, []).append(str(lid))
    out = {}
    for aid in [str(x) for x in ids]:
        links = by_agent.get(aid, [])
        o, d = od.get(aid, (None, None))
        out[aid] = MatchedPath(trajectory_id=aid, source_engine=NAME,
                               matched_link_sequence=links, start_node_id=o, end_node_id=d,
                               meta={"backend": "batch", "n_corridors": len(evs)})
    return out


def _read_nodes(node_csv):
    nodes = {}
    with open(node_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                nodes[int(r["node_id"])] = (float(r["x_coord"]), float(r["y_coord"]))
            except (KeyError, ValueError):
                continue
    return nodes


def _clip_network(node_csv, link_csv, bbox, run_dir):
    """Write node.csv/link.csv clipped to `bbox` (minlon,minlat,maxlon,maxlat) into run_dir.
    trace2route (the HMM engine) is a SUBAREA matcher -- it segfaults on a statewide network
    and on out-of-area garbage coords, so we clip first (subarea-first, same principle as the
    geometric engine). Returns the set of kept node_ids."""
    minlon, minlat, maxlon, maxlat = bbox
    kept = set()
    with open(node_csv, encoding="utf-8-sig", newline="") as f, \
         open(os.path.join(run_dir, "node.csv"), "w", newline="", encoding="utf-8") as g:
        rdr = csv.DictReader(f); w = csv.DictWriter(g, fieldnames=rdr.fieldnames); w.writeheader()
        for r in rdr:
            try:
                x, y = float(r["x_coord"]), float(r["y_coord"])
            except (KeyError, ValueError):
                continue
            if minlon <= x <= maxlon and minlat <= y <= maxlat:
                w.writerow(r); kept.add(r["node_id"])
    with open(link_csv, encoding="utf-8-sig", newline="") as f, \
         open(os.path.join(run_dir, "link.csv"), "w", newline="", encoding="utf-8") as g:
        rdr = csv.DictReader(f); w = csv.DictWriter(g, fieldnames=rdr.fieldnames); w.writeheader()
        for r in rdr:
            if r.get("from_node_id") in kept and r.get("to_node_id") in kept:
                w.writerow(r)
    return kept


def _nearest_node(nodes, lon, lat):
    best, bd = None, 1e30
    for nid, (x, y) in nodes.items():
        d = (x - lon) ** 2 + (y - lat) ** 2
        if d < bd:
            bd, best = d, nid
    return best


def match(evidence, network_dir, *, agent_id=None, buffer_deg=0.05):
    """Run trace2route on the corridor evidence trace against the GMNS network in
    network_dir (must contain node.csv + link.csv with trace2route's expected columns:
    node_id/x_coord/y_coord; link_id/from_node_id/to_node_id/length/geometry). The network
    is CLIPPED to the evidence bbox first (the HMM engine is a subarea matcher).
    Returns a MatchedPath, or None if the engine is unavailable or produced no route."""
    native = native_module()
    if native is None:
        return None
    node_csv = os.path.join(network_dir, "node.csv")
    link_csv = os.path.join(network_dir, "link.csv")
    if not (os.path.exists(node_csv) and os.path.exists(link_csv)):
        return None
    pts = evidence.reference_points
    if pts is None or len(pts) < 2:
        return None
    lons = pts.longitude.astype(float); lats = pts.latitude.astype(float)
    bbox = (lons.min() - buffer_deg, lats.min() - buffer_deg,
            lons.max() + buffer_deg, lats.max() + buffer_deg)
    tid = str(agent_id or evidence.corridor_id)

    with tempfile.TemporaryDirectory() as run:
        kept = _clip_network(node_csv, link_csv, bbox, run)
        if len(kept) < 2:
            return None
        nodes = _read_nodes(os.path.join(run, "node.csv"))    # clipped node set
        o_node = _nearest_node(nodes, float(pts.iloc[0].longitude), float(pts.iloc[0].latitude))
        d_node = _nearest_node(nodes, float(pts.iloc[-1].longitude), float(pts.iloc[-1].latitude))
        with open(os.path.join(run, "trace.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["agent_id", "x_coord", "y_coord", "trace_no", "trace_id",
                        "o_node_id", "d_node_id"])
            for i, p in enumerate(pts.itertuples()):
                # trace2route reads BOTH o_node_id and d_node_id from the FIRST row
                o = o_node if i == 0 else ""
                d = d_node if i == 0 else ""
                w.writerow([tid, p.longitude, p.latitude, i, i, o, d])

        try:
            rows = native.run_in_dir(run)
        except Exception:
            return None
        backend = "native:mapmatching4gmns._native"

        links, total = [], 0.0
        for r in rows:
            lid = r.get("link_id")
            if lid in (None, ""):
                continue
            links.append(str(lid))
            try:
                total = float(r.get("distance", total) or total)
            except (ValueError, TypeError):
                pass
    if not links:
        return None
    return MatchedPath(
        trajectory_id=tid, source_engine=NAME, matched_link_sequence=links,
        start_node_id=o_node, end_node_id=d_node,
        confidence_score=None, transition_error=None,
        meta={"path_distance_m": round(total, 1), "backend": backend})
