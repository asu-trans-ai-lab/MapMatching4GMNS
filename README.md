# MapMatching2GMNS

Please send your comments to <xzhou74@asu.edu> if you have any suggestions and
questions.

Based on input network and given GPS trajectory data, the map-matching program
of MapMatching4GMNS aims to find the most likely route in terms of node sequence
in the underlying network, with the following data flow chart.

Test Python Script: https://github.com/asu-trans-ai-lab/MapMatching4GMNS/blob/master/MapMatching4GMNS.ipynb 

[GMNS: General Modeling Network
Specification (GMNS) ](https://github.com/zephyr-data-specs/GMNS)

1.  **Read standard GMNS network files** node and link files

2.  **Read GPS trace.csv** file

    Note: the M2G program will convert trace.csv to input_agent.csv for
    visualization in NeXTA.

3.  **Construct 2d grid system** to speed up the indexing of GSP points to the
    network. For example, a 10x10 grid for a network of 100 K nodes could lead
    to 1K nodes in each cell.

4.  **Identify the related subarea** for the traversed cells by each GPS trace,
    so only a small subset of the network will be loaded in the resulting
    shortest path algorithm.

5.  **Identify the origin and destination** nodes in the grid for each GPS
    trace, in case, the GPS trace does not start from or end at a node inside
    the network (in this case, the boundary origin and destination nodes will be
    identified). The OD node identification is important to run the following
    shortest path algorithm.

6.  **Estimate link cost** to calculate a generalized weight/cost for each link
    in the cell, that is, the distance from nearly GPS points to a link inside
    the cell.

7.  Use **likely path finding algorithm** selects the least cost path with the
    smallest generalized cumulative cost from the beginning to the end of the
    GPS trace.

8.  **Identify matched timestamps** of each node in the likely path

9.  **Output agent file** with **map-matched node sequence** and time sequence

10. **Output link performance** with **estimated link travel time and delay**
    based on free-flow travel time of each link along the GPS matched routes

11. **Data flow**

| **Input files** | **Output files** |
|-----------------|------------------|
| node.csv        | agent.csv        |
| link.csv        |                  |
| input_agent.csv |                  |

12. **Input file description**

    **File node.csv** gives essential node information of the underlying
    (subarea) network in GMNS format, including node_id, x_coord and y_coord.

![](media/22d8257ea35209b83eefefa4eec814c0.png)

**File link.csv** provides essential link information of the underlying
(subarea) network, including link_id, from_node_id and to_node_id.

![](media/1f78e34e3e8ff4091a1997e44825a503.png)

**Input trace file** as

The agent id is GPS trace id, x_coord and y_coord should be consistent to the
network coordinate defined in node.csv and link.cvs. Fields hh mm and ss
correspond the hour, minute and second for the related GPS timestamp. We use
separate columns directly to avoid confusion caused by different time coding
formats.

![](media/5fdd74e09597da19d58779b8aaa7fc60.png)

Another format of trace file is input_agent.csv, which could come from the
[grid2demand](https://github.com/asu-trans-ai-lab/grid2demand) program. The
geometry field describes longitude and latitude of each GPS point along the
trace of each agent. In the following example there are exactly 2 GPS points as
the origin and destination locations, while other examples can include more than
2 GPS points along the trace. The geometry field follows the WKT format.

https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry

![](media/308de5075f12b12dab40c3309182b047.png)

1.  **Output file description**

    **File agent.csv** describes the most-likely path for each agent based on
    input trajectories.

![](media/caec124ffd9a88d841b924a0dda3d3b7.png)

The original input_agent.csv and resulting agent.csv can be visualized through
NeXTA.

1.  Load the network node.csv and click on the following 4 buttons or menu check
    box.

    ![](media/bb2f8e2690c0478afdef7893260e5a16.png)

2.  The original GPS trace is shown in green and the map-matched route in the
    network is displayed in purple. The user can use the scroll wheel of the
    mouse to zoom in the focused area.

![](media/2c3e07d7afef6c519cf7ee331e0bace5.png)

**Reference:**

This code is implemented based on a published paper in Journal of Transportation
Research Part C:

Estimating the most likely space–time paths, dwell times and path uncertainties
from vehicle trajectory data: A time geographic method

https://www.sciencedirect.com/science/article/pii/S0968090X15003150
