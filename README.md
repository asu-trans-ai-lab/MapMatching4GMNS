# MapMatching4GMNS

`mapmatching4gmns` 0.3.0 provides one Python API for three GMNS map-matching engine selectors:

| Selector | Implementation | Intended use | Output |
|---|---|---|---|
| `native` | packaged C++ `trace2route` extension | most-likely connected paths | ordered, routable link sequence |
| `geometric` | built-in Python centerline matcher | TMC, GTFS, LRS, and corridor conflation | matched links with local mileposts |
| `mapmatcher4gmns` | adapter to the separate `mapmatcher4gmns` HMM package | noisy GPS and probe trajectories | expanded, connected link sequence |

The legacy selector `hmm` is an alias for `native`; it does not select the external HMM.
Use `engine="mapmatcher4gmns"` for the actual HMM package.

`engine="both"` retains the established two-engine QA workflow: it runs `native` and
`geometric`, compares them, and resolves a trusted result. It does not currently run all three
engines.

## Installation

```bash
python -m pip install mapmatching4gmns
```

One installation command provides all three selectors. The platform wheel contains the native
extension and geometric engine; pip installs `mapmatcher4gmns>=0.2.1,<0.3` and its Python
dependencies for the third selector.

Version 0.3.0 targets CPython 3.9 through 3.14 on:

- Linux x86_64
- Windows AMD64
- macOS x86_64
- macOS arm64

Installing from an sdist instead of a wheel requires CMake and a C++14 compiler.

Verify the installed engine entry points:

```python
import mapmatching4gmns as mm

print(mm.__version__)
print(mm.engines_available())
```

## Quick start

### TMC or corridor evidence

```python
import mapmatching4gmns as mm

evidence = mm.corridor_from_tmc(
    "TMC_Identification.csv",
    road="I-95",
    direction="NORTHBOUND",
)

native_path = mm.match(
    evidence,
    network_dir="network",
    engine="native",
)

geometric_path = mm.match(
    evidence,
    network_dir="network",
    engine="geometric",
)

qa = mm.match(
    evidence,
    network_dir="network",
    engine="both",
)
```

The single-engine calls return `MatchedPath`. The `both` call returns a QA dictionary containing
the two paths, agreement metrics, flags, and the selected trusted path.

### GPS evidence with the third engine

```python
import pandas as pd
import mapmatching4gmns as mm
from mapmatching4gmns.adapters.gps import trace_to_evidence

gps = pd.read_csv("gps.csv")
evidence = trace_to_evidence(gps, corridor_id="trip-001")

hmm_path = mm.match(
    evidence,
    network_dir="network",
    engine="mapmatcher4gmns",
    mapmatcher_options={"search_radius": 25.0},
)
```

`trace_to_evidence` accepts `x_coord`/`y_coord` or `longitude`/`latitude`. It preserves optional
observation fields. The third-engine adapter automatically recognizes these common names:

| Meaning | Recognized fields |
|---|---|
| trajectory time | `local_time`, `timestamp`, `time`, `capture_time` |
| heading | `heading_deg_north`, `heading` |
| speed | `speed_mph`, `speed` |

Explicit third-engine selection is strict. Missing dependencies, unsupported versions, invalid
inputs, an empty result, unknown link IDs, or a disconnected expanded route raise an error instead
of silently falling back to `geometric`.

## Input requirements

All engines use a GMNS network directory containing `node.csv` and `link.csv`.

### `node.csv`

Required shared fields:

- `node_id`
- `x_coord`
- `y_coord`

### `link.csv`

Core fields used across the engines:

- `link_id`
- `from_node_id`
- `to_node_id`
- `geometry` as WKT `LINESTRING`

Additional requirements differ by engine:

| Engine | Additional fields |
|---|---|
| native | `length` and `free_speed` are used when available; internal defaults are retained for older fixtures |
| geometric | `link_type`, used with `gp_types` to select matchable facilities |
| mapmatcher4gmns | `lanes`; accepts the other standard GMNS link attributes |

Coordinates must be longitude/latitude for the packaged workflows and fixtures.
String link IDs, including direction suffixes and meaningful leading zeros, are preserved.

## Public API

```python
mm.match(
    evidence,
    network_dir=None,
    base_link_df=None,
    gp_types=("1", "2", "3"),
    engine="both",
    mapmatcher_options=None,
)
```

Supported selectors:

- `native`: packaged `trace2route` connected-path engine
- `hmm`: legacy alias for `native`
- `geometric`: built-in centerline projection engine
- `mapmatcher4gmns`: external HMM through the strict adapter
- `both`: native+geometric comparison and resolution

`network_dir` is required by `native`, `mapmatcher4gmns`, and normal `both` use. For
`geometric`, callers may supply either `network_dir` or a preloaded `base_link_df`.

Every single-engine result uses the common `MatchedPath` schema, including:

- trajectory and engine identifiers
- ordered matched and candidate link sequences
- start/end nodes when available
- geometric, transition, direction, and confidence fields when the engine can provide them
- engine-specific provenance in `meta`

Not every engine estimates every field. Missing metrics remain `None`; the package does not invent
mileposts or confidence values for the HMM route.

## Packaged validation data

The canonical fixtures live under `datasets/` in the source repository and are copied into each
wheel under `mapmatching4gmns/data/`.

```text
datasets/
├── gtfs/
├── i95/
├── lrs/
└── tmc/
```

| Dataset | Purpose |
|---|---|
| `i95` | canonical GPS integration: 467 observations, 5 journeys, 113 nodes, 132 links |
| `tmc` | TMC-to-GMNS conflation, milepost, coverage, and gateway checks |
| `gtfs` | GTFS shape evidence regression |
| `lrs` | LRS route and event projection regression |

The I-95 folder contains only reusable inputs copied from the sibling `mapmatcher4gmns` example,
plus a fresh 0.2.1 software regression baseline. Generated matcher outputs are not copied from the
sibling repository. See the
[`SOURCE.md` provenance record](https://github.com/asu-trans-ai-lab/MapMatching4GMNS/blob/v0.3.0/datasets/i95/SOURCE.md)
for file hashes and the evidence boundary. The upstream collector and dataset license for these
GPS observations are not documented, so they must not be attributed to a specific agency.

These datasets verify packaging, conversion, route mechanics, connectivity, and regression
stability. They are not independently surveyed accuracy ground truth. In particular, successful
execution or cross-engine agreement must not be reported as an external accuracy measurement.

## Self-demo and review workflow

The CLI provides one canonical I-95 GPS batch case and three native+geometric evidence cases:

- `i95`
- `tmc`
- `gtfs`
- `lrs`

Run one case or all cases:

```bash
mapmatching4gmns self-demo --case tmc
mapmatching4gmns self-demo --all
```

Outputs are written under `self_demo_report/<case>/` by default. Depending on the case, they
include:

- `normalized_trace.csv`
- `mapmatcher_routes.csv` and `journey_verification.csv` for I-95
- `hmm_route.csv` (`hmm` is the legacy native-engine label)
- `geometric_route.csv`
- `trusted_route.csv`
- `engine_comparison.csv`
- `match_verification.csv`
- `case_summary.json`
- `dashboard.html`
- `match_review.csv`
- source-specific TMC or LRS crosswalk files

The TMC, GTFS, and LRS cases generate a local, self-contained dashboard and review contract. The
I-95 batch case writes one verified route per journey and does not collapse the five journeys into
one dashboard/review row. This repository no longer stores the old screenshots, notebook, or
historical visualization portal referenced by earlier README versions.

To apply a human review without editing the GMNS network:

```bash
mapmatching4gmns apply-review \
    self_demo_report/tmc \
    --network datasets/tmc
```

The reviewer fills `reviewer_decision` in `match_review.csv`. Supported decisions are
`ACCEPT_TRUSTED`, `ACCEPT_HMM`, `ACCEPT_GEOMETRIC`, `REPLACE_PATH`, and
`INSUFFICIENT_EVIDENCE`. The command writes `reviewed_route.csv`,
`match_review_resolved.csv`, and `review_applied.json`.

The I-95 self-demo and `tests/test_third_engine.py` require all five GPS journeys to match the
stored software regression routes. A separate integration assertion runs one selected journey
through all three engine entry points.

## Development and testing

```bash
git clone https://github.com/asu-trans-ai-lab/MapMatching4GMNS.git
cd MapMatching4GMNS

python -m pip install -e ".[dev]"
python -m pytest tests -q
```

The source layout is:

```text
mapmatching4gmns/
├── src/mapmatching4gmns/
│   └── _native_src/
├── datasets/
├── tests/
├── dist/                 # local build output; ignored by Git
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitattributes
└── .gitignore
```

Build local release artifacts:

```bash
python -m pip install -e ".[release]"
python -m build --sdist --wheel
python -m twine check --strict dist/*
```

The native source is built with scikit-build-core, CMake, and pybind11. It is compiled into
`mapmatching4gmns._native`; no external executable is required. See the
[`PORTABILITY_NOTES.md`](https://github.com/asu-trans-ai-lab/MapMatching4GMNS/blob/v0.3.0/src/mapmatching4gmns/_native_src/PORTABILITY_NOTES.md)
build notes.

GitHub Actions uses cibuildwheel in separate source-test, wheel-build, and trusted-PyPI-release
workflows. The release matrix expects 24 wheels: six CPython versions across four
OS/architecture targets, plus one sdist. `dist/` is local output and is not committed.

## Package relationship and attribution

The similarly named projects remain distinct:

| Package | Repository | Role here |
|---|---|---|
| `mapmatching4gmns` | <https://github.com/asu-trans-ai-lab/MapMatching4GMNS> | this multi-engine package, native code, geometric matcher, QA, adapters, and review workflow |
| `mapmatcher4gmns` | <https://github.com/yajunliu99/mapmatcher4gmns> | separately maintained HMM package used by the third-engine adapter |

The package authors are Xuesong (Simon) Zhou, Kai (Frank) Zhang, Jiawei Lu, and Yajun Liu.
For questions about the package, contact [xzhou74@asu.edu](mailto:xzhou74@asu.edu).

The package is distributed under the
[MIT License](https://github.com/asu-trans-ai-lab/MapMatching4GMNS/blob/v0.3.0/LICENSE).

## Reference

The native most-likely-path implementation is partially based on:

Tang, J., Song, Y., Miller, H. J., and Zhou, X. (2015). “Estimating the most likely space-time
paths, dwell times and path uncertainties from vehicle trajectory data: A time geographic
method.” *Transportation Research Part C*, 66, 16–35.
<https://doi.org/10.1016/j.trc.2015.08.014>
