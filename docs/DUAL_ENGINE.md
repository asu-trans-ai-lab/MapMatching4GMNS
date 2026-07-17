# Dual-engine map matching = quality control

A single matcher can be confidently wrong. Two independent matchers catch each other. That is
the design: both engines emit the **same `MatchedPath` schema**, and a comparator scores their
agreement — the comparator never sees engine internals, only the schema.

## The two engines

- **Engine 1 — native (`trace2route`, Zhou).** A most-likely **connected path** from origin to
  destination, guided by the trace (time-geographic least-cost path; Tang et al. 2015 — **not** a
  Hidden Markov Model). Returns a routable link sequence — the right input for assignment / OD.
  Slower (loads the network), and needs the corridor inside its clip. Keyword `engine="native"`
  (legacy alias `"hmm"`; the `hmm_*` output columns below are Engine 1's, same legacy label).
- **Engine 2 — geometric.** Projects the corridor centerline onto nearby links (buffer + heading
  + distance). Fast, full-network, returns a link set with **per-link milepost**. Can have gaps.

> These are the two engines *inside* this package. A distinct **third** option — Yajun Liu's
> `mapmatcher4gmns` (a real HMM matcher, TrackIt/GoTrackIt lineage) — can be driven via
> `mapmatcher4gmns_adapter`, but that path is currently gated pending upstream fixes. Don't confuse
> `mapmatcher4gmns` (Yajun) with `mapmatching4gmns` (this package).

## The comparison (`compare`)

Given two `MatchedPath`, `compare` reports:

- **link Jaccard** — |A∩B| / |A∪B| on normalized link ids (the headline agreement)
- **link_jaccard_raw** — before id normalization; a large gap flags `link_id_representation_differs`
- **direction** — start/end node agreement
- **milepost** — matched-extent agreement (within tolerance)
- **gateway** — subarea entry/exit agreement (when present)

…and a **verdict**: `high_confidence_match` · `acceptable_match` · `needs_manual_review` ·
`failed_match`. `dual_match` (via `match(engine="both")`) then **resolves** a single trusted path.

## Gotchas the comparator handles

- **link_id representation.** Engine 1 emits `193912`, Engine 2 emits `193912AB` — identical
  physical links reading as total disagreement (Jaccard 0). Ids are normalized before comparison
  (and Engine 1 now preserves the `AB/BA` suffix at the source).
- **link count is not a quality metric.** A fine mesh yields more links for the same route. Use
  the **coverage ratio** (`mm_metrics`: matched length / input length ≈ 1.0), not raw count.
- **`gp_types` is a string filter.** Pass `{"1","2","3"}`, not `{1,2,3}` — ints match 0 links.

## When to use which

| need | engine |
|---|---|
| routable connected path (assignment / OD) | **native** (alias `hmm`) |
| fast attribute tagging / milepost profiles | **geometric** |
| a trustworthy result | **both** — agreement (Jaccard ≥ 0.8) is the confidence |
| corridor may fall outside a tight clip | **geometric** (full network) |
