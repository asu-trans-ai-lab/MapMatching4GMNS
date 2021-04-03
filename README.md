# Matching2Path

Please send your comments to <xzhou74@asu.edu> if you have any suggestions and
questions.

Based on input network and given GPS trajectory data, the map-matching program
of Matching2Path aims to find most likely route in terms of node sequence in the
underlying network, with the following data flow chart.

![](media/5d46d46e6d66cfe932399f796dcd713c.png)

The 2D grid system aims to speed up the indexing of GSP points to the network.
For example, a 10x10 grid for a network of 100 K nodes could lead to 1K nodes in
each cell. We first identify all cells traveled by a GPS trace, so only a small
subset of the network will be loaded in the resulting shortest path algorithm.

The link cost estimation step calculates a generalized weight/cost for each link
in the cell, that is, the distance from nearly GPS points to a link inside the
cell. The likely path finding algorithm selects the least cost path with the
smallest generalized cumulative cost from the beginning to the end of the GPS
trace.

1.  **Data flow**

| **Input files** | **Output files** |
|-----------------|------------------|
| node.csv        | agent.csv        |
| link.csv        |                  |
| input_agent.csv |                  |

2.  **Input file description**

    **File node.csv** gives essential node information of the underlying
    (subarea) network in GMNS format, including node_id, x_coord and y_coord.

![](media/1fa21c1d6e8cfdd05b74ce9d3f48bf9f.png)

**File link.csv** provides essential link information of the underlying
(subarea) network, including link_id, from_node_id and to_node_id.

![](media/1f78e34e3e8ff4091a1997e44825a503.png)

**Input trace file** as input_agent.csv. The geometry field describes longitude
and latitude of each GPS point along the trace of each agent. In the following
example there are exactly 2 GPS points as the origin and destination locations,
while other examples can include more than 2 GPS points along the trace. The
geometry field follows the WKT format.

https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry

![](media/308de5075f12b12dab40c3309182b047.png)

1.  **Output file description**

    **File agent.csv** describes the most-likely path for each agent based on
    input trajectories.

![](media/caec124ffd9a88d841b924a0dda3d3b7.png)

**Reference:**

This code is implemented based on a published paper in Journal of Transportation
Research Part C:

Estimating the most likely space–time paths, dwell times and path uncertainties
from vehicle trajectory data: A time geographic method

https://www.sciencedirect.com/science/article/pii/S0968090X15003150
