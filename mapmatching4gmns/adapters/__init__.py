"""Evidence adapters: source records -> one standard corridor evidence (points + segments).

This is the first responsibility of MapMatching4GMNS (evidence adapter). Each adapter turns a
source (GPS/CV trace, TMC corridor, GTFS shape/stops, LRS events) into a CorridorEvidence that
both matching engines consume identically.
"""
from .gps import trace_to_evidence          # noqa: F401
from . import tmc, i95, gtfs, lrs            # noqa: F401
