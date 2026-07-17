# Synthetic example (open, no private data)

A 5-node freeway corridor (`link_type=1`) and a 3-TMC eastbound `TMC_Identification.csv`.

```python
import mapmatching4gmns as mm
p = mm.match_from_tmc("examples/synthetic/TMC_Identification.csv", "SR-DEMO", "EASTBOUND",
                      network_dir="examples/synthetic", engine="geometric")
print(p.matched_link_sequence)     # links along the corridor
```

Engine 2 (**geometric**) runs with just pandas/numpy. Engine 1 (**native** `trace2route`, keyword
`engine="native"`, legacy alias `"hmm"`) additionally needs the native module built from `native/`
(see the top-level README).
