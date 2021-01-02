// trace2route.cpp : This file contains the 'main' function. Program execution begins and ends there.
//
#include "stdafx.h"
#include <iostream>
#include <fstream>
#include <list> 
#include <omp.h>
#include <algorithm>
#include <time.h>
#include "CSVParser.h"
#include <math.h>

using namespace std;

#define _MAX_LABEL_COST 999999
#define _MAX_GRID_SIZE 100

int g_max_number_of_threads = 4;
int g_number_of_nodes = 0;
int g_number_of_links = 0;
int g_number_of_agents = 0;
int g_grid_size = 1;

std::map<int, int> g_internal_node_seq_no_map;
std::map<int, int> g_internal_link_no_map;
std::map<string, int> g_internal_agent_no_map;


extern void g_Program_stop();

struct GDPoint //geometry data
{
	double x;
	double y;
};

class CNode
{
public:
	int node_seq_no;  // sequence number
	int node_id;      //external node number
	string name;
	std::vector<int> m_outgoing_link_seq_no_vector;
	GDPoint pt;
};


class CLink
{
public:

	int link_id;
	string name;
	int from_node_id;
	int to_node_id;

	int link_seq_no;
	int from_node_seq_no;
	int to_node_seq_no;
	float distance;
};

std::vector<CNode> g_node_vector;
std::vector<CLink> g_link_vector;


double g_GetPoint2Point_Distance(GDPoint p1, GDPoint p2)
{
	return pow(((p1.x - p2.x) * (p1.x - p2.x) + (p1.y - p2.y) * (p1.y - p2.y)), 0.5);
}

double g_GetPoint2LineDistance(GDPoint pt, GDPoint FromPt, GDPoint ToPt, double UnitMile, bool no_intersection_requirement)
{
	float U;
	GDPoint Intersection;

	float  LineLength = g_GetPoint2Point_Distance(FromPt, ToPt);

	U = ((pt.x - ToPt.x) * (FromPt.x - ToPt.x) + (pt.y - ToPt.y) * (FromPt.y - ToPt.y)) / (LineLength * LineLength);

	if (no_intersection_requirement == false)
	{

		if (U < 0.0f || U > 1.0f)
			return max(UnitMile * 100, 999999);   // intersection does not fall within the segment
	}
	Intersection.x = ToPt.x + U * (FromPt.x - ToPt.x);
	Intersection.y = ToPt.y + U * (FromPt.y - ToPt.y);

	float distance_1 = g_GetPoint2Point_Distance(pt, Intersection);
	float distance_0 = g_GetPoint2Point_Distance(pt, FromPt);
	float distance_2 = g_GetPoint2Point_Distance(pt, ToPt);

	if (no_intersection_requirement)
	{
		return min(min(distance_1, distance_0), distance_2) / max(0.000001, UnitMile);
	}
	else
		return distance_1 / max(0.000001, UnitMile);
}

class CGPSPoint
{
public:

public:
	GDPoint pt;
	//double time_interval_no;
	string time_str;		// hhmm:ss
	int time_in_second;
};


class GridNodeSet
{
public:
	double x;
	double y;

	std::vector<int> m_NodeVector;
	std::vector<int> m_LinkNoVector;
	std::vector<CGPSPoint> m_GPSPointVector;

	int origin_cell_flag;  
	int destination_cell_flag;
	GDPoint m_o_boundary_point[2];  // from point and to point
	GDPoint m_d_boundary_point[2];

};
class CAgent
{
public:
	CAgent()
	{
		matching_link_no = -1;
	}

	string agent_id;
	int agent_no;

	int o_node_id;
	int d_node_id;
	int matching_link_no;
	int origin_node_seq_no;
	int destination_node_seq_no;
	int origin_zone_id;
	int destination_zone_id;

	int start_time_in_second;
	int end_time_in_second;
	int duration_in_second;

	std::vector<CGPSPoint> m_GPSPointVector;

	int m_node_size;
	int* path_node_vector; // final node sequqence for the path
	void AllocatePathNodeVector(int node_size, int* node_vector)  //store the data into the path node sequence
	{
		m_node_size = node_size;
		path_node_vector = new int[node_size];  // dynamic array

		for (int i = 0; i < m_node_size; i++)  // copy backward from the result of shortest path tree
		{
			path_node_vector[i] = node_vector[m_node_size - 1 - i];
		}
	}
};
vector<CAgent> g_agent_vector;

class NetworkForSP  // mainly for shortest path calculation
{
public:

	NetworkForSP()
	{
	}


	GridNodeSet** m_GridMatrix;  //important data structure for creating grid matrix 
	float m_left;  // boundary of grid matrix 
	float m_right;
	float m_top;
	float m_bottom;

	float m_GridXStep; // x resolution of grid cell
	float m_GridYStep;

	void BuildGridSystem()
	{

		m_GridMatrix = Allocate2DDynamicArray<GridNodeSet>(_MAX_GRID_SIZE, _MAX_GRID_SIZE);
		g_grid_size = min(_MAX_GRID_SIZE, g_node_vector.size() / 1000);  // dynamically determine the size of grid. e.g. for a testing network <100 nodes, use a grid size of 1.
        // g_grid_size is the number of cells horizonatally or virtically
		cout << "grid size = " << g_grid_size << endl;

		// initialization of grid rectangle boundary
		m_left = 100000000;
		m_right = -100000000;
		m_top = -1000000000;
		m_bottom = 1000000000;

		// exapnd the grid boundary according to the nodes 
		for (int i = 0; i < g_node_vector.size(); i++)
		{
			m_left = min(m_left, g_node_vector[i].pt.x);
			m_right = max(m_right, g_node_vector[i].pt.x);
			m_top = max(m_top, g_node_vector[i].pt.y);
			m_bottom = min(m_bottom, g_node_vector[i].pt.y);

		}

		m_GridXStep = max(0.0001, (m_right - m_left) / g_grid_size);
		m_GridYStep = max(0.0001, (m_top - m_bottom) / g_grid_size);  // both x and y resolutions are the same


		// put nodes into grid cell

		for (int i = 0; i < g_node_vector.size(); i++)
		{
			int x_key = (g_node_vector[i].pt.x - m_left) / m_GridXStep;  // x_key internal x horizonal index of grid 
			int y_key = (g_node_vector[i].pt.y - m_bottom) / m_GridYStep;

			//feasible region in case of out of bound 
			x_key = max(0, x_key);
			x_key = min(g_grid_size - 1, x_key);

			y_key = max(0, y_key);
			y_key = min(g_grid_size - 1, y_key);

			m_GridMatrix[x_key][y_key].m_NodeVector.push_back(i);

		}

		// put links into grid cell

		for (int l = 0; l < g_link_vector.size(); l++)
		{
			int x_key = (g_node_vector[g_link_vector[l].from_node_seq_no].pt.x - m_left) / m_GridXStep;  // from node
			int y_key = (g_node_vector[g_link_vector[l].from_node_seq_no].pt.y - m_bottom) / m_GridYStep;

			//feasible region
			x_key = max(0, x_key);
			x_key = min(g_grid_size - 1, x_key);

			y_key = max(0, y_key);
			y_key = min(g_grid_size - 1, y_key);

			m_GridMatrix[x_key][y_key].m_LinkNoVector.push_back(l);

			int from_x_key = x_key;
			int from_y_key = y_key;

			x_key = (g_node_vector[g_link_vector[l].to_node_seq_no].pt.x - m_left) / m_GridXStep;  //to node
			y_key = (g_node_vector[g_link_vector[l].to_node_seq_no].pt.y - m_bottom) / m_GridYStep;

			//feasible region
			x_key = max(0, x_key);
			x_key = min(g_grid_size - 1, x_key);

			y_key = max(0, y_key);
			y_key = min(g_grid_size - 1, y_key);

			if (from_x_key != x_key || from_y_key != y_key)  // when the from node and to node of a link belong to  different cells.
			{
				m_GridMatrix[x_key][y_key].m_LinkNoVector.push_back(l);
			}



			/// put this link to the next cells. 

		}


	}


	void AddGPSPointsIntoGridSystem(int agent_no)
	{  // for every agent 

		for (int x_i = 0; x_i < g_grid_size; x_i++)
			for (int y_i = 0; y_i < g_grid_size; y_i++)
			{
				m_GridMatrix[x_i][y_i].origin_cell_flag = 0;
				m_GridMatrix[x_i][y_i].destination_cell_flag = 0;
				m_GridMatrix[x_i][y_i].m_GPSPointVector.clear();  //reset the existing GPS point records in this grid 
			}


		for (int l = 0; l < g_link_vector.size(); l++)  // reset the cost for all links 
		{
			m_link_generalised_cost_array[l] = _MAX_LABEL_COST/1000;  // feasible range
		}
		// put GPS points into grid cell


		for (int g = 0; g < g_agent_vector[agent_no].m_GPSPointVector.size(); g++)  // for each GPS point
		{ // x_key and y_key are relative index of grid
			int x_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.x - m_left) / m_GridXStep;
			int y_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.y - m_bottom) / m_GridYStep;

			//feasible region
			x_key = max(0, x_key);
			x_key = min(g_grid_size - 1, x_key);

			y_key = max(0, y_key);
			y_key = min(g_grid_size - 1, y_key);

			m_GridMatrix[x_key][y_key].m_GPSPointVector.push_back(g_agent_vector[agent_no].m_GPSPointVector[g]);


			if (g == 0)  // mark starting GPS point to find the o_node for shortest path
			{

				m_GridMatrix[x_key][y_key].origin_cell_flag = true;
				m_GridMatrix[x_key][y_key].m_o_boundary_point[0] = g_agent_vector[agent_no].m_GPSPointVector[g].pt;
				
				if(g_agent_vector[agent_no].m_GPSPointVector.size()>=2)
				{
				m_GridMatrix[x_key][y_key].m_o_boundary_point[1] = g_agent_vector[agent_no].m_GPSPointVector[g+1].pt;
				}
			}
			else if (g == g_agent_vector[agent_no].m_GPSPointVector.size() - 1 && (g_agent_vector[agent_no].m_GPSPointVector.size() >= 2))  //ending GPS point to find the d_node 
			{

				m_GridMatrix[x_key][y_key].destination_cell_flag = true;
				m_GridMatrix[x_key][y_key].m_d_boundary_point[0] = g_agent_vector[agent_no].m_GPSPointVector[g - 1].pt;
				m_GridMatrix[x_key][y_key].m_d_boundary_point[1] = g_agent_vector[agent_no].m_GPSPointVector[g].pt;

			}


		}

		// for each grid matrix cell
			//scan x and y index in the grid
		// m_link_generalised_cost_array is the link cost used in shortest path


		for (int x_i = 0; x_i < g_grid_size; x_i++)
			for (int y_i = 0; y_i < g_grid_size; y_i++)
			{

				// for each grid cell
				// second, we now select the mininum of GPS point (in the same cell) to link distance to set the link cost 
				for (int g = 0; g < m_GridMatrix[x_i][y_i].m_GPSPointVector.size(); g++)  // for each GPS point of an agent in the cell 
				{
					if (g == m_GridMatrix[x_i][y_i].m_GPSPointVector.size() - 1)  // boundary points
						continue;


					// compute the average distance from the GPS points (g, g+1) to the ending points of a link
					for (int local_l = 0; local_l < m_GridMatrix[x_i][y_i].m_LinkNoVector.size(); local_l++)  // for all links in this cell
					{
						int l = m_GridMatrix[x_i][y_i].m_LinkNoVector[local_l];

						double distance_from = g_GetPoint2Point_Distance(m_GridMatrix[x_i][y_i].m_GPSPointVector[g].pt, g_node_vector[g_link_vector[l].from_node_seq_no].pt);
						double distance_to = 0;
						
						if(g_agent_vector[agent_no].m_GPSPointVector.size() >= 2)
						{ 
							distance_to = g_GetPoint2Point_Distance(m_GridMatrix[x_i][y_i].m_GPSPointVector[g + 1].pt, g_node_vector[g_link_vector[l].to_node_seq_no].pt);
						}

						// distance from is the distance from GPS point g to from node of link
						// distance to is the distance from GPS point g to to node of link
						double distance = (distance_from + distance_to)/2;
						if (distance < m_link_generalised_cost_array[l])
						{
							m_link_generalised_cost_array[l] = distance;  // use this distance as the likelihood cost
		
					
						}
					}
				}

				if (m_GridMatrix[x_i][y_i].origin_cell_flag == 1)  //   find origin node of shortest path
				{
					double min_distance_to_boundary_point = _MAX_LABEL_COST;
					for (int local_l = 0; local_l < m_GridMatrix[x_i][y_i].m_LinkNoVector.size(); local_l++)  // for all links in this cell
					{
						int l = m_GridMatrix[x_i][y_i].m_LinkNoVector[local_l];

						
						
						double distance_from = g_GetPoint2LineDistance(m_GridMatrix[x_i][y_i].m_o_boundary_point[0],
							g_node_vector[g_link_vector[l].from_node_seq_no].pt, g_node_vector[g_link_vector[l].to_node_seq_no].pt,
							1, true);

						double distance_to = 0;

						if (g_agent_vector[agent_no].m_GPSPointVector.size() >= 2)
						{
							distance_to = g_GetPoint2LineDistance(m_GridMatrix[x_i][y_i].m_o_boundary_point[1],
								g_node_vector[g_link_vector[l].from_node_seq_no].pt, g_node_vector[g_link_vector[l].to_node_seq_no].pt,
								1, true);
						}

						double distance_from_p2p = g_GetPoint2Point_Distance(m_GridMatrix[x_i][y_i].m_o_boundary_point[0] , g_node_vector[g_link_vector[l].from_node_seq_no].pt);
						double distance_to_p2p = g_GetPoint2Point_Distance(m_GridMatrix[x_i][y_i].m_o_boundary_point[0] , g_node_vector[g_link_vector[l].to_node_seq_no].pt);
						


						double distance = (distance_from + distance_to + distance_from_p2p + distance_to_p2p) / 4;
						
						int i_trace = 0;

		/*				if (g_link_vector[l].from_node_id == 7280 && g_link_vector[l].to_node_id)
						{
							i_trace = 1;
						}


						if (g_link_vector[l].from_node_id == 727 && g_link_vector[l].to_node_id == 5724)
						{
							i_trace = 1;
						}*/

						if (distance < min_distance_to_boundary_point)
						{

							min_distance_to_boundary_point = distance;
							origin_node_no = g_link_vector[l].from_node_seq_no;
							g_agent_vector[agent_no].matching_link_no = l;

						}
					}
				}

				if (m_GridMatrix[x_i][y_i].destination_cell_flag == 1)  // find destination_node_no
				{
					double min_distance_to_boundary_point = _MAX_LABEL_COST;
					for (int local_l = 0; local_l < m_GridMatrix[x_i][y_i].m_LinkNoVector.size(); local_l++)  // for all links in this cell
					{
						int l = m_GridMatrix[x_i][y_i].m_LinkNoVector[local_l];

						double distance_from = g_GetPoint2LineDistance(m_GridMatrix[x_i][y_i].m_d_boundary_point[0],
							g_node_vector[g_link_vector[l].from_node_seq_no].pt, g_node_vector[g_link_vector[l].to_node_seq_no].pt,
							1, true);
						double distance_to = g_GetPoint2LineDistance(m_GridMatrix[x_i][y_i].m_d_boundary_point[1],
							g_node_vector[g_link_vector[l].from_node_seq_no].pt, g_node_vector[g_link_vector[l].to_node_seq_no].pt,
							1, true);

						double distance = (distance_from + distance_to ) / 4;
						if (distance < min_distance_to_boundary_point)
						{
							min_distance_to_boundary_point = distance;
							destination_node_no = g_link_vector[l].to_node_seq_no;
						}
					}
				}
			}
	}

	std::vector<int>  m_agent_vector;
	int m_memory_block_no;

	std::vector<int>  m_origin_node_vector; // assigned nodes for computing 
	std::vector<int>  m_origin_zone_seq_no_vector;

	int  tau; // assigned nodes for computing 
	int  m_agent_type_no; // assigned nodes for computing 
	float m_value_of_time;


	int m_threadNo;  // internal thread number 

	int m_ListFront; // used in coding SEL
	int m_ListTail;  // used in coding SEL

	int* m_SENodeList; // used in coding SEL

	float* m_node_label_cost;  // label cost // for shortest path calcuating
	float* m_label_time_array;  // time-based cost
	float* m_label_distance_array;  // distance-based cost

	int* m_node_predecessor;  // predecessor for nodes
	int* m_node_status_array; // update status 
	int* m_link_predecessor;  // predecessor for this node points to the previous link that updates its label cost (as part of optimality condition) (for easy referencing)

	float* m_link_flow_volume_array;

	float* m_link_generalised_cost_array;

	int* temp_path_node_vector;
	// major function 1:  allocate memory and initialize the data 
	void AllocateMemory(int number_of_nodes, int number_of_links)
	{

		m_SENodeList = new int[number_of_nodes];  //1


		m_node_status_array = new int[number_of_nodes];  //2
		m_label_time_array = new float[number_of_nodes];  //3
		m_label_distance_array = new float[number_of_nodes];  //4
		m_node_predecessor = new int[number_of_nodes];  //5
		m_link_predecessor = new int[number_of_nodes];  //6
		m_node_label_cost = new float[number_of_nodes];  //7

		m_link_flow_volume_array = new float[number_of_links];  //8

		m_link_generalised_cost_array = new float[number_of_links];  //9
		temp_path_node_vector = new int[number_of_nodes];
	}

	~NetworkForSP()
	{

		if (m_SENodeList != NULL)  //1
			delete m_SENodeList;

		if (m_node_status_array != NULL)  //2
			delete m_node_status_array;

		if (m_label_time_array != NULL)  //3
			delete m_label_time_array;

		if (m_label_distance_array != NULL)  //4
			delete m_label_distance_array;

		if (m_node_predecessor != NULL)  //5
			delete m_node_predecessor;

		if (m_link_predecessor != NULL)  //6
			delete m_link_predecessor;

		if (m_node_label_cost != NULL)  //7
			delete m_node_label_cost;


		if (m_link_flow_volume_array != NULL)  //8
			delete m_link_flow_volume_array;


		if (m_link_generalised_cost_array != NULL) //9
			delete m_link_generalised_cost_array;

		if (temp_path_node_vector != NULL) //9
			delete temp_path_node_vector;
		

		if (m_GridMatrix)
			Deallocate2DDynamicArray<GridNodeSet>(m_GridMatrix, _MAX_GRID_SIZE);


	}




	





	// SEList: scan eligible List implementation: the reason for not using STL-like template is to avoid overhead associated pointer allocation/deallocation
	inline void SEList_clear()
	{
		m_ListFront = -1;
		m_ListTail = -1;
	}

	inline void SEList_push_front(int node)
	{
		if (m_ListFront == -1)  // start from empty
		{
			m_SENodeList[node] = -1;
			m_ListFront = node;
			m_ListTail = node;
		}
		else
		{
			m_SENodeList[node] = m_ListFront;
			m_ListFront = node;
		}
	}
	inline void SEList_push_back(int node)
	{
		if (m_ListFront == -1)  // start from empty
		{
			m_ListFront = node;
			m_ListTail = node;
			m_SENodeList[node] = -1;
		}
		else
		{
			m_SENodeList[m_ListTail] = node;
			m_SENodeList[node] = -1;
			m_ListTail = node;
		}
	}

	inline bool SEList_empty()
	{
		return(m_ListFront == -1);
	}



	//major function: update the cost for each node at each SP tree, using a stack from the origin structure 

	int origin_node_no;
	int destination_node_no;

	//major function 2: // abel correcting algorithm with double queue implementation
	float optimal_label_correcting(int agent_no)
	{
		origin_node_no = -1;
		destination_node_no = -1;
		
		AddGPSPointsIntoGridSystem(agent_no); //find the origin and destination nodes 

		int number_of_nodes = g_node_vector.size();
		int i;
		for (i = 0; i < number_of_nodes; i++) //Initialization for all non-origin nodes
		{
			m_node_status_array[i] = 0;  // not scanned
			m_node_label_cost[i] = _MAX_LABEL_COST;
			m_link_predecessor[i] = -1;  // pointer to previous NODE INDEX from the current label at current node and time
			m_node_predecessor[i] = -1;  // pointer to previous NODE INDEX from the current label at current node and time
			// comment out to speed up comuting 
			////m_label_time_array[i] = 0;
			////m_label_distance_array[i] = 0;
		}


		int internal_debug_flag = 0;
		if (origin_node_no == -1 || destination_node_no == -1)
		{
			return 0;
		}

		cout << "origin_node_no =" << g_node_vector[origin_node_no].node_id << "; " << "destination_node_no =" << g_node_vector[destination_node_no].node_id << endl;

		//Initialization for origin node at the preferred departure time, at departure time, cost = 0, otherwise, the delay at origin node
		m_label_time_array[origin_node_no] = 0;
		m_node_label_cost[origin_node_no] = 0.0;
		//Mark:	m_label_distance_array[origin_node_no] = 0.0;

		m_link_predecessor[origin_node_no] = -1;  // pointer to previous NODE INDEX from the current label at current node and time
		m_node_predecessor[origin_node_no] = -1;  // pointer to previous NODE INDEX from the current label at current node and time

		SEList_clear();
		SEList_push_back(origin_node_no);


		int from_node, to_node;
		int link_sqe_no;
		float new_time = 0;
		float new_distance = 0;
		float new_to_node_cost = 0;
		int tempFront;
		while (!(m_ListFront == -1))   //SEList_empty()
		{
			//          from_node = SEList_front(); 
			//			SEList_pop_front();  // remove current node FromID from the SE list

			from_node = m_ListFront;//pop a node FromID for scanning
			tempFront = m_ListFront;
			m_ListFront = m_SENodeList[m_ListFront];
			m_SENodeList[tempFront] = -1;

			m_node_status_array[from_node] = 2;

			int pred_link_seq_no = m_link_predecessor[from_node];

			for (i = 0; i < g_node_vector[from_node].m_outgoing_link_seq_no_vector.size(); i++)  // for each link (i,j) belong A(i)
			{


				link_sqe_no = g_node_vector[from_node].m_outgoing_link_seq_no_vector[i];
				to_node = g_link_vector[link_sqe_no].to_node_seq_no;


				//remark: the more complicated implementation can be found in paper Shortest Path Algorithms In Transportation Models: Classical and Innovative Aspects
				//	A note on least time path computation considering delays and prohibitions for intersection movements
				//very important: only origin zone can access the outbound connectors, 
				//the other zones do not have access to the outbound connectors

				new_to_node_cost = m_node_label_cost[from_node] + m_link_generalised_cost_array[link_sqe_no];  // m_link_generalised_cost_array is the likelihood cost determined externally by the GPS points to link distance 

				if (new_to_node_cost < m_node_label_cost[to_node]) // we only compare cost at the downstream node ToID at the new arrival time t
				{

					m_node_label_cost[to_node] = new_to_node_cost;
					m_node_predecessor[to_node] = from_node;  // pointer to previous physical NODE INDEX from the current label at current node and time
					m_link_predecessor[to_node] = link_sqe_no;  // pointer to previous physical NODE INDEX from the current label at current node and time

					// deque updating rule for m_node_status_array
					if (m_node_status_array[to_node] == 0)
					{
						///// SEList_push_back(to_node);
						///// begin of inline block
						if (m_ListFront == -1)  // start from empty
						{
							m_ListFront = to_node;
							m_ListTail = to_node;
							m_SENodeList[to_node] = -1;
						}
						else
						{
							m_SENodeList[m_ListTail] = to_node;
							m_SENodeList[to_node] = -1;
							m_ListTail = to_node;
						}
						///// end of inline block

						m_node_status_array[to_node] = 1;
					}
					if (m_node_status_array[to_node] == 2)
					{
						/////SEList_push_front(to_node);
						///// begin of inline block
						if (m_ListFront == -1)  // start from empty
						{
							m_SENodeList[to_node] = -1;
							m_ListFront = to_node;
							m_ListTail = to_node;
						}
						else
						{
							m_SENodeList[to_node] = m_ListFront;
							m_ListFront = to_node;
						}
						///// end of inline block

						m_node_status_array[to_node] = 1;
					}

				}

			}

		}

		return m_node_label_cost[destination_node_no];
	}

	void find_path_for_agents_assigned_for_this_thread()
	{
		int return_value;

		for (int i = 0; i < m_agent_vector.size(); i++)
		{
			CAgent* p_agent = &(g_agent_vector[m_agent_vector[i]]);

			cout << "agent_id =" << p_agent->agent_id.c_str() << endl;

			return_value = optimal_label_correcting(p_agent->agent_no);
			if (return_value == -1)
			{
				continue;
			}
			// step 2: backtrack to the origin (based on node and time predecessors)
			int current_node_seq_no = destination_node_no;  // destination node
			int current_link_seq_no = -1;

			int l_node_size = 0;
			// backtrace the shortest path tree from the destination to the root (at origin) 
			while (current_node_seq_no >= 0 && current_node_seq_no < g_number_of_nodes)
			{

				temp_path_node_vector[l_node_size++] = current_node_seq_no;

				if (l_node_size >= 10000)
				{
					cout << "Error: l_node_size >= temp_path_node_vector_size" << endl;
					g_Program_stop();
				}

				current_node_seq_no = m_node_predecessor[current_node_seq_no];  // update node seq no	
			}

			p_agent->AllocatePathNodeVector(l_node_size, temp_path_node_vector);
			if(origin_node_no>=0 && destination_node_no>=0)  //feasible origin and destination nodes
			{
			p_agent->o_node_id = g_node_vector[origin_node_no].node_id;

			p_agent->d_node_id = g_node_vector[destination_node_no].node_id;
			}

		}


	}

};



void g_Program_stop()
{

	cout << "Program stops. Press any key to terminate. Thanks!" << endl;
	getchar();
	exit(0);
};


int timestr2second(string time_str)
{
	//string hh = time_str.substr(0, 2);
	//string mm = time_str.substr(2, 2);
	//string ss = time_str.substr(5, 2);
	//int hhi = stoi(hh);
	//int mmi = stoi(mm);
	//int ssi = stoi(ss);
	//return hhi * 3600 + mmi * 60 + ssi;
	return 0;
}


string second2timestr(int time_int)
{
	int hhi = time_int / 3600;
	int mmi = (time_int - 3600 * hhi) / 60;
	int ssi = time_int - 3600 * hhi - 60 * mmi;
	string hh = hhi < 10 ? "0" + to_string(hhi) : to_string(hhi);
	string mm = mmi < 10 ? "0" + to_string(mmi) : to_string(mmi);
	string ss = ssi < 10 ? "0" + to_string(ssi) : to_string(ssi);
	return hh + mm + ":" + ss;
}





void g_ReadInputData()
{
	CCSVParser parser;
	if (parser.OpenCSVFile("node.csv", true))
	{
		int node_id;

		while (parser.ReadRecord())  // if this line contains [] mark, then we will also read field headers.
		{
			if (parser.GetValueByFieldName("node_id", node_id) == false)
				continue;

			if (g_internal_node_seq_no_map.find(node_id) != g_internal_node_seq_no_map.end())
			{
				cout << "warning: duplicate definition of node " << node_id << " was detected\n";
				continue;
			}

			CNode node;
			node.node_id = node_id;
			node.node_seq_no = g_number_of_nodes++;
			parser.GetValueByFieldName("x_coord", node.pt.x, false);
			parser.GetValueByFieldName("y_coord", node.pt.y, false);

			g_node_vector.push_back(node);
			g_internal_node_seq_no_map[node_id] = node.node_seq_no;
			if (g_number_of_nodes % 1000 == 0)
				cout << "reading " << g_number_of_nodes << " nodes.. " << endl;
		}

		cout << "number of nodes = " << g_number_of_nodes << endl;
		parser.CloseCSVFile();
	}
	else
	{
		cout << "Cannot open file node.csv" << endl;
		g_Program_stop();
	}


	CCSVParser parser_link;
	if (parser_link.OpenCSVFile("link.csv", true))
	{
		while (parser_link.ReadRecord())
		{
			CLink link;

			if (parser_link.GetValueByFieldName("link_id", link.link_id) == false)
				continue;
			if (parser_link.GetValueByFieldName("from_node_id", link.from_node_id) == false)
				continue;
			if (parser_link.GetValueByFieldName("to_node_id", link.to_node_id) == false)
				continue;

			int allowed_uses = 0;
			parser_link.GetValueByFieldName("allowed_uses", allowed_uses, false);

				if (allowed_uses != 1)
					continue;


			if (g_internal_node_seq_no_map.find(link.from_node_id) == g_internal_node_seq_no_map.end())
			{
				cout << "warning: from_node_id " << link.from_node_id << " of link " << link.link_id << " has not been defined in node.csv\n";
				continue;
			}
			if (g_internal_node_seq_no_map.find(link.to_node_id) == g_internal_node_seq_no_map.end())
			{
				cout << "warning: to_node_id " << link.to_node_id << " of link " << link.link_id << " has not been defined in node.csv\n";
				continue;
			}

			link.from_node_seq_no = g_internal_node_seq_no_map[link.from_node_id];
			link.to_node_seq_no = g_internal_node_seq_no_map[link.to_node_id];
			link.link_seq_no = g_number_of_links++;

			g_internal_link_no_map[link.link_id] = link.link_seq_no;
			g_node_vector[link.from_node_seq_no].m_outgoing_link_seq_no_vector.push_back(link.link_seq_no);
			g_link_vector.push_back(link);

			if (g_number_of_links % 1000 == 0)
				cout << "reading " << g_number_of_links << " links.. " << endl;
		}

		cout << "number of links = " << g_number_of_links << endl;
		parser_link.CloseCSVFile();
	}
	else
	{
		cout << "Cannot open file link.csv" << endl;
		g_Program_stop();
	}

	CCSVParser gps_parser;
	int gps_point_count = 0;
	if (gps_parser.OpenCSVFile("trace.csv", true))
	{
		double x, y;
		string time_stamp;
		int time_in_second;
		while (gps_parser.ReadRecord())
		{
			string agent_id;
			if (gps_parser.GetValueByFieldName("agent_id", agent_id) == false)
				continue;

			if (g_internal_agent_no_map.find(agent_id) == g_internal_agent_no_map.end())
			{

				g_internal_agent_no_map[agent_id] = g_internal_agent_no_map.size();  // assign the internal agent no as the current size of the map.
				CAgent agent;
				agent.agent_id = agent_id;
				agent.agent_no = g_agent_vector.size();
				g_agent_vector.push_back(agent);
			}

			gps_parser.GetValueByFieldName("x_coord", x, false);
			gps_parser.GetValueByFieldName("y_coord", y, false);
			gps_parser.GetValueByFieldName("timestamp", time_stamp);
			time_in_second = timestr2second(time_stamp);

			CGPSPoint GPSPoint;
			GPSPoint.pt.x = x;
			GPSPoint.pt.y = y;
			GPSPoint.time_str = time_stamp;
			GPSPoint.time_in_second = time_in_second;
			g_agent_vector[g_internal_agent_no_map[agent_id]].m_GPSPointVector.push_back(GPSPoint);
			gps_point_count++;
		}

		cout << "number of agents = " << g_agent_vector.size() << endl;
		cout << "number of GPS points = " << gps_point_count << endl;

		gps_parser.CloseCSVFile();

	}
	else
	{
		cout << "Cannot open file trace.csv" << endl;
		g_Program_stop();
	}


}

int g_number_of_CPU_threads()
{
	int number_of_threads = omp_get_max_threads();
	if (number_of_threads <= g_max_number_of_threads)
		return number_of_threads;
	else
		return g_max_number_of_threads;
}



NetworkForSP* g_pNetworkVector = NULL;
#pragma warning(disable : 4996)

void g_OutputAgentCSVFile()
{
	FILE* g_pFileAgent = NULL;
	g_pFileAgent = fopen("agent.csv", "w");

	if (g_pFileAgent == NULL)
	{
		cout << "File agent.csv cannot be opened." << endl;
		g_Program_stop();
	}
	else
	{
		fprintf(g_pFileAgent, "agent_id,o_node_id,d_node_id,o_zone_id,d_zone_id,matching_link_from_node_id,matching_link_to_node_id,matching_link_id,node_sequence,geometry,time_sequence\n");

		for (int a = 0; a < g_agent_vector.size(); a++)
		{
			CAgent* p_agent = &(g_agent_vector[a]);
			int matching_link_from_node_id = -1;
			int matching_link_to_node_id = -1;
			int matching_link_id = -1;

			if (p_agent->matching_link_no >= 0)
			{
				matching_link_from_node_id = g_link_vector[p_agent->matching_link_no].from_node_id;
				matching_link_to_node_id = g_link_vector[p_agent->matching_link_no].to_node_id;
				matching_link_id = g_link_vector[p_agent->matching_link_no].link_id;
			}

			fprintf(g_pFileAgent, "%s,%d,%d,%d,%d,%d,%d,%d,",
				p_agent->agent_id.c_str(),
				p_agent->o_node_id,
				p_agent->d_node_id,
				p_agent->origin_zone_id,
				p_agent->destination_zone_id,
				matching_link_from_node_id,
				matching_link_to_node_id,
				matching_link_id

			);

			for (int i = 0; i < p_agent->m_node_size; i++)
			{
				fprintf(g_pFileAgent, "%d;", g_node_vector[p_agent->path_node_vector[i]].node_id);
			}

			fprintf(g_pFileAgent, ",");

			fprintf(g_pFileAgent, "\"LINESTRING (");

			if (p_agent->m_node_size > 1)
			{
			
				for (int i = 0; i < p_agent->m_node_size; i++)
				{
					fprintf(g_pFileAgent, "%f %f,", g_node_vector[p_agent->path_node_vector[i]].pt.x, g_node_vector[p_agent->path_node_vector[i]].pt.y);
				}
			}
			else 
			{
				if (p_agent->matching_link_no >= 0)
				{
					fprintf(g_pFileAgent, "%f %f,", g_node_vector[g_link_vector[p_agent->matching_link_no].from_node_seq_no].pt.x,
						g_node_vector[g_link_vector[p_agent->matching_link_no].from_node_seq_no].pt.y);

					fprintf(g_pFileAgent, "%f %f", g_node_vector[g_link_vector[p_agent->matching_link_no].to_node_seq_no].pt.x,
						g_node_vector[g_link_vector[p_agent->matching_link_no].to_node_seq_no].pt.y);

				}
			}


			fprintf(g_pFileAgent, ")\"");

			fprintf(g_pFileAgent, "\n");
		}

		fclose(g_pFileAgent);
	}
}

bool g_LikelyRouteFinding()
{
	int number_of_threads = g_number_of_CPU_threads();
	number_of_threads = 1;
	g_pNetworkVector = new NetworkForSP[number_of_threads]; // create n copies of network, each for a subset of agents to use 

	cout << "number of CPU threads = " << number_of_threads << endl;

	NetworkForSP* p_Network;

	for (int i = 0; i < number_of_threads; i++)
	{
		g_pNetworkVector[i].AllocateMemory(g_number_of_nodes, g_number_of_links);
		g_pNetworkVector[i].BuildGridSystem();  // called once
	}

	for (int a = 0; a < g_agent_vector.size(); a++)  // 
	{

		p_Network = &g_pNetworkVector[a % number_of_threads];

		p_Network->m_agent_vector.push_back(a);
	}



#pragma omp parallel for
	for (int thread_no = 0; thread_no < number_of_threads; thread_no++)
	{
		g_pNetworkVector[thread_no].find_path_for_agents_assigned_for_this_thread();
	}

	g_OutputAgentCSVFile();

	cout << "End of Sequential Optimization Process. " << endl;

	return true;
}


int main(int argc, TCHAR* argv[], TCHAR* envp[])
{
	clock_t start_t, end_t, total_t;

	start_t = clock();
	g_ReadInputData();
	g_LikelyRouteFinding();

	end_t = clock();
	total_t = (end_t - start_t);
	cout << "CPU Running Time = " << total_t / 1000.0f << " seconds" << endl;
	cout << "free memory.." << endl;
	cout << "done." << endl;

	g_node_vector.clear();
	g_link_vector.clear();
	g_agent_vector.clear();

	return 1;
}