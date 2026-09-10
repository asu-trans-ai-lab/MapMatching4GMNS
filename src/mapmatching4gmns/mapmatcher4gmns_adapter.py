"""Adapter for :mod:`mapmatcher4gmns`, the third map-matching engine.

`mapmatcher4gmns` (by Yajun Liu, https://github.com/yajunliu99/mapmatcher4gmns) is a *separate*
Hidden Markov Model matcher (TrackIt/GoTrackIt lineage) -- a distinct distribution from the two
engines implemented in this repository. This adapter is the seam to run it as a third
engine when a user wants the HMM path for noisy GPS/probe traces. It normalizes the complete route
into this package's sidecar schema and records the selected matcher. Version 0.2.1 is the first
release supported by this adapter.

Engine selection (`engine=`):
  'auto'            -> built-in geometric matcher. Correct default for TMC-segment and
                       corridor-polyline evidence (directed centerline chords, not noisy
                       GPS); proven ~3 m median on AZNET I-10 and dependency-free.
  'builtin'         -> force the geometric matcher.
  'mapmatcher4gmns' -> use the HMM engine (for GPS/probe traces). Missing dependencies,
                       unsupported versions, invalid inputs, and matcher failures raise errors;
                       an explicit engine selection never falls back silently.
"""
from pathlib import Path
import math
import tempfile

import pandas as pd

from .mapmatch_corridor_to_gmns import match_corridor as _geometric


_MINIMUM_VERSION = (0, 2, 1)


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
    """Require the currently validated mapmatcher4gmns release."""
    v = version()
    if v is None:
        return (False, "not installed")
    if _ver_tuple(v) < _MINIMUM_VERSION:
        return (True, f"mapmatcher4gmns {v} is unsupported; install >= 0.2.1")
    return (False, "")


def match(evidence, base_link_df, gp_types, *, engine="auto", network_dir=None,
          matcher_options=None, **kw):
    """Return (sidecar_df, engine_used, notes). sidecar carries a `matcher_engine` column."""
    notes = []
    want = engine
    if want == "auto":
        want = "builtin"    # correct for TMC/corridor evidence; see module docstring

    if want == "mapmatcher4gmns":
        if not available():
            raise RuntimeError(
                "mapmatcher4gmns is not installed; install mapmatching4gmns with its "
                "declared dependencies"
            )
        broken, reason = is_known_broken()
        if broken:
            raise RuntimeError(reason)
        if network_dir is None:
            raise ValueError("network_dir is required for engine='mapmatcher4gmns'")
        options = dict(matcher_options or {})
        options.update(kw)
        sc, adapter_notes = _match_via_hmm(
            evidence, base_link_df, gp_types, network_dir=network_dir, **options
        )
        notes.extend(adapter_notes)
        sc = sc.assign(matcher_engine="mapmatcher4gmns")
        return sc, "mapmatcher4gmns", notes

    if want != "builtin":
        raise ValueError("engine must be 'auto', 'builtin', or 'mapmatcher4gmns'")

    sc = _geometric(evidence, base_link_df, gp_types, **kw)
    sc = sc.assign(matcher_engine="builtin")
    return sc, "builtin", notes


def _field(columns, requested, candidates):
    """Resolve an optional observation field without inventing missing data."""
    if requested is not None:
        if requested not in columns:
            raise ValueError(f"requested mapmatcher4gmns field {requested!r} is missing")
        return requested
    return next((name for name in candidates if name in columns), None)


def _id_text(value):
    """Normalize CSV numeric scalars without changing meaningful string identifiers."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise ValueError("missing identifier")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    try:
        return str(value.item())
    except AttributeError:
        return str(value).strip()


def _match_via_hmm(evidence, base_link_df, gp_types, *, network_dir,
                   time_field=None, heading_field=None, speed_field=None,
                   time_format=None, **matcher_options):
    """Run mapmatcher4gmns and convert its expanded, connected route to a sidecar.

    ``gp_types`` is accepted to keep the adapter contract identical to the geometric engine.
    The HMM evaluates the complete directed network supplied in ``network_dir`` instead of
    pre-filtering it by link type.
    """
    del gp_types
    import mapmatcher4gmns as external

    network = Path(network_dir)
    node_csv = network / "node.csv"
    link_csv = network / "link.csv"
    missing = [str(path) for path in (node_csv, link_csv) if not path.is_file()]
    if missing:
        raise FileNotFoundError("mapmatcher4gmns network input missing: " + ", ".join(missing))

    points = getattr(evidence, "reference_points", None)
    if points is None or len(points) < 2:
        raise ValueError("mapmatcher4gmns requires at least two ordered reference points")
    trace = points.copy().reset_index(drop=True)
    rename = {}
    if "longitude" not in trace and "x_coord" in trace:
        rename["x_coord"] = "longitude"
    if "latitude" not in trace and "y_coord" in trace:
        rename["y_coord"] = "latitude"
    trace = trace.rename(columns=rename)
    required = {"longitude", "latitude"}
    absent = sorted(required.difference(trace.columns))
    if absent:
        raise ValueError(f"reference_points missing required columns: {absent}")
    trace["longitude"] = pd.to_numeric(trace["longitude"], errors="raise")
    trace["latitude"] = pd.to_numeric(trace["latitude"], errors="raise")
    trace["journey_id"] = str(evidence.corridor_id)
    trace = trace[["journey_id"] + [column for column in trace if column != "journey_id"]]

    resolved_time = _field(
        trace.columns, time_field, ("local_time", "timestamp", "time", "capture_time")
    )
    resolved_heading = _field(
        trace.columns, heading_field, ("heading_deg_north", "heading")
    )
    resolved_speed = _field(trace.columns, speed_field, ("speed_mph", "speed"))
    use_heading = matcher_options.pop("use_heading", resolved_heading is not None)
    reserved = {
        "network", "agent_field", "lng_field", "lat_field", "out_dir",
        "result_file", "route_file", "export_csv", "export_route", "export_geo",
        "core_num", "verbose", "show_progress",
    }
    conflicts = sorted(reserved.intersection(matcher_options))
    if conflicts:
        raise ValueError(
            "adapter controls these mapmatcher4gmns options: " + ", ".join(conflicts)
        )

    notes = []
    with tempfile.TemporaryDirectory(prefix="mapmatching4gmns_hmm_") as run_dir:
        try:
            loaded_network = external.LoadNetFromCSV(
                folder=str(network), node_file="node.csv", link_file="link.csv"
            )
        except SystemExit as exc:
            raise RuntimeError(f"mapmatcher4gmns could not load the GMNS network: {exc}") from exc

        trace_csv = Path(run_dir) / "trace.csv"
        trace.to_csv(trace_csv, index=False)
        matcher = external.MapMatcher(
            network=loaded_network,
            agent_field="journey_id",
            lng_field="longitude",
            lat_field="latitude",
            time_field=resolved_time,
            heading_field=resolved_heading,
            speed_field=resolved_speed,
            use_heading=use_heading,
            time_format=time_format,
            out_dir=run_dir,
            result_file="matched_result.csv",
            route_file="matched_route.csv",
            export_csv=True,
            export_route=True,
            export_geo=False,
            core_num=1,
            verbose=False,
            show_progress=False,
            **matcher_options,
        )
        try:
            result, warnings, errors = matcher.match(str(trace_csv))
        except SystemExit as exc:
            raise RuntimeError(f"mapmatcher4gmns failed: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"mapmatcher4gmns failed: {exc}") from exc

        if errors:
            raise RuntimeError(f"mapmatcher4gmns did not match the trajectory: {errors}")
        # The 0.2.1 streaming API writes the result CSVs and intentionally returns an
        # empty DataFrame.  Its __stream_stats__ record is run metadata, not a warning.
        stream_stats = warnings.get("__stream_stats__", {}) if isinstance(warnings, dict) else {}
        actual_warnings = ({key: value for key, value in warnings.items()
                            if key != "__stream_stats__"}
                           if isinstance(warnings, dict) else warnings)
        matched_rows = stream_stats.get("rows_matched")
        if matched_rows is not None and int(matched_rows) <= 0:
            raise RuntimeError("mapmatcher4gmns returned no matched GPS points")
        if actual_warnings:
            notes.append(f"mapmatcher4gmns warnings: {actual_warnings}")

        route_csv = Path(run_dir) / "matched_route.csv"
        if not route_csv.is_file():
            raise RuntimeError("mapmatcher4gmns did not produce matched_route.csv")
        routes = pd.read_csv(route_csv, dtype=str, keep_default_na=False)
        if routes.empty or "link_ids" not in routes:
            raise RuntimeError("mapmatcher4gmns produced no complete route")
        route_row = routes.loc[routes["journey_id"] == str(evidence.corridor_id)]
        if route_row.empty:
            raise RuntimeError("mapmatcher4gmns route is missing the requested trajectory")
        link_ids = [item.strip() for item in route_row.iloc[0]["link_ids"].split(",")
                    if item.strip()]

    if not link_ids:
        raise RuntimeError("mapmatcher4gmns produced an empty link sequence")

    links = base_link_df.copy()
    required_link_cols = {"link_id", "from_node_id", "to_node_id"}
    absent = sorted(required_link_cols.difference(links.columns))
    if absent:
        raise ValueError(f"base_link_df missing required columns: {absent}")
    links["__adapter_link_id"] = links["link_id"].map(_id_text)
    if links["__adapter_link_id"].duplicated().any():
        raise ValueError("base_link_df contains duplicate link_id values")
    lookup = links.set_index("__adapter_link_id", drop=False)
    unknown = [link_id for link_id in link_ids if link_id not in lookup.index]
    if unknown:
        raise RuntimeError(f"mapmatcher4gmns returned unknown link IDs: {unknown}")

    rows = []
    for sequence_no, link_id in enumerate(link_ids):
        link = lookup.loc[link_id]
        rows.append({
            "sequence_no": sequence_no,
            "link_id": link_id,
            "from_node_id": link["from_node_id"],
            "to_node_id": link["to_node_id"],
            "route_id": evidence.route_label,
            "corridor_name": evidence.corridor_name,
            "mp_begin": None,
            "mp_end": None,
            "mp_dir": None,
            "mp_datum": None,
            "matched_tmc": None,
            "match_dist_m": None,
            "match_head_deg": None,
        })

    for previous, current in zip(rows, rows[1:]):
        if _id_text(previous["to_node_id"]) != _id_text(current["from_node_id"]):
            raise RuntimeError(
                "mapmatcher4gmns returned a disconnected route between links "
                f"{previous['link_id']} and {current['link_id']}"
            )
    return pd.DataFrame(rows), notes
