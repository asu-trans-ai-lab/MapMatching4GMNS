"""Build CorridorEvidence from an INRIX/RITIS TMC file (SPEC Layer A).

TMCs already carry a route label, a direction, per-segment length (miles), and a
`road_order` that sequences them along the route. That is exactly a corridor definition:
order the TMCs by road_order within (road, direction), accumulate miles into a milepost,
and emit an ordered reference chain the downstream map-matcher can conflate onto a GMNS
base network.
"""
from dataclasses import dataclass, field

import pandas as pd

from .read_inrix_tmc import read_tmc_identification, list_roads


@dataclass
class CorridorEvidence:
    corridor_id: str
    corridor_name: str
    direction: str
    source_type: str                 # 'inrix_tmc'
    route_label: str
    milepost_begin: float
    milepost_end: float
    confidence_score: float
    reference_segments: "pd.DataFrame"   # ordered: tmc, seq, mp_begin, mp_end, lat/lon, ...
    reference_points: "pd.DataFrame"     # ordered endpoints (lon/lat) for map-matching
    meta: dict = field(default_factory=dict)

    def summary(self):
        return (f"{self.corridor_id} [{self.route_label} {self.direction}] "
                f"{len(self.reference_segments)} TMCs, "
                f"MP {self.milepost_begin:.2f}-{self.milepost_end:.2f} "
                f"({self.milepost_end - self.milepost_begin:.1f} mi), conf {self.confidence_score:.2f}")


def _ordered_chain(sub):
    """Order one (road, direction) group by road_order and accumulate milepost."""
    sub = sub.sort_values("road_order").reset_index(drop=True)
    sub["seq"] = range(1, len(sub) + 1)
    mp = 0.0
    mpb, mpe = [], []
    for m in sub["miles"].fillna(0.0):
        mpb.append(mp); mp += float(m); mpe.append(mp)
    sub["mp_begin"] = mpb; sub["mp_end"] = mpe
    return sub


def corridor_from_tmc(tmc_path, road=None, direction=None, corridor_id=None):
    """Build CorridorEvidence for one (road, direction). If road/direction are None, pick
    the (road, direction) with the most corridor miles. Returns one CorridorEvidence.

    Use `evidences_from_tmc` to build all (road, direction) corridors in a file at once."""
    df = read_tmc_identification(tmc_path)
    roads = list_roads(df)
    if road is None:
        road = roads.iloc[0]["road"]
    cand = roads[roads.road == road]
    if direction is None:
        direction = cand.sort_values("miles", ascending=False).iloc[0]["direction"]
    sub = df[(df.road == road) & (df.direction == direction)].copy()
    if len(sub) == 0:
        raise ValueError(f"no TMC segments for road={road!r} direction={direction!r} in {tmc_path}")
    sub = _ordered_chain(sub)
    cid = corridor_id or f"{road}_{direction[:2]}"
    pts = _endpoints(sub)
    return CorridorEvidence(
        corridor_id=cid, corridor_name=road, direction=direction, source_type="inrix_tmc",
        route_label=road, milepost_begin=float(sub.mp_begin.min()),
        milepost_end=float(sub.mp_end.max()),
        confidence_score=_confidence(sub),
        reference_segments=sub, reference_points=pts,
        meta={"tmc_file": tmc_path, "n_tmc": int(len(sub))})


def evidences_from_tmc(tmc_path, min_miles=1.0):
    """Build a CorridorEvidence for every (road, direction) in the file with >= min_miles."""
    df = read_tmc_identification(tmc_path)
    out = []
    for _, r in list_roads(df).iterrows():
        if r["miles"] < min_miles:
            continue
        out.append(corridor_from_tmc(tmc_path, road=r["road"], direction=r["direction"]))
    return out


def _endpoints(sub):
    """Ordered lon/lat points along the chain (each TMC start, plus the final end) --
    the trace the map-matcher will snap onto the GMNS network."""
    rows = []
    for _, r in sub.iterrows():
        rows.append({"seq": r.seq, "role": "start", "longitude": r.start_longitude,
                     "latitude": r.start_latitude, "mp": r.mp_begin, "tmc": r.tmc})
    last = sub.iloc[-1]
    rows.append({"seq": len(sub) + 1, "role": "end", "longitude": last.end_longitude,
                 "latitude": last.end_latitude, "mp": last.mp_end, "tmc": last.tmc})
    return pd.DataFrame(rows)


def _confidence(sub):
    """Simple confidence: fraction of segments with a valid order + length + coordinates,
    penalized if road_order has gaps (chain may be discontinuous)."""
    ok = sub[["road_order", "miles", "start_latitude", "end_latitude"]].notna().all(axis=1).mean()
    orders = sub["road_order"].dropna().astype(float).round().astype(int).tolist()
    gaps = sum(1 for a, b in zip(orders, orders[1:]) if b - a > 3)
    penalty = min(0.3, 0.05 * gaps)
    return round(max(0.0, float(ok) - penalty), 3)


def write_corridor_reference(ev, out_csv):
    """Emit corridor_reference_link.csv (SPEC step 1 output)."""
    cols = ["seq", "tmc", "road", "direction", "intersection", "mp_begin", "mp_end", "miles",
            "start_longitude", "start_latitude", "end_longitude", "end_latitude", "road_order"]
    cols = [c for c in cols if c in ev.reference_segments.columns]
    out = ev.reference_segments[cols].copy()
    out.insert(0, "corridor_id", ev.corridor_id)
    out.insert(1, "source_type", ev.source_type)
    out.to_csv(out_csv, index=False)
    return out_csv
