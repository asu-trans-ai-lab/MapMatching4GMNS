"""Adapter for `mapmatcher4gmns` -- an *optional third engine*.

`mapmatcher4gmns` (by Yajun Liu, https://github.com/yajunliu99/mapmatcher4gmns) is a *separate*
Hidden Markov Model matcher (TrackIt/GoTrackIt lineage) -- NOT part of this package's two engines
(Engine 1 native `trace2route`, Engine 2 geometric). This adapter is the seam to run it as a third
engine when a user wants the HMM path for noisy GPS/probe traces. It normalizes the result into the
sidecar schema, adding a `matcher_engine` column so every downstream artifact records how it was
matched. The HMM path is currently gated (see `_match_via_hmm`) pending the upstream fixes below.

Honest status: `mapmatcher4gmns` 0.1.9 has 5 blocking bugs on real GMNS + modern pandas
(documented with a reproduction kit at docs/mapmatcher4gmns_repro in the parent repo:
`infer_datetime_format` removed, unguarded temp-col delete, int()-only link_id, blank
zone_id crash, silent multicore data loss). Until those are fixed upstream, the HMM path is
gated, and the default engine is the built-in geometric matcher.

Engine selection (`engine=`):
  'auto'            -> built-in geometric matcher. Correct default for TMC-segment and
                       corridor-polyline evidence (directed centerline chords, not noisy
                       GPS); proven ~3 m median on AZNET I-10 and dependency-free.
  'builtin'         -> force the geometric matcher.
  'mapmatcher4gmns' -> use the HMM engine (for GPS/probe traces where it genuinely wins);
                       falls back to built-in with a recorded warning if unavailable or the
                       known-broken version is installed.
"""
from .mapmatch_corridor_to_gmns import match_corridor as _geometric


def available():
    try:
        import mapmatcher4gmns  # noqa: F401
        return True
    except Exception:
        return False


def version():
    try:
        import mapmatcher4gmns
        return getattr(mapmatcher4gmns, "__version__", "?")
    except Exception:
        return None


def _ver_tuple(v):
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def is_known_broken():
    """< 0.1.10 has the 5 blocking bugs (see the repro kit); 0.1.10 fixed them.
    Returns (broken, reason)."""
    v = version()
    if v is None:
        return (False, "not installed")
    if _ver_tuple(v) < (0, 1, 10):
        return (True, f"mapmatcher4gmns {v} has 5 blocking bugs on real GMNS + pandas>=2 "
                      "(see docs/mapmatcher4gmns_repro); install >= 0.1.10 (fixed) to enable "
                      "the HMM path")
    return (False, "")


def match(evidence, base_link_df, gp_types, *, engine="auto", **kw):
    """Return (sidecar_df, engine_used, notes). sidecar carries a `matcher_engine` column."""
    notes = []
    want = engine
    if want == "auto":
        want = "builtin"    # correct for TMC/corridor evidence; see module docstring

    if want == "mapmatcher4gmns":
        broken, reason = is_known_broken()
        if not available():
            notes.append("mapmatcher4gmns not installed; fell back to built-in")
            want = "builtin"
        elif broken:
            notes.append(reason + "; fell back to built-in")
            want = "builtin"
        else:
            try:
                sc = _match_via_hmm(evidence, base_link_df, gp_types, **kw)
                sc = sc.assign(matcher_engine="mapmatcher4gmns")
                return sc, "mapmatcher4gmns", notes
            except NotImplementedError as e:
                notes.append(f"{e}; fell back to built-in")
                want = "builtin"

    sc = _geometric(evidence, base_link_df, gp_types, **kw)
    sc = sc.assign(matcher_engine="builtin")
    return sc, "builtin", notes


def _match_via_hmm(evidence, base_link_df, gp_types, **kw):
    """Convert corridor reference points -> a trace, run mapmatcher4gmns's HMM against a
    network built from base_link_df, and map the matched link sequence back to the sidecar
    schema. Implement once mapmatcher4gmns >= 0.2 lands (the repro-kit bugs fixed); the
    conversion + known workarounds (string link_id map, blank zone_id -> 0, core_num=1,
    tolerant to_datetime) are documented in docs/mapmatcher4gmns_repro."""
    raise NotImplementedError(
        "HMM matching via mapmatcher4gmns is gated on the upstream 0.1.9 fixes "
        "(docs/mapmatcher4gmns_repro)")
