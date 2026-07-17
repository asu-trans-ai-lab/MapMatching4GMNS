"""Conflate CorridorEvidence onto a GMNS base network (SPEC Layer A->B).

Geometric, dependency-light matcher (does NOT require mapmatcher4gmns): for each GMNS
mainline link inside the corridor's bounding box, find the nearest TMC reference segment
with an agreeing heading, and attribute the TMC's route + interpolated milepost + direction
to that link. The result is an LRS-style sidecar (never modifies the GMNS network) that
`construction.corridor_chain` orders topologically and `analytics.gateway_od` consumes.

Subarea-first by construction: links are clipped to the evidence bbox + buffer before any
distance work, so this never scans the statewide network. Heading agreement separates the
two directions automatically (EB links match EB TMCs).
"""
import math

import pandas as pd

_DIR_CODE = {"EASTBOUND": 1, "NORTHBOUND": 1, "WESTBOUND": -1, "SOUTHBOUND": -1}
_M_PER_DEG_LAT = 111_320.0


def _parse_linestring(wkt):
    """WKT 'LINESTRING (lon lat, lon lat, ...)' -> [(lon,lat),...]; None if unparseable."""
    if not isinstance(wkt, str) or "(" not in wkt:
        return None
    inside = wkt[wkt.find("(") + 1: wkt.rfind(")")]
    pts = []
    for pair in inside.split(","):
        xy = pair.strip().split()
        if len(xy) >= 2:
            try:
                pts.append((float(xy[0]), float(xy[1])))
            except ValueError:
                return None
    return pts if len(pts) >= 2 else None


def _mperdeg_lon(lat):
    return _M_PER_DEG_LAT * math.cos(math.radians(lat))


def _heading(a, b, mlon):
    """Bearing degrees [0,360) from a to b, using local metric scaling."""
    dx = (b[0] - a[0]) * mlon
    dy = (b[1] - a[1]) * _M_PER_DEG_LAT
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _head_diff(h1, h2):
    d = abs(h1 - h2) % 360.0
    return min(d, 360.0 - d)


def _point_seg(p, a, b, mlon):
    """Perpendicular distance (m) from p to segment a-b, and projection fraction [0,1]."""
    ax, ay = a[0] * mlon, a[1] * _M_PER_DEG_LAT
    bx, by = b[0] * mlon, b[1] * _M_PER_DEG_LAT
    px, py = p[0] * mlon, p[1] * _M_PER_DEG_LAT
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    projx, projy = ax + t * dx, ay + t * dy
    return math.hypot(px - projx, py - projy), t


def _local_heading(coords, mlon):
    """Heading of the polyline AT ITS MIDPOINT (small window around the middle vertex),
    not the endpoint chord. On a curved link the chord can agree with a reference segment
    the link doesn't actually follow (or disagree with one it does) -- the local tangent
    at the point we measure distance from (the midpoint) is the honest direction."""
    n = len(coords)
    if n == 2:
        return _heading(coords[0], coords[1], mlon)
    im = n // 2
    a = coords[max(0, im - 1)]
    b = coords[min(n - 1, im + 1)]
    if a == b:                               # degenerate window -> fall back to chord
        return _heading(coords[0], coords[-1], mlon)
    return _heading(a, b, mlon)


def _project_endpoint(p, tmcs, fallback_tm, mlon, max_dist_m):
    """Milepost for a link ENDPOINT: project onto the nearest reference segment to that
    endpoint (not necessarily the one the midpoint matched), so a link spanning two TMCs
    interpolates its milepost ACROSS the boundary instead of clamping at it. Falls back to
    the midpoint's TMC when no segment is within max_dist_m."""
    best = None
    for tm in tmcs:
        d, t = _point_seg(p, tm["a"], tm["b"], mlon)
        if d <= max_dist_m and (best is None or d < best[0]):
            best = (d, tm["mpb"] + t * (tm["mpe"] - tm["mpb"]))
    if best is not None:
        return best[1]
    _, t = _point_seg(p, fallback_tm["a"], fallback_tm["b"], mlon)
    return fallback_tm["mpb"] + t * (fallback_tm["mpe"] - fallback_tm["mpb"])


def match_corridor(evidence, base_link_df, gp_types, *, buffer_m=800.0,
                   max_dist_m=250.0, max_head_deg=35.0):
    """Attribute TMC route + milepost to GMNS mainline links.

    evidence: CorridorEvidence (needs reference_segments with start/end lon/lat, mp_begin,
              mp_end, direction).
    base_link_df: GMNS link.csv as DataFrame with link_id, from_node_id, to_node_id,
              link_type (str), geometry (WKT).
    gp_types: set of link_type strings that are mainline (from the network profile).

    Returns a sidecar DataFrame: link_id, from_node_id, to_node_id, route_id,
    corridor_name, mp_begin, mp_end, mp_dir, match_dist_m, match_head_deg.
    """
    seg = evidence.reference_segments
    lat0 = float(seg[["start_latitude", "end_latitude"]].stack().mean())
    mlon = _mperdeg_lon(lat0)
    bufdeg_lat = buffer_m / _M_PER_DEG_LAT
    bufdeg_lon = buffer_m / mlon
    minlon = seg[["start_longitude", "end_longitude"]].min().min() - bufdeg_lon
    maxlon = seg[["start_longitude", "end_longitude"]].max().max() + bufdeg_lon
    minlat = seg[["start_latitude", "end_latitude"]].min().min() - bufdeg_lat
    maxlat = seg[["start_latitude", "end_latitude"]].max().max() + bufdeg_lat

    # pre-parse TMC segments (endpoints + heading + mp)
    tmcs = []
    for _, r in seg.iterrows():
        a = (r.start_longitude, r.start_latitude); b = (r.end_longitude, r.end_latitude)
        tmcs.append({"a": a, "b": b, "head": _heading(a, b, mlon),
                     "mpb": r.mp_begin, "mpe": r.mp_end, "dir": r.direction, "tmc": r.tmc})

    rows = []
    lk = base_link_df
    for lid, fn, tn, lt, geo in zip(lk["link_id"], lk["from_node_id"], lk["to_node_id"],
                                    lk["link_type"].astype(str), lk["geometry"]):
        if lt not in gp_types:
            continue
        coords = _parse_linestring(geo)
        if not coords:
            continue
        # quick bbox reject on the link midpoint
        mid = coords[len(coords) // 2]
        if not (minlon <= mid[0] <= maxlon and minlat <= mid[1] <= maxlat):
            continue
        lhead = _local_heading(coords, mlon)     # local tangent at the midpoint, not chord
        best = None
        for tm in tmcs:
            hd = _head_diff(lhead, tm["head"])
            if hd > max_head_deg:
                continue
            d, _ = _point_seg(mid, tm["a"], tm["b"], mlon)
            if d <= max_dist_m and (best is None or d < best[0]):
                best = (d, hd, tm)
        if best is None:
            continue
        d, hd, tm = best
        # per-endpoint projection: each endpoint finds its own nearest reference segment,
        # so a link spanning two TMCs interpolates mp across the boundary
        mp0 = _project_endpoint(coords[0], tmcs, tm, mlon, max_dist_m)
        mp1 = _project_endpoint(coords[-1], tmcs, tm, mlon, max_dist_m)
        rows.append({"link_id": lid, "from_node_id": fn, "to_node_id": tn,
                     "route_id": evidence.route_label, "corridor_name": evidence.corridor_name,
                     "mp_begin": round(min(mp0, mp1), 4), "mp_end": round(max(mp0, mp1), 4),
                     "mp_dir": _DIR_CODE.get(tm["dir"], 1),
                     "mp_datum": "chain_local",          # TMC-derived; see registry mp_datum
                     "matched_tmc": tm["tmc"],           # for TMC/sensor-matching QC
                     "match_dist_m": round(d, 1), "match_head_deg": round(hd, 1)})
    # QA-hardening: when NO link matches (e.g. the corridor is an arterial and gp_types is
    # freeway-only), return an EMPTY sidecar WITH the schema columns -- not a bare 0x0
    # DataFrame, whose .drop_duplicates('link_id') raises KeyError downstream.
    _cols = ["link_id", "from_node_id", "to_node_id", "route_id", "corridor_name",
             "mp_begin", "mp_end", "mp_dir", "mp_datum", "matched_tmc",
             "match_dist_m", "match_head_deg"]
    if not rows:
        return pd.DataFrame(columns=_cols)
    return pd.DataFrame(rows).drop_duplicates("link_id")


def write_sidecar(sidecar_df, path):
    sidecar_df.to_csv(path, index=False)
    return path
