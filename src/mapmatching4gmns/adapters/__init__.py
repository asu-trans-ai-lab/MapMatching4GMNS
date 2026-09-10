"""Evidence adapters: source records -> one standard corridor evidence (points + segments).

This is the first responsibility of MapMatching4GMNS (evidence adapter). Each adapter turns a
source (GPS trace, TMC corridor, GTFS shape/stops, LRS events) into a CorridorEvidence used by
the matching engines.
"""
from .gps import trace_to_evidence          # noqa: F401
from . import tmc, gtfs, lrs                 # noqa: F401
