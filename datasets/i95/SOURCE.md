# I-95 GPS integration fixture

These files were copied from the
[`datasets/I95` example](https://github.com/yajunliu99/mapmatcher4gmns/tree/19f2ae3def09e7bb1494fa348d7a913d15aa1a4f/datasets/I95)
in the sibling `mapmatcher4gmns` repository.

The files first appeared together in upstream commit
[`19f2ae3`](https://github.com/yajunliu99/mapmatcher4gmns/commit/19f2ae3def09e7bb1494fa348d7a913d15aa1a4f)
on 2026-08-31.

Only the reusable inputs are included. They are the canonical I-95 dataset for this package:

- `gps.csv`: 467 GPS observations in 5 journeys
- `node.csv`: 113 GMNS nodes
- `link.csv`: 132 GMNS links

SHA-256 checksums of the copied files:

```text
e5fab1ec1b372ba17298d45dc7ec4cdfc1af1e3ae41817d066b0567e26902cc3  gps.csv
eb73ce567a5f391192a2692f27cb90653207ac7308189ed010e36133911239d8  node.csv
0a931b483d881e25a0442f711154ab5c575d53aa4875c7bc65508f8cfc93ce16  link.csv
```

The sibling repository's generated result and QGIS files are deliberately excluded. Its stored
result had 390 matched point rows, while a fresh `mapmatcher4gmns 0.2.1` run produced 382 rows and
different route sequences. Those generated files are therefore not treated as ground truth.
`expected_routes.csv` records the five complete routes from the fresh 0.2.1 run as a software
regression baseline, not as surveyed truth.

The sibling repository does not identify the upstream collector, agency, or dataset license for
the 467 GPS observations. Their provenance can therefore be stated only as the sibling
`mapmatcher4gmns` I-95 example; they must not be attributed to INRIX, RITIS, VDOT, USDOT, or
another source without additional evidence.

This fixture checks installation, field conversion, route completeness, link validity,
connectivity, and deterministic regression behavior. It is not an independently surveyed
accuracy benchmark.
