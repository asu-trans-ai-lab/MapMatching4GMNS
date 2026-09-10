"""Engine 2 -- public GMNS geometric map matcher.

Wraps the built-in geometric/heading matcher (mapmatch_corridor_to_gmns) and returns the
standard MatchedPath. Correct for directed TMC/corridor centerline evidence; dependency-free
and always available. This is the open engine that ships with the package.
"""
from .mapmatch_corridor_to_gmns import match_corridor
from .match_schema import matched_path_from_sidecar

NAME = "engine_gmns"


def available():
    return True


def match(evidence, base_link_df, gp_types, *, chain=None, **kw):
    """Return a MatchedPath for the corridor evidence via the geometric matcher."""
    sidecar = match_corridor(evidence, base_link_df, gp_types, **kw)
    return matched_path_from_sidecar(evidence.corridor_id, sidecar, engine=NAME, chain=chain)
