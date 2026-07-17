"""Common matched-path schema -- both map-matching engines emit THIS object.

The whole point of the dual-engine design is one standard output so a QA agent can compare
Engine 1 (internal HMM / MapMatching4GMNS C++) against Engine 2 (public GMNS geometric
matcher). Each engine wraps its own logic and returns a `MatchedPath`; the comparator never
sees engine internals, only this schema.
"""
from dataclasses import dataclass, field, asdict


@dataclass
class MatchedPath:
    trajectory_id: str                       # corridor/agent/trace id
    source_engine: str                       # 'engine_hmm' | 'engine_gmns'
    matched_link_sequence: list = field(default_factory=list)   # ordered link_ids
    candidate_link_sequence: list = field(default_factory=list)  # links considered (optional)
    confidence_score: float = None
    geometry_error: float = None             # mean offset (m) of trace to matched path
    transition_error: float = None           # HMM transition cost (engine_hmm only)
    direction_error: float = None            # heading disagreement (deg) where known
    start_node_id: int = None
    end_node_id: int = None
    start_milepost: float = None
    end_milepost: float = None
    subarea_origin_gateway: int = None       # first matched node inside a subarea
    subarea_destination_gateway: int = None  # last matched node inside a subarea
    matched_path_id: str = None              # engine + trajectory
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.matched_path_id is None:
            self.matched_path_id = f"{self.source_engine}:{self.trajectory_id}"

    def as_row(self):
        d = asdict(self)
        d["matched_link_sequence"] = ";".join(str(x) for x in self.matched_link_sequence)
        d["candidate_link_sequence"] = ";".join(str(x) for x in self.candidate_link_sequence)
        d.pop("meta", None)
        return d


SCHEMA_COLUMNS = [
    "matched_path_id", "trajectory_id", "source_engine",
    "matched_link_sequence", "candidate_link_sequence", "confidence_score",
    "geometry_error", "transition_error", "direction_error",
    "start_node_id", "end_node_id", "start_milepost", "end_milepost",
    "subarea_origin_gateway", "subarea_destination_gateway",
]


def matched_path_from_sidecar(trajectory_id, sidecar, *, engine="engine_gmns",
                              chain=None):
    """Build a MatchedPath from a Corridor2GMNS matcher sidecar (link_id + mp + match_dist).
    If `chain` (the ordered topological chain) is given, use its link order; else use the
    sidecar order sorted by mp_begin."""
    import pandas as pd
    df = chain if (chain is not None and len(chain)) else sidecar
    order_col = "mpb" if (chain is not None and "mpb" in getattr(chain, "columns", [])) else "mp_begin"
    if order_col in df.columns:
        df = df.sort_values(order_col)
    links = [str(x) for x in df["link_id"].tolist()]
    mpb = pd.to_numeric(sidecar.get("mp_begin"), errors="coerce") if "mp_begin" in sidecar else None
    mpe = pd.to_numeric(sidecar.get("mp_end"), errors="coerce") if "mp_end" in sidecar else None
    gerr = None
    if "match_dist_m" in sidecar:
        gerr = round(float(pd.to_numeric(sidecar.match_dist_m, errors="coerce").mean()), 2)
    derr = None
    if "match_head_deg" in sidecar:
        derr = round(float(pd.to_numeric(sidecar.match_head_deg, errors="coerce").max()), 1)
    return MatchedPath(
        trajectory_id=str(trajectory_id), source_engine=engine,
        matched_link_sequence=links,
        confidence_score=round(1.0 - min(1.0, (gerr or 0) / 300.0), 3) if gerr is not None else None,
        geometry_error=gerr, direction_error=derr,
        start_milepost=round(float(mpb.min()), 3) if mpb is not None and len(mpb) else None,
        end_milepost=round(float(mpe.max()), 3) if mpe is not None and len(mpe) else None)
