"""mapmatching4gmns — multi-engine map matching for GMNS.

The core QA pair is Engine 1 (native trace2route) plus Engine 2 (geometric projection).
Engine 3 integrates the separate mapmatcher4gmns HMM for GPS/probe trajectories.
"""
__version__ = "0.3.0"
from .api import (MatchedPath, corridor_from_tmc, engines_available, match,
                  match_from_tmc, compare)
__all__ = ["MatchedPath", "corridor_from_tmc", "engines_available", "match",
           "match_from_tmc", "compare", "__version__"]
