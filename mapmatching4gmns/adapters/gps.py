"""GPS / connected-vehicle trace -> standard corridor evidence."""
import math


def _hav_mi(a, b):
    R = 3958.8
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp = math.radians(b[1] - a[1]); dl = math.radians(b[0] - a[0])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(x)))


def trace_to_evidence(trace_df, direction="AB", corridor_id="trace"):
    """trace_df with x_coord/y_coord (ordered) -> CorridorEvidence (reference_points + segments)."""
    import pandas as pd
    from ..corridor_from_tmc import CorridorEvidence
    pts = trace_df.rename(columns={"x_coord": "longitude", "y_coord": "latitude"}).copy()
    pts["longitude"] = pd.to_numeric(pts["longitude"]); pts["latitude"] = pd.to_numeric(pts["latitude"])
    pts = pts.reset_index(drop=True)
    rows = []; mp = 0.0
    xy = list(zip(pts.longitude, pts.latitude))
    for i in range(len(xy) - 1):
        a, b = xy[i], xy[i + 1]
        seg = _hav_mi(a, b)
        rows.append({"tmc": f"{corridor_id}_{i}", "road": corridor_id, "direction": direction,
                     "seq": i, "road_order": i, "start_longitude": a[0], "start_latitude": a[1],
                     "end_longitude": b[0], "end_latitude": b[1], "mp_begin": mp, "mp_end": mp + seg})
        mp += seg
    seg_df = pd.DataFrame(rows)
    mpb = float(seg_df["mp_begin"].min()) if len(seg_df) else 0.0
    mpe = float(seg_df["mp_end"].max()) if len(seg_df) else 0.0
    return CorridorEvidence(corridor_id=corridor_id, corridor_name=corridor_id, direction=direction,
                            source_type="gps_trace", route_label=corridor_id,
                            milepost_begin=mpb, milepost_end=mpe, confidence_score=1.0,
                            reference_segments=seg_df, reference_points=pts[["longitude", "latitude"]])
