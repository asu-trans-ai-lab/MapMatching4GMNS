"""TMC corridor -> standard corridor evidence (uses the built-in corridor_from_tmc)."""
from ..corridor_from_tmc import corridor_from_tmc


def to_evidence(tmc_file, road, direction):
    return corridor_from_tmc(tmc_file, road=road, direction=direction)
