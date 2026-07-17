"""mapmatching4gmns — dual-engine map matching for GMNS.

Two independent matchers under one API: Engine 1 (Zhou's trace2route, native most-likely-path)
and Engine 2 (geometric centerline projection). Run either, or both — agreement is the QA signal.
"""
__version__ = "0.2.0"
from .api import (MatchedPath, corridor_from_tmc, engines_available, match,
                  match_from_tmc, compare)
__all__ = ["MatchedPath", "corridor_from_tmc", "engines_available", "match",
           "match_from_tmc", "compare", "__version__"]
