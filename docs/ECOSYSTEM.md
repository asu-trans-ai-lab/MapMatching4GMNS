# Where mapmatching4gmns fits

A **component** in the GMNS toolchain: it takes traces/corridors + a GMNS network and returns
matched links (as a QA-checked dual-engine result). Other tools consume it — notably
Subarea2GMNS, which uses it to seed subarea OD.

```mermaid
flowchart LR
    TMC[INRIX / TMC]
    GPS[GPS / trajectories]
    GTFSs[GTFS shapes]
    NET[(GMNS network)]

    subgraph MM[mapmatching4gmns]
      E1[Engine 1\n trace2route native\n connected path]
      E2[Engine 2\n geometric\n link set + milepost]
      QA{compare\n agreement = QA}
      E1 --> QA
      E2 --> QA
    end

    TMC --> MM
    GPS --> MM
    GTFSs --> MM
    NET --> MM
    QA --> OUT[/matched links +\n verdict/]

    OUT --> SUB[Subarea2GMNS\n seed OD]
    OUT --> C2G[corridor2gmns]

    style MM fill:#eef2ff,stroke:#4338ca
    style E1 fill:#fff7ed,stroke:#c2843b
    style E2 fill:#fff7ed,stroke:#c2843b
    style OUT fill:#e6fffa,stroke:#2c7a7b
```

| package | role | relation |
|---|---|---|
| **mapmatching4gmns** (this) | dual-engine map matching + QA | the matcher |
| MapMatching4GMNS (`trace2route`) | Zhou's C++ engine | **integrated here as Engine 1** |
| mapmatcher4gmns (PyPI, Yajun) | separate geometric/HMM matcher | optional 3rd engine via adapter |
| corridor2gmns | corridor evidence → GMNS | upstream evidence + consumer |
| Subarea2GMNS | corridor → subarea + OD | **downstream: uses this to seed OD** |
| osm2gmns / TAPLite / DTALite | network / assignment | network in, assignment downstream |
