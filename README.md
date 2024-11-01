# MapMatching4GMNS

Please send your comments to [xzhou74@asu.edu](mailto:xzhou74@asu.edu) if you have any suggestions and questions.

A work-in-progress user guide can be found at

[User Guide of Trace2Route_v3 - Google Docs](https://docs.google.com/document/d/1ZfUZ3OkZtNu9zwarQUN8XfnSBc8LvDT9HkMFgq9_jds/edit)

## 1. Introduction

Based on input network and given GPS trajectory data, the map-matching program of MapMatching4GMNS (trace2route.exe) aims to find the most likely route in terms of node sequence in the underlying network, with the following data flow chart.

GMNS: General Modeling Network Specification (GMNS) (<https://github.com/zephyr-data-specs/GMNS>)

## 2. Data flow

|                              | **files**          | **Data Source**                                                                                                                                                 | **Visualization**                                                                                                |
|------------------------------|--------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| GMNS network input           | node.csv, link.csv | [Openstreetmap](https://osm2gmns.readthedocs.io/en/latest/)                                                                                                     | [QGIS](https://www.qgis.org/en/site/), [web interface for GMNS](https://asu-trans-ai-lab.github.io/index.html#/) |
| Location sequence data input | trace.csv          | GPS traces downloaded from OpenStreetMap, e.g., using the script at <https://github.com/asu-trans-ai-lab/MapMatching4GMNS/blob/master/release/get_gps_trace.py> | QGIS                                                                                                             |
| Map-matched output           | route.csv          |                                                                                                                                                                 | QGIS                                                                                                             |

**Windows Executable: trace2route.exe** can be found from

<https://github.com/asu-trans-ai-lab/MapMatching4GMNS/tree/master/release>

## 3. File description

>   **File node.csv** gives essential node information of the underlying network in GMNS format, including node_id, x_coord and y_coord.

![](media/22d8257ea35209b83eefefa4eec814c0.png)

**File link.csv** should include essential link information of the underlying (subarea) network, including from_node_id, to_node_id, length and geometry.

![](media/1da34b49eeacb8a53bd98896d6e5953e.png)

**Input trace file** as

The agent ID (as a string) correspond to the GPS trace ID. Please ensure that x_coord and y_coord match the network coordinates as defined in node.csv and link.csv. Including fields o_node_id and d_node_id is essential to establish a clear starting and ending point within the network, facilitating accurate path searches for the most likely route.

![A screenshot of a table Description automatically generated](media/5d98e8ab46a2aca617f926a7cdcaa989.png)

Fields hh mm and ss correspond the hour, minute and second for the related GPS timestamp. We use separate columns directly to avoid confusion caused by different time coding formats.

![](media/5fdd74e09597da19d58779b8aaa7fc60.png)

Please note that, for mapping applications such as mapping sensor TMC corridors to the planning network, mapping bus lines to the highway driving network, the fields of hh, mm, ss are not needed. But we need to specify the origin node (identified by the first coordinate point) clearly so that the most likely path algorithm can be correctly performed.

**Output file description**

>   **File route.csv** describes the most-likely path for each agent based on input trajectories.

![](media/fbc4d80da3096a50ccd22e8d396b689c.png)

## 4. Visualization

### Step 1: Load GMNS files in QGIS

Install and open QGIS and click on menu Layer-\>Add-\>Add Delimited Text Layer. In the following dialogue box, load GMNS node.csv and link.csv, and ensure  
“point coordinates” is selected as geometry definition for node.csv wit x_coord and y_coord for “Geometry field”, and WKT is selected as geometry definition for link.csv.

![](media/3e5f92dd1b7d253cde1e9f627a6962ce.png)

![](media/d38aebb8269ae232b9ea5a684558eced.png)

### Step 2: Load XYZ Tiles in QGIS with background maps

Find XYZ Tiles and double-click OpenStreetMap on Browser panel. Please move the background layer to the bottom to show the GMNS network.

Refence: <https://gis.stackexchange.com/questions/20191/adding-basemaps-from-google-or-bing-in-qgis>

### Step 3. Visualize input trace and output route files in QGIS

The 'geometry' field can be obtained from link.csv file. Then open this file in the same way as above. (Menu Layer-\>Add-\>Add Delimited Text Layer)

![](media/4442e2534b75cc10507d353a26516509.png)

![](media/a83fb77f142a7b676f7c9f3f80953d0b.png)

![](media/bee94517db0f70b722b56c6fa93f2cfe.png)

## 5. Algorithm

1.  **Read standard GMNS network files** node and link files, **Read GPS trace.csv** file
2.  Note: the TRACE2ROUTE program will convert trace.csv to input_agent.csv for visualization in NeXTA.
3.  **Construct 2d grid system** to speed up the indexing of GSP points to the network. For example, a 10x10 grid for a network of 100 K nodes could lead to 1K nodes in each cell.
4.  **Identify the related subarea** for the traversed cells by each GPS trace, so only a small subset of the network will be loaded in the resulting shortest path algorithm.
5.  **Identify the origin and destination** nodes in the grid for each GPS trace, in case, the GPS trace does not start from or end at a node inside the network (in this case, the boundary origin and destination nodes will be identified). The OD node identification is important to run the following shortest path algorithm.
6.  **Estimate link cost** to calculate a generalized weight/cost for each link in the cell, that is, the distance from nearly GPS points to a link inside the cell.
7.  Use **likely path finding algorithm** selects the least cost path with the smallest generalized cumulative cost from the beginning to the end of the GPS trace.
8.  **Identify matched timestamps** of each node in the likely path
9.  **Output route.csv** with **estimated link travel time and delay** based on free-flow travel time of each link along the GPS matched routes

## Reference

This code is implemented partially based on a published paper in Transportation Research Part C:

Tang J, Song Y, Miller HJ, Zhou X (2015) “Estimating the most likely space–time paths, dwell times and path uncertainties from vehicle trajectory data: A time geographic method,” *Transportation Research Part C*, <http://dx.doi.org/10.1016/j.trc.2015.08.014>
