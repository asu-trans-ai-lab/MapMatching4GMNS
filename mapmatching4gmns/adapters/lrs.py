"""lrs evidence adapter — a linear-referencing route -> standard corridor evidence.

LRS data references attributes to a route by *measure* (milepost): a route centerline carries
ordered (measure, lon, lat) vertices, and events (speed limit, lanes, pavement, ...) are given as
[begin_measure, end_measure] ranges on that route. This adapter turns the route centerline into the
ordered corridor evidence the matchers consume; `project_events` maps event measure-ranges onto the
matched GMNS links (a milepost crosswalk, like the TMC case).

Measure unit: the route's cumulative distance in miles (the evidence builder measures haversine
miles from the first vertex), so event measures should be miles-from-route-start.

Datasets: state DOT roadway inventory / LRS — e.g. ADOT AllRoads / ATIS LRS (AZGeo open data) or
FHWA HPMS route-and-measure tables. The bundled self-demo fixture in examples/self_demo/04_lrs is
synthetic and self-contained.
"""
import csv


def read_route(route_csv):
    """route_csv: route_id, measure, x_coord|lon, y_coord|lat — returns rows ordered by measure."""
    rows = []
    with open(route_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            lon = r.get("x_coord", r.get("lon")); lat = r.get("y_coord", r.get("lat"))
            rows.append((float(r["measure"]), float(lon), float(lat), str(r.get("route_id", ""))))
    rows.sort()
    return rows


def read_events(events_csv):
    """events_csv: event_id, route_id, begin_measure, end_measure, attribute, value."""
    out = []
    with open(events_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out.append({"event_id": r.get("event_id"), "route_id": r.get("route_id"),
                        "begin_measure": float(r["begin_measure"]), "end_measure": float(r["end_measure"]),
                        "attribute": r.get("attribute", ""), "value": r.get("value", "")})
    return out


def to_evidence(route_csv, direction="AB", corridor_id=None):
    """LRS route centerline -> CorridorEvidence (reference_points + segments) via the GPS builder."""
    import pandas as pd
    from .gps import trace_to_evidence
    rows = read_route(route_csv)
    if not rows:
        raise ValueError(f"empty LRS route: {route_csv}")
    rid = rows[0][3] or "lrs"
    df = pd.DataFrame({"x_coord": [x for _, x, _, _ in rows], "y_coord": [y for _, _, y, _ in rows]})
    return trace_to_evidence(df, direction=direction, corridor_id=corridor_id or f"lrs_{rid}")


def project_events(events, sidecar):
    """Map each LRS event [begin,end] measure-range onto matched GMNS links.

    `sidecar` is the geometric matcher output (one row per matched link) carrying route mileposts
    `mp_begin`/`mp_end`. An event maps to every link whose milepost span overlaps the event range.
    Returns a list of dicts: event_id, attribute, value, begin/end measure, matched link ids, and
    whether it was covered by at least one link.
    """
    rows = sidecar.to_dict("records") if sidecar is not None else []
    out = []
    for ev in events:
        b, e = ev["begin_measure"], ev["end_measure"]
        hit = [str(r.get("link_id")) for r in rows
               if r.get("mp_begin") is not None and r.get("mp_end") is not None
               and float(r["mp_end"]) > b - 1e-9 and float(r["mp_begin"]) < e + 1e-9]
        out.append({"event_id": ev["event_id"], "attribute": ev["attribute"], "value": ev["value"],
                    "begin_measure": b, "end_measure": e,
                    "link_ids": ";".join(hit), "n_links": len(hit), "covered": bool(hit)})
    return out
