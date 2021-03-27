# Trace2Route

**MapMatching Program: Trace2route**

Please send your comments to <xzhou74@asu.edu> if you have any suggestions and
questions.

1.  **Data flow**

| Input files | Output files |
|-------------|--------------|
| node.csv    | agent.csv    |
| link.csv    |              |
| trace.csv   |              |

File node.csv gives essential node information of the underlying (subarea)
network in GMNS format, including node_id, x_coord and y_coord.

![](media/1fa21c1d6e8cfdd05b74ce9d3f48bf9f.png)

File link.csv provides essential link information of the underlying (subarea)
network, including link_id, from_node_id and to_node_id. In the current version,
a straight line is assumed to connect from node and to link of each link without
requiring the geometry field.

![](media/1f78e34e3e8ff4091a1997e44825a503.png)

File trace.csv descripes trajectory location points of each agent. The timestamp
format used here is hhmm:ss. In the future, we can also use DTALite

![](media/604d110f6a0bdf2a7b1b552b1172e194.png)

File agent.csv is the output file of the program. A most-likely path is given
for each agent based on input trajectories.

![](media/3c75bcdb579896286630db56d8dd9295.png)

Reference:

This code is implemented based on a published paper in Journal of Transportation
Research Part C:

Estimating the most likely space–time paths, dwell times and path uncertainties
from vehicle trajectory data: A time geographic method

https://www.sciencedirect.com/science/article/pii/S0968090X15003150
