# Self-demo / self-test framework

MapMatching4GMNS is **self-testing and self-demonstrating**. Its responsibility boundary:

> **MapMatching4GMNS = evidence adapter + route matching + match verification + visual review.**
> It does **not** judge which underlying network is globally "best" — that comparative role
> belongs to `qaqc4gmns`.

## The common pipeline (every case)

```
evidence → standard trace → HMM match → geometric match → agreement → trusted path
         → verification → GUI review export
```

Engine-adaptive: **geometric always runs**; **HMM runs when the native engine is built**
(`native/build_pybind.sh`, or `trace2route.exe`), else it is skipped and noted. The second run
self-validates against the case baseline (`expected_route.csv`); baselines are never overwritten
without `--update-baseline --confirm-baseline-update`.

```bash
python -m mapmatching4gmns.selfdemo --case synthetic     # or: mapmatching4gmns self-demo --case synthetic
mapmatching4gmns self-demo --all
```

Each case writes to `case_output/`: `input_manifest.json`, `normalized_trace.csv`,
`hmm_route.csv`, `geometric_route.csv`, `trusted_route.csv`, `engine_comparison.csv`,
`match_verification.csv`, `case_summary.json`, `dashboard.html`, `dashboard_layers/`,
`match_review.csv`, and `SELF_DEMO_PASS.txt` (only when the verdict passes).

## Graded verdicts (never a false binary pass)

`PASS` · `PASS_WITH_ENGINE_DISAGREEMENT` · `REVIEW_REQUIRED` · `FAIL`. Thresholds are **per-case**
(each case's `expected.yml`), not global — an ambiguous real trace can land in `REVIEW_REQUIRED`
rather than a forced pass.

## Cases (the ladder)

| # | case | source | status |
|---|---|---|---|
| 0 | **synthetic golden** | GPS trace + a competing frontage + ramp | **implemented, runs in CI** |
| 1 | **I-95 trip / connected-vehicle** | trip-path + CV | **implemented (public fixture in CI; real data local-only)** |
| 2 | **TMC → GMNS corridor** | `TMC_Identification.csv` | **implemented, runs in CI** |
| 3 | **GTFS → road GMNS** | route `shapes.txt` | **implemented, runs in CI** |
| 4 | **LRS → GMNS** | route centerline + `events.csv` | **implemented, runs in CI** |

Case 0 is the smallest fully-bundled test (`examples/self_demo/00_synthetic/`): parallel
directional facilities, a ramp, a competing-but-incorrect path, a noisy trace, and string link
ids. It verifies install, both engines, direction, connected-path, link-id preservation,
cross-engine comparison, output schemas, and GUI export.

## Review contract (visual, not editing)

`match_review.csv` records a reproducible human-in-the-loop history:
`review_id, trace_id, issue_type, hmm_link_ids, geometric_link_ids, trusted_link_ids,
review_status, reviewer_decision (ACCEPT_TRUSTED|ACCEPT_HMM|ACCEPT_GEOMETRIC|REPLACE_PATH|
INSUFFICIENT_EVIDENCE), replacement_link_ids, review_note`. The dashboard toggles raw trace / HMM /
geometric / trusted layers — visual review, not network editing (GUI4GMNS-aligned).

**`apply-review` (implemented).** A reviewer fills `reviewer_decision` (and `replacement_link_ids`
for `REPLACE_PATH`); the command applies the decisions and writes the corrected result — **without
editing the GMNS network**:

```bash
mapmatching4gmns apply-review case_output/ --network examples/self_demo/00_synthetic
```

- `ACCEPT_TRUSTED|ACCEPT_HMM|ACCEPT_GEOMETRIC` → that engine's recorded link set for the row.
- `REPLACE_PATH` → `replacement_link_ids`, **validated** against the network (`--network`): unknown
  link ids are `REJECTED`; a non-contiguous chain is `APPLIED` with a connectivity warning.
- `INSUFFICIENT_EVIDENCE` → accepts no route and flags the row for more data.

Outputs (into the case dir): `reviewed_route.csv` (corrected sequence: `review_id, trace_id, seq,
link_id`), `match_review_resolved.csv` (input rows + `review_status` + `applied_link_ids` +
`apply_note`; the input file is left untouched), and `review_applied.json` (per-row summary +
applied/rejected/open counts). The step is idempotent and re-runnable.

## Case 2 — TMC → GMNS corridor (implemented)

`examples/self_demo/02_tmc/` (freeway corridor + 5 eastbound TMCs + a frontage distractor).
Beyond the common outputs it writes `tmc_gmns_crosswalk.csv` (tmc_code → gmns_link_id +
projected mileposts + direction_match + confidence), `tmc_milepost.csv`, `tmc_unmatched.csv`, and
`tmc_verification.csv`, and verifies: **corridor continuity, direction agreement, sequence
preservation (sᵢ₊₁ ≥ sᵢ), milepost monotonicity, gateway traversal, TMC coverage, and one-to-many
handling** (a single TMC may legitimately map to several planning links — the relation is
preserved, not forced 1:1).

## Case 1 — I-95 trip / connected-vehicle (implemented)

Two evidence streams through the same contract (`adapters/i95.py`):
- **trip-path** — sparse, long, clean trajectories → direct evidence.
- **connected-vehicle (CV)** — dense/noisy: `clean_cv` drops duplicates and stationary points
  (speed ≈ 0 or < 5 m step), then matches; a **thinning-stability** check re-matches a thinned
  trajectory and requires the link set to stay stable (graded → `REVIEW_REQUIRED` if marginal).

**Public fixture** (`examples/self_demo/01_i95`) is sanitized/synthetic and runs in CI. A richer
**visualization portal** ships in `examples/portals/i95_va/` (deck.gl `datahub.html`, `gmns.kml`,
kepler configs, `network.geojson`) — built by GUI4GMNS from the **synthesized** I-95 output of the
MIT-licensed [USDOT JPO CodeHub Data Cleaning and Fusion Tool](https://github.com/usdot-jpo-codehub/data-cleaning-and-fusion-tool)
(see `examples/portals/i95_va/ATTRIBUTION.md`). `adapters.i95.portal_to_network` builds a GMNS
network from that portal's `network.geojson`. Any genuinely restricted feed stays in a gitignored
`local_data/`; nothing proprietary is committed.

## Case 3 — GTFS → road GMNS (implemented)

`examples/self_demo/03_gtfs/` (arterial corridor + a parallel local-street distractor + a synthetic
GTFS feed). `adapters/gtfs.py` takes the route's representative **shape** (`shapes.txt`) as the
ordered corridor evidence; with `gp_types: ['3']` the matcher snaps the bus route onto the arterial
and ignores the parallel local street (transit-on-roads matching). Verifies connected path +
expected-route agreement + baseline.

## Case 4 — LRS → GMNS (implemented)

`examples/self_demo/04_lrs/` (freeway corridor + frontage distractor + a linear-referenced route).
`adapters/lrs.py` turns the route centerline (`route.csv`: `route_id, measure, x_coord, y_coord`)
into corridor evidence, and `project_events` maps each event range in `events.csv`
(`begin_measure`–`end_measure`, e.g. speed-limit / lane changes) onto the matched links →
`lrs_event_crosswalk.csv`. Verifies connected path, expected-route agreement, and
`lrs_event_coverage` (every event lands on ≥1 link).

## Datasets

Every case ships a **synthetic, self-contained public fixture** under `examples/self_demo/` so the
whole ladder runs in CI with no external download or licensed data. Each adapter also consumes the
corresponding **real** source:

| case | bundled fixture | real source it targets |
|---|---|---|
| 0 synthetic | hand-built GPS trace | any GPS/GNSS trajectory |
| 1 I-95 | sanitized trip + CV points | USDOT JPO CodeHub *Data Cleaning & Fusion Tool* synthesized I-95 output (MIT; portal in `examples/portals/i95_va/`); real INRIX/RITIS/VDOT probe feeds stay local-only |
| 2 TMC | 5-TMC `TMC_Identification.csv` | INRIX/RITIS TMC network (licensed → local-only) |
| 3 GTFS | synthetic 1-route feed | any open GTFS feed (GTFS is an open spec; feeds via the Mobility Database / transit.land are generally openly licensed) |
| 4 LRS | synthetic route + events | state DOT roadway inventory / LRS — e.g. ADOT AllRoads / ATIS LRS (AZGeo open data) or FHWA HPMS route-and-measure |

Licensed/agency source **records** are never committed — only adapters, schemas, and synthetic
fixtures. Anything restricted stays in a gitignored `local_data/`.

## Roadmap

M1 harness + synthetic + CI **(done)** → M2 TMC **(done)** → M3 I-95 trip + CV **(done)** → M4 GUI
review contract + `apply-review` **(done)** → M5 GTFS **(done)** → M6 LRS **(done)**. All six cases
plug into the **same adapter + verification contract** — not one-off notebooks — and run in CI.

## Restricted data

Real ITS feeds (INRIX/RITIS probe, VDOT, CV) are **local-only** and never committed — the package
provides adapters + schemas and a sanitized public fixture, but no restricted source records. No
source record is copied into case outputs unless expressly permitted.
