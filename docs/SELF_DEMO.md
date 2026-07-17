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
| 1 | I-95 trip / connected-vehicle | trip-path + CV (local, restricted data) | adapter stub (`adapters/i95.py`) |
| 2 | **TMC → GMNS corridor** | `TMC_Identification.csv` | **implemented, runs in CI** |
| 3 | GTFS → road GMNS | shapes / stops | adapter stub (`adapters/gtfs.py`) |
| 4 | LRS → GMNS | route events + measures | adapter stub (`adapters/lrs.py`) |

Case 0 is the smallest fully-bundled test (`examples/self_demo/00_synthetic/`): parallel
directional facilities, a ramp, a competing-but-incorrect path, a noisy trace, and string link
ids. It verifies install, both engines, direction, connected-path, link-id preservation,
cross-engine comparison, output schemas, and GUI export.

## Review contract (visual, not editing)

`match_review.csv` records a reproducible human-in-the-loop history:
`review_id, trace_id, issue_type, hmm_link_ids, geometric_link_ids, trusted_link_ids,
review_status, reviewer_decision (ACCEPT_TRUSTED|ACCEPT_HMM|ACCEPT_GEOMETRIC|REPLACE_PATH|
INSUFFICIENT_EVIDENCE), replacement_link_ids, review_note`. `mapmatching4gmns apply-review`
regenerates a corrected result (Milestone 4). The dashboard toggles raw trace / HMM / geometric /
trusted layers — visual review, not network editing (GUI4GMNS-aligned).

## Case 2 — TMC → GMNS corridor (implemented)

`examples/self_demo/02_tmc/` (freeway corridor + 5 eastbound TMCs + a frontage distractor).
Beyond the common outputs it writes `tmc_gmns_crosswalk.csv` (tmc_code → gmns_link_id +
projected mileposts + direction_match + confidence), `tmc_milepost.csv`, `tmc_unmatched.csv`, and
`tmc_verification.csv`, and verifies: **corridor continuity, direction agreement, sequence
preservation (sᵢ₊₁ ≥ sᵢ), milepost monotonicity, gateway traversal, TMC coverage, and one-to-many
handling** (a single TMC may legitimately map to several planning links — the relation is
preserved, not forced 1:1).

## Roadmap

M1 self-demo harness + synthetic + CI **(done)** → M2 TMC **(done)** → M3 I-95 local (trip + CV) → M4 GUI
review contract → M5 GTFS → M6 LRS. New cases plug into the **same adapter + verification
contract**, not one-off notebooks.

## Restricted data

Real ITS feeds (INRIX/RITIS probe, VDOT, CV) are **local-only** and never committed — the package
provides adapters + schemas and a sanitized public fixture, but no restricted source records. No
source record is copied into case outputs unless expressly permitted.
