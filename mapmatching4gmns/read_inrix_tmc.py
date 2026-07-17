"""Read an INRIX/RITIS TMC_Identification.csv into a tidy, de-duplicated segment table.

TMC_Identification files list one row per TMC segment per active date-range, so the same
TMC appears several times (one per RITIS data period). This reader keeps one row per TMC
(the most recent active period) and normalizes the columns Corridor2GMNS needs.

Standard columns: tmc, road, direction, intersection, state, county, zip,
start_latitude, start_longitude, end_latitude, end_longitude, miles, road_order, type,
active_start_date, active_end_date.
"""
import pandas as pd

_KEEP = ["tmc", "road", "direction", "intersection", "county", "zip",
         "start_latitude", "start_longitude", "end_latitude", "end_longitude",
         "miles", "road_order", "type"]


def read_tmc_identification(path):
    """Return a DataFrame of unique TMC segments (one row per tmc, latest active period),
    with numeric coordinate/mile/order columns and the raw fields kept."""
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    # numeric coercions
    for c in ["start_latitude", "start_longitude", "end_latitude", "end_longitude",
              "miles", "road_order"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # keep the most recent active period per TMC (latest active_start_date)
    if "active_start_date" in df.columns:
        df["_start"] = pd.to_datetime(df["active_start_date"], errors="coerce", utc=True)
        df = df.sort_values("_start").drop_duplicates("tmc", keep="last").drop(columns="_start")
    else:
        df = df.drop_duplicates("tmc", keep="last")
    cols = [c for c in _KEEP if c in df.columns]
    return df[cols].reset_index(drop=True)


def list_roads(df):
    """(road, direction) pairs present, with segment count + total miles -- use this to
    see what corridors a TMC file actually contains before selecting one."""
    g = (df.groupby(["road", "direction"])
           .agg(n_tmc=("tmc", "size"), miles=("miles", "sum"))
           .reset_index().sort_values("miles", ascending=False))
    return g
