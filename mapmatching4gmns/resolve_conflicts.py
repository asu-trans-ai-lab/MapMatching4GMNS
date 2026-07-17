"""Resolve the dual-engine result into a single trusted MatchedPath + a trust label.

Rule-based (the "QA agent" decision): on agreement, trust the higher-fidelity engine; on
disagreement, do not silently pick one -- return the flagged pair for review.
"""
from .compare_match_results import HIGH, OK, REVIEW, FAILED


def resolve(path_a, path_b, comparison, *, prefer="engine_hmm"):
    """Return {trusted_path, trust, note}. `prefer` names the engine to trust when both
    agree (the internal HMM is usually higher-fidelity for GPS; the geometric engine for
    directed TMC centerlines)."""
    v = comparison.get("verdict")
    if v == FAILED:
        return {"trusted_path": None, "trust": FAILED, "note": comparison.get("reason", "")}
    if v == REVIEW:
        return {"trusted_path": None, "trust": REVIEW,
                "note": "engines disagree: " + ", ".join(comparison.get("flags", [])) or "review"}
    # agreement (HIGH or OK): pick the preferred engine's path if present
    by_engine = {p.source_engine: p for p in (path_a, path_b) if p}
    trusted = by_engine.get(prefer) or path_a or path_b
    return {"trusted_path": trusted, "trust": v,
            "note": f"engines agree ({comparison.get('link_jaccard')} link Jaccard); "
                    f"trusting {trusted.source_engine}"}
