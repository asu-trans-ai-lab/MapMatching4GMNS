"""Uniform map-matching quality metrics across all three modalities.

trace2route is one engine; the trace source differs (macro agent path / TMC corridor / GTFS
shape). To compare quality fairly, every modality is reduced to the SAME record:

  input agents (traces submitted)  ->  matched agents (>=1 route link)  ->  coverage.

A route.csv (TMC/GTFS) or agent.csv (meso) is read; metrics are computed the same way so the
three modalities line up in one comparison table.
"""
import csv
import math


def _haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def trace_lengths(trace_csv, agent_field="agent_id", x="x_coord", y="y_coord"):
    """Per-agent input polyline length (m) and point count from a trace.csv."""
    pts = {}
    with open(trace_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            a = r.get(agent_field)
            try:
                pts.setdefault(a, []).append((float(r[x]), float(r[y])))
            except (KeyError, ValueError, TypeError):
                continue
    out = {}
    for a, seq in pts.items():
        L = sum(_haversine_m(seq[i][0], seq[i][1], seq[i + 1][0], seq[i + 1][1])
                for i in range(len(seq) - 1))
        out[a] = {"input_len_m": L, "n_points": len(seq)}
    return out


def route_matched(route_csv, agent_field="agent_id", link_field="link_id"):
    """Per-agent matched-link count from a route.csv (TMC/GTFS style)."""
    got = {}
    with open(route_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            a = r.get(agent_field)
            lid = r.get(link_field)
            if a and lid not in (None, ""):
                got.setdefault(a, set()).add(str(lid))
    return {a: len(s) for a, s in got.items()}


def _parse_linestring(geom):
    """Yield (lon,lat) from a WKT LINESTRING / MULTILINESTRING string."""
    if not geom:
        return
    s = geom.replace("MULTILINESTRING", "").replace("LINESTRING", "")
    s = s.replace("(", " ").replace(")", " ").replace(",", " , ")
    tokens = s.split(",")
    for seg in tokens:
        nums = seg.split()
        i = 0
        while i + 1 < len(nums):
            try:
                yield float(nums[i]), float(nums[i + 1])
            except ValueError:
                pass
            i += 2


def route_matched_length_m(route_csv, agent_field="agent_id", geom_field="geometry"):
    """Per-agent matched path length in METERS, summed over route.csv link geometries
    (haversine on lat/lon -> unit-robust across networks, unlike the 'length' column which
    may be miles/km/feet)."""
    L = {}
    with open(route_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            a = r.get(agent_field)
            if not a:
                continue
            pts = list(_parse_linestring(r.get(geom_field, "")))
            d = sum(_haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                    for i in range(len(pts) - 1))
            L[a] = L.get(a, 0.0) + d
    return L


def coverage_stats(input_lengths, matched_lengths):
    """Coverage ratio = matched_len / input_len per agent (~1.0 = follows the route;
    <0.7 = partial; >1.3 = detour/wander). Returns (median_ratio, per_agent dict)."""
    ratios = {}
    for a, minfo in input_lengths.items():
        inl = minfo["input_len_m"]
        ml = matched_lengths.get(a, 0.0)
        if inl > 50:  # ignore trivially short traces
            ratios[a] = ml / inl
    vals = sorted(ratios.values())
    med = vals[len(vals) // 2] if vals else 0.0
    return round(med, 3), ratios


def summarize(input_agents, matched_counts, *, modality, network, n_links, median_coverage=None):
    """Reduce to the shared metric row. input_agents: set/list of submitted agent ids;
    matched_counts: {agent_id: n_links}."""
    inp = set(str(a) for a in input_agents)
    matched = {a: c for a, c in matched_counts.items() if str(a) in inp and c > 0}
    n_in = len(inp)
    n_matched = len(matched)
    total_links = sum(matched.values())
    avg_links = round(total_links / n_matched, 2) if n_matched else 0.0
    return {
        "modality": modality,
        "network": network,
        "network_links": n_links,
        "input_agents": n_in,
        "matched_agents": n_matched,
        "match_rate_pct": round(100.0 * n_matched / n_in, 1) if n_in else 0.0,
        "total_matched_links": total_links,
        "avg_links_per_matched_agent": avg_links,
        "median_coverage_ratio": median_coverage,
        "unmatched_agents": n_in - n_matched,
    }


def write_comparison(rows, out_csv):
    cols = ["modality", "network", "network_links", "input_agents", "matched_agents",
            "match_rate_pct", "total_matched_links", "avg_links_per_matched_agent",
            "median_coverage_ratio", "unmatched_agents"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)
