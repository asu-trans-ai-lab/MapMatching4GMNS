"""mapmatching4gmns — unified API over three engine selectors.

Engine 1 (native):    Zhou's `trace2route` — a most-likely **connected-path** matcher (time-
                      geographic; Tang et al. 2015), built as an in-process pybind module
                      (`_native_src/`). Returns a routable, connected link path. Keyword: engine="native"
                      (legacy alias: "hmm").
Engine 2 (geometric): centerline projection matcher. Fast; returns a link set + milepost.

Use any engine independently. ``engine="both"`` retains the established Engine 1 + Engine 2
quality-control comparison (agreement = confidence).

Not to be confused with `mapmatcher4gmns` (by Yajun Liu) — a *separate* HMM matcher
(TrackIt/GoTrackIt lineage) that this package drives as a third engine via
`mapmatcher4gmns_adapter`.
"""
import os

from . import corridor_from_tmc as _cft
from . import engine_hmm_internal as _hmm
from . import engine_gmns_public as _geo
from . import match_report as _report
from . import mapmatcher4gmns_adapter as _third
from .compare_match_results import compare as compare_paths
from .match_schema import MatchedPath, matched_path_from_sidecar


def corridor_from_tmc(tmc_file, road=None, direction=None):
    """Build corridor evidence (ordered TMC reference points/segments) from a TMC file."""
    return _cft.corridor_from_tmc(tmc_file, road=road, direction=direction)


def engines_available(network_dir=None):
    """Report whether each packaged or declared map-matching engine can run."""
    avail = _hmm.available()
    return {"native": avail, "hmm_native": avail, "geometric": True,
            "mapmatcher4gmns": _third.available() and not _third.is_known_broken()[0]}


def _base_links(network_dir, base_link_df):
    if base_link_df is not None:
        return base_link_df
    import pandas as pd
    return pd.read_csv(os.path.join(network_dir, "link.csv"), low_memory=False)


def match(evidence, network_dir=None, base_link_df=None, gp_types=("1", "2", "3"),
          engine="both", mapmatcher_options=None):
    """Match `evidence` (from corridor_from_tmc) to a GMNS network.

    engine: 'native' (Engine 1, native trace2route connected path; needs network_dir;
                       legacy alias 'hmm'),
            'geometric' (Engine 2; needs network_dir or base_link_df),
            'mapmatcher4gmns' (Engine 3 HMM; needs network_dir),
            'both' (run both, return the dual-engine QA record with agreement + resolution).
    Returns a MatchedPath (single engine) or a QA dict (both).
    """
    if engine in ("native", "hmm"):        # 'hmm' kept as a legacy alias for Engine 1
        return _hmm.match(evidence, network_dir)
    if engine == "geometric":
        return _geo.match(evidence, _base_links(network_dir, base_link_df), set(gp_types))
    if engine == "mapmatcher4gmns":
        sidecar, engine_used, notes = _third.match(
            evidence,
            _base_links(network_dir, base_link_df),
            set(gp_types),
            engine="mapmatcher4gmns",
            network_dir=network_dir,
            matcher_options=mapmatcher_options,
        )
        path = matched_path_from_sidecar(
            evidence.corridor_id, sidecar, engine="engine_mapmatcher4gmns"
        )
        path.meta.update({"backend": engine_used, "adapter_notes": notes})
        return path
    if engine == "both":
        return _report.dual_match(evidence, _base_links(network_dir, base_link_df),
                                  set(gp_types), network_dir=network_dir)
    raise ValueError(
        "engine must be 'native' (alias 'hmm'), 'geometric', "
        "'mapmatcher4gmns', or 'both'"
    )


def match_from_tmc(tmc_file, road, direction, network_dir, base_link_df=None,
                   gp_types=("1", "2", "3"), engine="both", mapmatcher_options=None):
    """Convenience: TMC file -> evidence -> match, in one call."""
    ev = corridor_from_tmc(tmc_file, road, direction)
    return match(ev, network_dir=network_dir, base_link_df=base_link_df,
                 gp_types=gp_types, engine=engine,
                 mapmatcher_options=mapmatcher_options)


def compare(path_a, path_b, **kw):
    """Compare two MatchedPath (link agreement + direction + milepost + gateways) -> verdict."""
    return compare_paths(path_a, path_b, **kw)


__all__ = ["MatchedPath", "corridor_from_tmc", "engines_available", "match",
           "match_from_tmc", "compare"]
