// trace2route.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

//Your code uses a function, class member, variable, or typedef that's marked deprecated. Symbols are deprecated by using a __declspec(deprecated) modifier, or the C++14 [[deprecated]] attribute. The actual C4996 warning message is specified
//by the deprecated modifier or attribute of the declaration.
//#include "MapMatching4GMNS.h"
#pragma warning(disable : 4996)

#include "stdafx.h"
//#ifdef _WIN32
//#include "pch.h"
//#endif

#include <algorithm>
#include <fstream>
#include <iostream>
#include <list>
//#include <omp.h>
//#include <time.h>
#include "CSVParser.h"
#include <ctime>
//#include <math.h>
#include <cmath>

using namespace std;

#define MAX_LABEL_COST_ 999999
#define MAX_GRID_SIZE_ 100
#define PI_ 3.1415

int g_max_number_of_threads = 4;
int g_number_of_nodes = 0;
int g_number_of_links = 0;
int g_number_of_agents = 0;
int g_grid_size = 1;

/*
constexpr auto g_max_number_of_threads = 4;
constexpr auto g_number_of_nodes = 0;
constexpr auto g_number_of_links = 0;
constexpr auto g_number_of_agents = 0;
constexpr auto g_grid_size = 1;
*/
using std::max;
using std::min;
//std::map<int, int> g_internal_node_seq_no_map;
//std::map<int, int> g_internal_link_no_map;
//std::map<string, int> g_internal_agent_no_map;

map<int, int> g_internal_node_seq_no_map;
map<int, int> g_internal_link_no_map;
map<string, int> g_internal_agent_no_map;

extern void g_Program_stop();
extern void g_OutputInputAgentCSVFile();

void g_Program_stop()
{

  cout << "Program stops. Press any key to terminate. Thanks!" << endl;
  getchar();
  exit(0);
};

struct GDPoint //geometry data
{
  double x;
  double y;
};

typedef struct
{
  double X, Y, Z;
} CCoordinate;

class CGeometry
{
public:
  enum GeometryType
  {
    POINT,
    LINE,
    POLYGON,
    UNKNOWN
  };

private:
  GeometryType m_Type;
  int m_NumOfCoordinates;
  std::vector<CCoordinate> v_Coordinates;
  bool ReadPointCoordinate(string s);
  bool ReadLineStringCoordinates(string s);
  bool ReadPolygonCoordinates(string s);

public:
  CGeometry(string s);
  //~CGeometry(void);
  ~CGeometry();

  //GeometryType GetGeometryType(void);
  //std::vector<CCoordinate> GetCoordinateList(void);
  //int GetNumberOfCoordinates(void);
  GeometryType GetGeometryType();
  std::vector<CCoordinate> GetCoordinateList();
  int GetNumberOfCoordinates();
};

CGeometry::CGeometry(string s)
{
  m_NumOfCoordinates = 0;

  string tmp;
  if (s.find("POINT") != std::string::npos)
  {
    tmp = s.substr(s.find_first_not_of(' '));
    size_t start_idx = tmp.find_first_of('(');
    size_t end_idx = tmp.find_first_of(')');

    if (start_idx == std::string::npos || end_idx == std::string::npos)
      return;

    string type_str = tmp.substr(0, start_idx);
    type_str.erase(type_str.find_last_not_of(" ") + 1); // works for 'LINESTRING (....' and 'LINESTRING(....'

    string start_tag = "(";
    string end_tag = ")";

    start_idx = tmp.find(start_tag);
    start_idx += start_tag.length();
    end_idx = tmp.find(end_tag);

    tmp = tmp.substr(start_idx, end_idx - start_idx);

    m_Type = POINT;
  }
  else if (s.find("LINESTRING") != std::string::npos)
  {
    tmp = s.substr(s.find_first_not_of(' '));
    size_t start_idx = tmp.find_first_of('(');
    size_t end_idx = tmp.find_first_of(')');

    if (start_idx == std::string::npos || end_idx == std::string::npos)
      return;

    string type_str = tmp.substr(0, start_idx);
    type_str.erase(type_str.find_last_not_of(" ") + 1); // works for 'LINESTRING (....' and 'LINESTRING(....'

    string start_tag = "(";
    string end_tag = ")";

    start_idx = tmp.find(start_tag);
    start_idx += start_tag.length();
    end_idx = tmp.find(end_tag);

    tmp = tmp.substr(start_idx, end_idx - start_idx);

    m_Type = LINE;
  }
  else if (s.find("POLYGON") != std::string::npos)
  {
    tmp = s.substr(s.find_first_not_of(' '));
    size_t start_idx = tmp.find('((');
    size_t end_idx = tmp.find('))');

    if (start_idx == std::string::npos || end_idx == std::string::npos)
      return;

    string type_str = tmp.substr(0, start_idx);
    type_str.erase(type_str.find_last_not_of(" ") + 1); // works for 'LINESTRING (....' and 'LINESTRING(....'

    string start_tag = "((";
    string end_tag = "))";

    start_idx = tmp.find(start_tag);
    start_idx += start_tag.length();
    end_idx = tmp.find(end_tag);

    tmp = tmp.substr(start_idx, end_idx - start_idx);

    m_Type = POLYGON;
  }
  else
  {
    m_Type = UNKNOWN;
  }

  switch (m_Type)
  {
  case POINT:
    ReadPointCoordinate(tmp);
    break;
  case LINE:
    ReadLineStringCoordinates(tmp);
    break;
  case POLYGON:
    ReadPolygonCoordinates(tmp);
    break;
  default:
    break;
  }
}

CGeometry::~CGeometry(void)
{
}

CGeometry::GeometryType CGeometry::GetGeometryType(void)
{
  return m_Type;
}

int CGeometry::GetNumberOfCoordinates(void)
{
  return m_NumOfCoordinates;
}

std::vector<CCoordinate> CGeometry::GetCoordinateList(void)
{
  return v_Coordinates;
}

bool CGeometry::ReadLineStringCoordinates(string s)
{
  istringstream ss(s);
  string sub_str;

  if (std::string::npos == s.find_first_of("0123456789"))
  {
    // "digit not found!, empty string//
    return false;
  }

  while (std::getline(ss, sub_str, ','))
  {
    sub_str = sub_str.substr(sub_str.find_first_not_of(' '));

    CCoordinate coordinate;
    istringstream sub_ss(sub_str);
    string tmp;

    std::getline(sub_ss, tmp, ' ');
    istringstream x_ss(tmp);
    x_ss >> coordinate.X;

    std::getline(sub_ss, tmp, ' ');
    istringstream y_ss(tmp);
    y_ss >> coordinate.Y;

    v_Coordinates.push_back(coordinate);
    m_NumOfCoordinates += 1;
  }
  return true;
}

bool CGeometry::ReadPolygonCoordinates(string s)
{
  istringstream ss(s);
  string sub_str;
  if (std::string::npos == s.find_first_of("0123456789"))
  {
    // "digit not found!, empty string//
    return false;
  }

  while (std::getline(ss, sub_str, ','))
  {
    sub_str = sub_str.substr(sub_str.find_first_not_of(' '));

    CCoordinate coordinate;
    istringstream sub_ss(sub_str);
    string tmp;

    std::getline(sub_ss, tmp, ' ');
    istringstream x_ss(tmp);
    x_ss >> coordinate.X;

    std::getline(sub_ss, tmp, ' ');
    istringstream y_ss(tmp);
    y_ss >> coordinate.Y;

    v_Coordinates.push_back(coordinate);
    m_NumOfCoordinates += 1;
  }
  return true;
}
bool CGeometry::ReadPointCoordinate(string s)
{
  CCoordinate coordinate;
  istringstream ss(s);

  string sub_str;
  std::getline(ss, sub_str, ' ');
  istringstream x_ss(sub_str);

  std::getline(ss, sub_str, ' ');
  istringstream y_ss(sub_str);
  x_ss >> coordinate.X;
  y_ss >> coordinate.Y;
  coordinate.Z = 0.0;

  v_Coordinates.push_back(coordinate);
  m_NumOfCoordinates = 1;

  return true;
}

int g_ParserIntSequence(std::string str, std::vector<int>& vect)
{

  std::stringstream ss(str);

  int i;

  while (ss >> i)
  {
    vect.push_back(i);

    if (ss.peek() == ';')
      ss.ignore();
  }

  return vect.size();
}

class CNode
{
public:
  int node_seq_no; // sequence number
  int node_id;     //external node number
  string name;
  std::vector<int> m_outgoing_link_seq_no_vector;

  std::map<int, int> m_outgoing_link_seq_no_map;
  GDPoint pt;
};

class CLink
{
public:
  CLink()
  {
    length = 1;
    FFTT_in_sec = 0;
    free_speed;
    x_key = 0;
    y_key = 0;
  }

  int link_id;
  string name;
  string geometry;

  std::vector<GDPoint> m_PointVector;

  int from_node_id;
  int to_node_id;
  double length;
  double free_speed;
  double FFTT_in_sec;
  int x_key;
  int y_key;

  int link_seq_no;
  int from_node_seq_no;
  int to_node_seq_no;
  double distance;
};

std::vector<CNode> g_node_vector;
std::vector<CLink> g_link_vector;

double g_GetPoint2Point_Distance(const GDPoint* p1, const GDPoint* p2)
{
  return pow(((p1->x - p2->x) * (p1->x - p2->x) + (p1->y - p2->y) * (p1->y - p2->y)), 0.5);
}

double g_GetPoint2LineDistance(const GDPoint* pt, const GDPoint* FromPt, const GDPoint* ToPt, double UnitMile, bool no_intersection_requirement)
{
  double U;
  GDPoint Intersection;

  double LineLength = g_GetPoint2Point_Distance(FromPt, ToPt);

  U = ((pt->x - ToPt->x) * (FromPt->x - ToPt->x) + (pt->y - ToPt->y) * (FromPt->y - ToPt->y)) / (LineLength * LineLength);

  if (no_intersection_requirement == false)
  {

    if (U < 0.0 || U > 1.0)
      return max(UnitMile * 100, 999999); // intersection does not fall within the segment
  }
  Intersection.x = ToPt->x + U * (FromPt->x - ToPt->x);
  Intersection.y = ToPt->y + U * (FromPt->y - ToPt->y);

  double distance_1 = g_GetPoint2Point_Distance(pt, &Intersection);
  double distance_0 = g_GetPoint2Point_Distance(pt, FromPt);
  double distance_2 = g_GetPoint2Point_Distance(pt, ToPt);

  if (no_intersection_requirement)
  {
    return min(min(distance_1, distance_0), distance_2) / max(0.000001, UnitMile);
  }
  else
    return distance_1 / max(0.000001, UnitMile);
}

double g_Find_P2P_Angle(const GDPoint* p1, const GDPoint* p2)
{
  double delta_x = p2->x - p1->x;
  double delta_y = p2->y - p1->y;

  if (fabs(delta_x) < 0.00001)
    delta_x = 0;

  if (fabs(delta_y) < 0.00001)
    delta_y = 0;

  int angle = atan2(delta_y, delta_x) * 180 / PI_ + 0.5;
  // angle = 90 - angle;

  while (angle < 0)
    angle += 360;

  while (angle > 360)
    angle -= 360;

  return angle;
}
double g_Find_PPP_RelativeAngle(const GDPoint* p1, const GDPoint* p2, const GDPoint* p3, const GDPoint* p4)
{
  int relative_angle;

  int angle1 = g_Find_P2P_Angle(p1, p2);
  int angle2 = g_Find_P2P_Angle(p3, p4);
  relative_angle = angle2 - angle1;

  while (relative_angle > 180)
    relative_angle -= 360;

  while (relative_angle < -180)
    relative_angle += 360;

  return relative_angle;
}
//ill conditioning detection
bool g_ill_conditioning_detection(double link_distance, double GPS_segment_distance)
{
  double cutoff_ratio = 3;
  double ratio = link_distance / max(0.00000001, GPS_segment_distance);
  if ((1.0 / cutoff_ratio) < ratio && ratio < cutoff_ratio)
    return false; //this indicates: good_conditioning, so ill_conditioning = false
  else
    return true;
}

class CGPSPoint
{
public:
  CGPSPoint()
  {
    bInsideGrid = false;
    Inside_index = -1;
    trace_id = -1;
  }

public:
  GDPoint pt;
  int trace_id;
  //double time_interval_no;
  int time_in_second;
  bool bInsideGrid;
  int Inside_index;
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
  GDPoint m_o_boundary_point[2]; // from point and to point
  GDPoint m_d_boundary_point[2];
};
class CAgent
{
public:
  CAgent()
  {
    matching_link_no = -1;
    avg_GPS_segment_distance = 0;
    first_segment_distance = 0;
    last_segment_distance = 0;

    head_gps_index = -1;
    tail_gps_index = -1;

    path_node_vector = NULL;
    path_link_vector = NULL;
    path_node_matched_time_in_sec = NULL;
    path_link_matched_trace_id = NULL;

  }

  ~CAgent()
  {
      if (path_node_vector != NULL)
      {
          delete path_node_vector;
      }
          
      if (path_link_vector != NULL)
      {
          delete path_link_vector;
      }

      if (path_node_matched_time_in_sec != NULL)
      {
          delete path_node_matched_time_in_sec;
      }

      if (path_link_matched_trace_id != NULL)
      {
          delete path_link_matched_trace_id;
      }

  }


  int head_gps_index;
  int tail_gps_index;

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

  double avg_GPS_segment_distance;
  double first_segment_distance;
  double last_segment_distance;

  int upstream_node_matched_time_in_sec;

  int m_node_size;
  int* path_node_vector; // final node sequqence for the path
  int* path_link_vector; // final link sequqence for the path
  int* path_node_matched_time_in_sec; // for each link
  int* path_link_matched_trace_id;    // for each link
  /*
  void AllocatePathNodeVector(int node_size, int* node_vector)  //store the data into the path node sequence
  {
    m_node_size = node_size;
    path_node_vector = new int[node_size];  // dynamic array

    for (int i = 0; i < m_node_size; i++)  // copy backward from the result of shortest path tree
    {
      path_node_vector[i] = node_vector[m_node_size - 1 - i];
    }
  }
  */
  // Reference the Dr.Peiheng, 02/02/21, consider using move later
  //A good example to apply the move semantics is AllocateVector() in main_api.cpp in DTALite.
  void AllocatePathNodeVector(int node_size, const int* node_vector, bool backwardflag = false)
  {
    m_node_size = node_size;
    path_node_vector = new int[m_node_size]; // dynamic array
    path_link_vector = new int[m_node_size]; // dynamic array
    
    path_node_matched_time_in_sec = new int[m_node_size]; // dynamic array
    path_link_matched_trace_id = new int[m_node_size]; // dynamic array

    if (backwardflag)
    {
      //copy backward
      for (int i = 0; i < m_node_size; ++i)
      {
        path_node_vector[i] = node_vector[m_node_size - 1 - i];
      }
    }
    else
    { // copy forward
      for (int i = 0; i < m_node_size; ++i)
      {
        path_node_vector[i] = node_vector[i];
      }
    }
  }
};
vector<CAgent> g_agent_vector;

class NetworkForSP // mainly for shortest path calculation
{
public:
  NetworkForSP()
  {
  }

  GridNodeSet** m_GridMatrix; //important data structure for creating grid matrix
  double m_left;              // boundary of grid matrix
  double m_right;
  double m_top;
  double m_bottom;

  double m_GridXStep; // x resolution of grid cell
  double m_GridYStep;

  void BuildGridSystem()
  {

    m_GridMatrix = Allocate2DDynamicArray<GridNodeSet>(MAX_GRID_SIZE_, MAX_GRID_SIZE_);
    g_grid_size = max(1, min(MAX_GRID_SIZE_, g_node_vector.size() / 3000)); // dynamically determine the size of grid. e.g. for a testing network <100 nodes, use a grid size of 1.
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
    m_GridYStep = max(0.0001, (m_top - m_bottom) / g_grid_size); // both x and y resolutions are the same

    // put nodes into grid cell

    for (int i = 0; i < g_node_vector.size(); i++)
    {
      int x_key = (g_node_vector[i].pt.x - m_left) / m_GridXStep; // x_key internal x horizonal index of grid
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
      int x_key = (g_node_vector[g_link_vector[l].from_node_seq_no].pt.x - m_left) / m_GridXStep; // from node
      int y_key = (g_node_vector[g_link_vector[l].from_node_seq_no].pt.y - m_bottom) / m_GridYStep;

      //feasible region
      x_key = max(0, x_key);
      x_key = min(g_grid_size - 1, x_key);

      y_key = max(0, y_key);
      y_key = min(g_grid_size - 1, y_key);

      m_GridMatrix[x_key][y_key].m_LinkNoVector.push_back(l);

      int from_x_key = x_key;
      int from_y_key = y_key;

      x_key = (g_node_vector[g_link_vector[l].to_node_seq_no].pt.x - m_left) / m_GridXStep; //to node
      y_key = (g_node_vector[g_link_vector[l].to_node_seq_no].pt.y - m_bottom) / m_GridYStep;

      //feasible region
      x_key = max(0, x_key);
      x_key = min(g_grid_size - 1, x_key);

      y_key = max(0, y_key);
      y_key = min(g_grid_size - 1, y_key);

      g_link_vector[l].x_key = x_key;
      g_link_vector[l].y_key = y_key;

      if (from_x_key != x_key || from_y_key != y_key) // when the from node and to node of a link belong to  different cells.
      {
        m_GridMatrix[x_key][y_key].m_LinkNoVector.push_back(l);
      }
      /// put this link to the next cells.
    }
  }

  bool bInsideGrid(const GDPoint* pt)
  {
    if (pt->x < m_left || pt->x > m_right || pt->y < m_bottom || pt->y > m_top)
      return false;
    else
      return true;
  }

  void AddGPSPointsIntoGridSystem(int agent_no)
  { // for every agent

    for (int x_i = 0; x_i < g_grid_size; x_i++)
      for (int y_i = 0; y_i < g_grid_size; y_i++)
      {
        m_GridMatrix[x_i][y_i].origin_cell_flag = 0;
        m_GridMatrix[x_i][y_i].destination_cell_flag = 0;
        m_GridMatrix[x_i][y_i].m_GPSPointVector.clear(); //reset the existing GPS point records in this grid
      }

    for (int i = 0; i < g_link_vector.size(); i++) // reset the cost for all links
    {
      m_link_generalised_cost_array[i] = MAX_LABEL_COST_ / 1000; // feasible range
    }
    // put GPS points into grid cell

    // calculate avg distance
    double total_GPS_distance = 0;
    int g;

    if (g_agent_vector[agent_no].m_GPSPointVector.size() >= 2)
    {
      for (g = 0; g < g_agent_vector[agent_no].m_GPSPointVector.size() - 1; g++) // for each GPS point
      {
        double segment_distance;
        segment_distance = g_GetPoint2Point_Distance(&g_agent_vector[agent_no].m_GPSPointVector[g].pt, &g_agent_vector[agent_no].m_GPSPointVector[g + 1].pt);

        total_GPS_distance += segment_distance;
        if (g == 0)
        {
          g_agent_vector[agent_no].first_segment_distance = segment_distance;
        }

        if (g == g_agent_vector[agent_no].m_GPSPointVector.size() - 2)
        {
          g_agent_vector[agent_no].last_segment_distance = segment_distance;
        }
      }
    }

    g_agent_vector[agent_no].avg_GPS_segment_distance = total_GPS_distance / max(1, g_agent_vector[agent_no].m_GPSPointVector.size() - 1);

    // first step, determine the inside flag

    // default settings if all GPS points inside
    g_agent_vector[agent_no].head_gps_index = 0;
    g_agent_vector[agent_no].tail_gps_index = g_agent_vector[agent_no].m_GPSPointVector.size() - 1;

    int g_Inside_index = -1;
    for (g = 0; g < g_agent_vector[agent_no].m_GPSPointVector.size(); g++) // for each GPS point
    {                                                                      // x_key and y_key are relative index of grid

      int x_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.x - m_left) / m_GridXStep;
      int y_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.y - m_bottom) / m_GridYStep;

      //if (g_agent_vector[agent_no].m_GPSPointVector[g].trace_id == 134)
      //{
      //TRACE("x, y = %d,%d\n", x_key, y_key);
      //("");
      //}

      //feasible region
      x_key = max(0, x_key);
      x_key = min(g_grid_size - 1, x_key);

      y_key = max(0, y_key);
      y_key = min(g_grid_size - 1, y_key);

      if (bInsideGrid(&g_agent_vector[agent_no].m_GPSPointVector[g].pt) == true)
      {
        m_GridMatrix[x_key][y_key].m_GPSPointVector.push_back(g_agent_vector[agent_no].m_GPSPointVector[g]);
        g_agent_vector[agent_no].m_GPSPointVector[g].bInsideGrid = true;
        if (g_Inside_index == -1)
        {
          g_Inside_index = 0; // initialize
          g_agent_vector[agent_no].m_GPSPointVector[g].Inside_index = g_Inside_index;
          if (g != 0)
          { // reset the head gps index as the first entrance gps point
            g_agent_vector[agent_no].head_gps_index = g;
          }
        }
        else
        {
          g_Inside_index++;
          g_agent_vector[agent_no].m_GPSPointVector[g].Inside_index = g_Inside_index;
        }
      }
      else
      {                          // outside
        if (g_Inside_index >= 0) // g-1 has been inside
        {
          g_Inside_index = -100;                                                          // g-1 as boundary before outside
          g_agent_vector[agent_no].m_GPSPointVector[g - 1].Inside_index = g_Inside_index; // mark g-1 as boundary where g-1 inside
          g_agent_vector[agent_no].tail_gps_index = g - 1;                                // reset the tail index
        }
      }
    }
    // second step for origin GPS index

    g = g_agent_vector[agent_no].head_gps_index;
    int x_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.x - m_left) / m_GridXStep;
    int y_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.y - m_bottom) / m_GridYStep;

    //feasible region
    x_key = max(0, x_key);
    x_key = min(g_grid_size - 1, x_key);

    y_key = max(0, y_key);
    y_key = min(g_grid_size - 1, y_key);

    m_GridMatrix[x_key][y_key].origin_cell_flag = true;
    m_GridMatrix[x_key][y_key].m_o_boundary_point[0] = g_agent_vector[agent_no].m_GPSPointVector[g].pt;

    if (g + 1 < g_agent_vector[agent_no].m_GPSPointVector.size())
    {
      m_GridMatrix[x_key][y_key].m_o_boundary_point[1] = g_agent_vector[agent_no].m_GPSPointVector[g + 1].pt;
    }

    // third step for destination GPS index

    g = g_agent_vector[agent_no].tail_gps_index;
    x_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.x - m_left) / m_GridXStep;
    y_key = (g_agent_vector[agent_no].m_GPSPointVector[g].pt.y - m_bottom) / m_GridYStep;

    //feasible region
    x_key = max(0, x_key);
    x_key = min(g_grid_size - 1, x_key);

    y_key = max(0, y_key);
    y_key = min(g_grid_size - 1, y_key);

    m_GridMatrix[x_key][y_key].destination_cell_flag = true;
    if (g - 1 >= 0)
    {
      m_GridMatrix[x_key][y_key].m_d_boundary_point[0] = g_agent_vector[agent_no].m_GPSPointVector[g - 1].pt;
      m_GridMatrix[x_key][y_key].m_d_boundary_point[1] = g_agent_vector[agent_no].m_GPSPointVector[g].pt;
    }

    // fourth step
    // for each grid matrix cell
    //scan x and y index in the grid
    // m_link_generalised_cost_array is the link cost used in shortest path

    for (int x_i = 0; x_i < g_grid_size; x_i++)
      for (int y_i = 0; y_i < g_grid_size; y_i++)
      {

        // for each grid cell
        // second, we now select the mininum of GPS point (in the same cell) to link distance to set the link cost
        for (int g = 0; g < m_GridMatrix[x_i][y_i].m_GPSPointVector.size(); g++) // for each GPS point of an agent in the cell
        {
          if (g == m_GridMatrix[x_i][y_i].m_GPSPointVector.size() - 1) // boundary points
            continue;

          // compute the average distance from the GPS points (g, g+1) to the ending points of a link
          for (int local_l = 0; local_l < m_GridMatrix[x_i][y_i].m_LinkNoVector.size(); local_l++) // for all links in this cell
          {
            int l = m_GridMatrix[x_i][y_i].m_LinkNoVector[local_l];

            // we consider GPS segment to the link shape point segment distance
            for (int p = 0; p < g_link_vector[l].m_PointVector.size(); p++)
            {
              double distance_from = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_GPSPointVector[g].pt, &g_link_vector[l].m_PointVector[p]);
              double distance_to = 0;

              if (g_agent_vector[agent_no].m_GPSPointVector.size() >= 2 && p < g_link_vector[l].m_PointVector.size() - 1)
              {
                distance_to = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_GPSPointVector[g + 1].pt, &g_link_vector[l].m_PointVector[p + 1]);
              }

              // we do not need to detect ill conditionning here, as the link in the cell , and the GPS trace information is all we have.
              // distance from is the distance from GPS point g to from node of link
              // distance to is the distance from GPS point g to to node of link
              double distance = (distance_from + distance_to) / 2;

              //if (g_link_vector[l].to_node_id == 172)
              //{
              //TRACE("grid: %d,%d,trace_d: %d, dist = %f\n",
              //	x_i, y_i,m_GridMatrix[x_i][y_i].m_GPSPointVector[g + 1].trace_id, distance);
              //}

              if (distance < m_link_generalised_cost_array[l])
              {
                m_link_generalised_cost_array[l] = distance; // use this distance as the likelihood cost
              }
            }
          }
        }

        if (m_GridMatrix[x_i][y_i].origin_cell_flag == 1) //   find origin node of shortest path
        {
          double min_distance_to_boundary_point = MAX_LABEL_COST_;

          for (int local_l = 0; local_l < m_GridMatrix[x_i][y_i].m_LinkNoVector.size(); local_l++) // for all links in this cell
          {
            int l = m_GridMatrix[x_i][y_i].m_LinkNoVector[local_l];

            double distance = MAX_LABEL_COST_;

            //if (g_link_vector[l].from_node_id == 9945 && g_link_vector[l].to_node_id == 115)
            //{
            //TRACE("");
            //}

            //ill conditioning detection

            if (g_ill_conditioning_detection(g_link_vector[l].distance, g_agent_vector[agent_no].first_segment_distance) == false)
            { // case of good conditioning
              double distance_from = g_GetPoint2LineDistance(&m_GridMatrix[x_i][y_i].m_o_boundary_point[0], &g_node_vector[g_link_vector[l].from_node_seq_no].pt, &g_node_vector[g_link_vector[l].to_node_seq_no].pt,
                1, false);

              double distance_to = 0;

              if (g_agent_vector[agent_no].m_GPSPointVector.size() >= 2)
              {
                distance_to = g_GetPoint2LineDistance(&m_GridMatrix[x_i][y_i].m_o_boundary_point[1],
                  &g_node_vector[g_link_vector[l].from_node_seq_no].pt, &g_node_vector[g_link_vector[l].to_node_seq_no].pt,
                  1, false);
              }
              double distance_from_p2p = 0;
              double distance_to_p2p = 0;

              distance_from_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_o_boundary_point[0], &g_node_vector[g_link_vector[l].from_node_seq_no].pt);
              distance_to_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_o_boundary_point[0], &g_node_vector[g_link_vector[l].to_node_seq_no].pt);
              distance = (distance_from + distance_to + distance_from_p2p + distance_to_p2p) / 4;
            }
            else
            {
              //case of ill conditioning, we have no help, we can only take the minimum of point to point distance
              double distance_from_p2p = 0;
              double distance_to_p2p = 0;

              distance_from_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_o_boundary_point[0], &g_node_vector[g_link_vector[l].from_node_seq_no].pt);
              distance_to_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_o_boundary_point[0], &g_node_vector[g_link_vector[l].to_node_seq_no].pt);

              distance = min(distance_from_p2p, distance_to_p2p);

              // consider the minimal distance of any point, and avg distance of cross-section distance
            }

            // we check this relative angle condition for both ill and good conditions,
            if (g_agent_vector[agent_no].m_GPSPointVector.size() >= 2)
            {
              double relative_angle = fabs(g_Find_PPP_RelativeAngle(
                &m_GridMatrix[x_i][y_i].m_o_boundary_point[0],
                &m_GridMatrix[x_i][y_i].m_o_boundary_point[1],
                &g_node_vector[g_link_vector[l].from_node_seq_no].pt,
                &g_node_vector[g_link_vector[l].to_node_seq_no].pt));

              if (relative_angle > 45)
              {
                // add penalty for opposite direction
                distance = distance * 10; /// 10 times as panalty
              }
            }

            int i_trace = 0;

            if (distance < min_distance_to_boundary_point)
            {

              min_distance_to_boundary_point = distance;
              origin_node_no = g_link_vector[l].from_node_seq_no;
              g_agent_vector[agent_no].matching_link_no = l;
              //							g_agent_vector[agent_no].upstream_node_matched_time_in_sec = t;

              //TRACE("%d -> %d, %f \n", g_link_vector[l].from_node_id, g_link_vector[l].to_node_id, distance);
            }
          }
        }

        if (m_GridMatrix[x_i][y_i].destination_cell_flag == 1) // find destination_node_no
        {
          double min_distance_to_boundary_point = MAX_LABEL_COST_;
          for (int local_l = 0; local_l < m_GridMatrix[x_i][y_i].m_LinkNoVector.size(); local_l++) // for all links in this cell
          {
            int l = m_GridMatrix[x_i][y_i].m_LinkNoVector[local_l];

            //if (g_link_vector[l].from_node_id == 4699)
            //{
            //	TRACE("");
            //}

            double distance = MAX_LABEL_COST_;

            if (g_ill_conditioning_detection(g_link_vector[l].distance, g_agent_vector[agent_no].last_segment_distance) == false)
            { // case of good conditioning
              double distance_from = g_GetPoint2LineDistance(&m_GridMatrix[x_i][y_i].m_d_boundary_point[0],
                &g_node_vector[g_link_vector[l].from_node_seq_no].pt, &g_node_vector[g_link_vector[l].to_node_seq_no].pt,
                1, false);
              double distance_to = 0;

              distance_to = g_GetPoint2LineDistance(&m_GridMatrix[x_i][y_i].m_d_boundary_point[1],
                &g_node_vector[g_link_vector[l].from_node_seq_no].pt, &g_node_vector[g_link_vector[l].to_node_seq_no].pt,
                1, false);

              //ill conditioning detection

              double distance_from_p2p = 0;
              double distance_to_p2p = 0;

              distance_from_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_d_boundary_point[0], &g_node_vector[g_link_vector[l].from_node_seq_no].pt);
              distance_to_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_d_boundary_point[0], &g_node_vector[g_link_vector[l].to_node_seq_no].pt);
              distance = (distance_from + distance_to + distance_from_p2p + distance_to_p2p) / 4;
            }
            else
            { // case of ill conditionning
              double distance_from_p2p = 0;
              double distance_to_p2p = 0;

              distance_from_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_d_boundary_point[1], &g_node_vector[g_link_vector[l].from_node_seq_no].pt);
              //[1] ending point of GPS point segment
              distance_to_p2p = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_d_boundary_point[1], &g_node_vector[g_link_vector[l].to_node_seq_no].pt);
              distance = min(distance_from_p2p, distance_to_p2p);
            }

            // we check this relative angle condition for both ill and good conditions,
            if (g_agent_vector[agent_no].m_GPSPointVector.size() >= 2)
            {
              double relative_angle = fabs(g_Find_PPP_RelativeAngle(
                &m_GridMatrix[x_i][y_i].m_d_boundary_point[0],
                &m_GridMatrix[x_i][y_i].m_d_boundary_point[1],
                &g_node_vector[g_link_vector[l].from_node_seq_no].pt,
                &g_node_vector[g_link_vector[l].to_node_seq_no].pt));

              if (relative_angle > 45)
              {
                // add penalty for opposite direction
                distance = distance * 10; /// 10 times as panalty
              }
            }

            if (distance < min_distance_to_boundary_point)
            {
              min_distance_to_boundary_point = distance;
              destination_node_no = g_link_vector[l].to_node_seq_no;
              //TRACE("%d -> %d, %f \n", g_link_vector[l].from_node_id, g_link_vector[l].to_node_id, distance);
            }
          }
        }
      }
  }

  void AlignGPSPoints2Route(int agent_no)
  {

    double total_GPS_distance = 0;
    int g;

    for (int i = 0; i < g_agent_vector[agent_no].m_node_size - 1; i++) // for each link along the route
    {

       int link_no = g_agent_vector[agent_no].path_link_vector[i];

      double least_distance_to = MAX_LABEL_COST_; // init

      int x_i = g_link_vector[link_no].x_key;
      int y_i = g_link_vector[link_no].y_key;

      for (int g = 0; g < m_GridMatrix[x_i][y_i].m_GPSPointVector.size(); g++) // for each GPS point of an agent in the cell
      {
        if (g == m_GridMatrix[x_i][y_i].m_GPSPointVector.size() - 1) // boundary points
          continue;
        // compute the average distance from the GPS points (g, g+1) to the ending points of a link

        // we consider GPS segment to the link shape point segment distance

        if (g_link_vector[link_no].m_PointVector.size()>=1)
        {

          double distance_to = g_GetPoint2Point_Distance(&m_GridMatrix[x_i][y_i].m_GPSPointVector[g].pt, &g_link_vector[link_no].m_PointVector[0]);

          /*
          if (g_link_vector[link_no].to_node_id == 172)
          {
            TRACE("grid: %d,%d,trace_d: %d, dist = %f\n",
              x_i, y_i,
              m_GridMatrix[x_i][y_i].m_GPSPointVector[g].trace_id, distance_to);
          }
          */
          if (distance_to < least_distance_to)
          {
            least_distance_to = distance_to;
            g_agent_vector[agent_no].path_node_matched_time_in_sec[i] = m_GridMatrix[x_i][y_i].m_GPSPointVector[g].time_in_second; // g
            g_agent_vector[agent_no].path_link_matched_trace_id[i] = m_GridMatrix[x_i][y_i].m_GPSPointVector[g].trace_id;
          }
        }
      }
    }
  }

  std::vector<int> m_agent_vector;
  int m_memory_block_no;

  std::vector<int> m_origin_node_vector; // assigned nodes for computing
  std::vector<int> m_origin_zone_seq_no_vector;

  int tau;             // assigned nodes for computing
  int m_agent_type_no; // assigned nodes for computing
  double m_value_of_time;

  int m_threadNo; // internal thread number

  int m_ListFront; // used in coding SEL
  int m_ListTail;  // used in coding SEL

  int* m_SENodeList; // used in coding SEL

  double* m_node_label_cost;      // label cost // for shortest path calcuating
  double* m_label_time_array;     // time-based cost
  double* m_label_distance_array; // distance-based cost

  int* m_node_predecessor;  // predecessor for nodes
  int* m_node_status_array; // update status
  int* m_link_predecessor;  // predecessor for this node points to the previous link that updates its label cost (as part of optimality condition) (for easy referencing)

  double* m_link_flow_volume_array;

  double* m_link_generalised_cost_array;

  int* temp_path_node_vector;
  // major function 1:  allocate memory and initialize the data
  void AllocateMemory(int number_of_nodes, int number_of_links)
  {

    m_SENodeList = new int[number_of_nodes]; //1

    m_node_status_array = new int[number_of_nodes];       //2
    m_label_time_array = new double[number_of_nodes];     //3
    m_label_distance_array = new double[number_of_nodes]; //4
    m_node_predecessor = new int[number_of_nodes];        //5
    m_link_predecessor = new int[number_of_nodes];        //6
    m_node_label_cost = new double[number_of_nodes];      //7

    m_link_flow_volume_array = new double[number_of_links]; //8

    m_link_generalised_cost_array = new double[number_of_links]; //9
    temp_path_node_vector = new int[number_of_nodes];
  }

  ~NetworkForSP()
  {

    if (m_SENodeList != NULL) //1
      delete[] m_SENodeList;

    if (m_node_status_array != NULL) //2
      delete[] m_node_status_array;

    if (m_label_time_array != NULL) //3
      delete[] m_label_time_array;

    if (m_label_distance_array != NULL) //4
      delete[] m_label_distance_array;

    if (m_node_predecessor != NULL) //5
      delete[] m_node_predecessor;

    if (m_link_predecessor != NULL) //6
      delete[] m_link_predecessor;

    if (m_node_label_cost != NULL) //7
      delete[] m_node_label_cost;

    if (m_link_flow_volume_array != NULL) //8
      delete[] m_link_flow_volume_array;

    if (m_link_generalised_cost_array != NULL) //9
      delete[] m_link_generalised_cost_array;

    if (temp_path_node_vector != NULL) //9
      delete[] temp_path_node_vector;

    if (m_GridMatrix)
      Deallocate2DDynamicArray<GridNodeSet>(m_GridMatrix, MAX_GRID_SIZE_);
  }

  // SEList: scan eligible List implementation: the reason for not using STL-like template is to avoid overhead associated pointer allocation/deallocation
  inline void SEList_clear()
  {
    m_ListFront = -1;
    m_ListTail = -1;
  }

  inline void SEList_push_front(int node)
  {
    if (m_ListFront == -1) // start from empty
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
    if (m_ListFront == -1) // start from empty
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
    return (m_ListFront == -1);
  }

  //major function: update the cost for each node at each SP tree, using a stack from the origin structure

  int origin_node_no;
  int destination_node_no;

  //major function 2: // abel correcting algorithm with double queue implementation
  double optimal_label_correcting(int agent_no)
  {
    origin_node_no = -1;
    destination_node_no = -1;

    AddGPSPointsIntoGridSystem(agent_no); //find the origin and destination nodes

    int number_of_nodes = g_node_vector.size();
    int i;
    for (i = 0; i < number_of_nodes; i++) //Initialization for all non-origin nodes
    {
      m_node_status_array[i] = 0; // not scanned
      m_node_label_cost[i] = MAX_LABEL_COST_;
      m_link_predecessor[i] = -1; // pointer to previous NODE INDEX from the current label at current node and time
      m_node_predecessor[i] = -1; // pointer to previous NODE INDEX from the current label at current node and time
                                  // comment out to speed up comuting
                                  ////m_label_time_array[i] = 0;
                                  ////m_label_distance_array[i] = 0;
    }

    int internal_debug_flag = 0;
    if (origin_node_no == -1 || destination_node_no == -1)
    {
      return 0;
    }

    cout << "origin_node_no =" << g_node_vector[origin_node_no].node_id << "; "
      << "destination_node_no =" << g_node_vector[destination_node_no].node_id << endl;

    //Initialization for origin node at the preferred departure time, at departure time, cost = 0, otherwise, the delay at origin node
    m_label_time_array[origin_node_no] = 0;
    m_node_label_cost[origin_node_no] = 0.0;
    //Mark:	m_label_distance_array[origin_node_no] = 0.0;

    m_link_predecessor[origin_node_no] = -1; // pointer to previous NODE INDEX from the current label at current node and time
    m_node_predecessor[origin_node_no] = -1; // pointer to previous NODE INDEX from the current label at current node and time

    SEList_clear();
    SEList_push_back(origin_node_no);

    int from_node, to_node;
    int link_sqe_no;
    double new_time = 0;
    double new_distance = 0;
    double new_to_node_cost = 0;
    int tempFront;
    while (!(m_ListFront == -1)) //SEList_empty()
    {
      //          from_node = SEList_front();
      //			SEList_pop_front();  // remove current node FromID from the SE list

      from_node = m_ListFront; //pop a node FromID for scanning
      tempFront = m_ListFront;
      m_ListFront = m_SENodeList[m_ListFront];
      m_SENodeList[tempFront] = -1;

      m_node_status_array[from_node] = 2;

      int pred_link_seq_no = m_link_predecessor[from_node];

      for (i = 0; i < g_node_vector[from_node].m_outgoing_link_seq_no_vector.size(); i++) // for each link (i,j) belong A(i)
      {

        link_sqe_no = g_node_vector[from_node].m_outgoing_link_seq_no_vector[i];
        to_node = g_link_vector[link_sqe_no].to_node_seq_no;

        //remark: the more complicated implementation can be found in paper Shortest Path Algorithms In Transportation Models: Classical and Innovative Aspects
        //	A note on least time path computation considering delays and prohibitions for intersection movements
        //very important: only origin zone can access the outbound connectors,
        //the other zones do not have access to the outbound connectors

        new_to_node_cost = m_node_label_cost[from_node] + m_link_generalised_cost_array[link_sqe_no]; // m_link_generalised_cost_array is the likelihood cost determined externally by the GPS points to link distance

        if (new_to_node_cost < m_node_label_cost[to_node]) // we only compare cost at the downstream node ToID at the new arrival time t
        {

          m_node_label_cost[to_node] = new_to_node_cost;
          m_node_predecessor[to_node] = from_node;   // pointer to previous physical NODE INDEX from the current label at current node and time
          m_link_predecessor[to_node] = link_sqe_no; // pointer to previous physical NODE INDEX from the current label at current node and time

          // deque updating rule for m_node_status_array
          if (m_node_status_array[to_node] == 0)
          {
            ///// SEList_push_back(to_node);
            ///// begin of inline block
            if (m_ListFront == -1) // start from empty
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
            if (m_ListFront == -1) // start from empty
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
      int current_node_seq_no = destination_node_no; // destination node
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

        current_node_seq_no = m_node_predecessor[current_node_seq_no]; // update node seq no
      }

      p_agent->AllocatePathNodeVector(l_node_size, temp_path_node_vector, true);
      if (origin_node_no >= 0 && destination_node_no >= 0) //feasible origin and destination nodes
      {
        p_agent->o_node_id = g_node_vector[origin_node_no].node_id;

        p_agent->d_node_id = g_node_vector[destination_node_no].node_id;
      }

      // determine path link sequence
      for (int n = 0; n < p_agent->m_node_size - 1; n++) // for each link along the route
      {
          int node_no = p_agent->path_node_vector[n];
          int next_node_no = p_agent->path_node_vector[n + 1];

          int link_no = 0;

          if (g_node_vector[node_no].m_outgoing_link_seq_no_map.find(next_node_no) != g_node_vector[node_no].m_outgoing_link_seq_no_map.end())
          {
              p_agent->path_link_vector[n] = g_node_vector[node_no].m_outgoing_link_seq_no_map[next_node_no];
          }
      }

      AlignGPSPoints2Route(i); // GPS points to route alignmennt at the final stage
    }
  }
};
NetworkForSP* g_pNetworkVector = nullptr;

vector<double> g_timestr2second(string str)
{
  vector<double> output_global_minute;
  vector<double> output_global_second;

  int string_lenghth = str.length();

  const char* string_line = str.data(); //string to char*

  int char_length = strlen(string_line);

  char ch, buf_ddhhmm[32] = { 0 }, buf_SS[32] = { 0 }, buf_sss[32] = { 0 };
  char dd1, dd2, hh1, hh2, mm1, mm2, SS1, SS2, sss1, sss2, sss3;
  double ddf1, ddf2, hhf1, hhf2, mmf1, mmf2, SSf1, SSf2, sssf1, sssf2, sssf3;
  double global_minute = 0;
  double dd = 0, hh = 0, mm = 0, SS = 0, sss = 0;
  int i = 0;
  int buffer_i = 0, buffer_k = 0, buffer_j = 0;
  int num_of_colons = 0;

  //DDHHMM:SS:sss or HHMM:SS:sss

  while (i < char_length)
  {
    ch = string_line[i++];

    if (num_of_colons == 0 && ch != '_' && ch != ':') //input to buf_ddhhmm until we meet the colon
    {
      buf_ddhhmm[buffer_i++] = ch;
    }
    else if (num_of_colons == 1 && ch != ':') //start the Second "SS"
    {
      buf_SS[buffer_k++] = ch;
    }
    else if (num_of_colons == 2 && ch != ':') //start the Millisecond "sss"
    {
      buf_sss[buffer_j++] = ch;
    }

    if (ch == '_' || ch == ';' || i == char_length) //start a new time string
    {
      if (buffer_i == 4) //"HHMM"
      {
        //HHMM, 0123
        hh1 = buf_ddhhmm[0]; //read each first
        hh2 = buf_ddhhmm[1];
        mm1 = buf_ddhhmm[2];
        mm2 = buf_ddhhmm[3];

        hhf1 = ((double)hh1 - 48); //convert a char to a double
        hhf2 = ((double)hh2 - 48);
        mmf1 = ((double)mm1 - 48);
        mmf2 = ((double)mm2 - 48);

        dd = 0;
        hh = hhf1 * 10 * 60 + hhf2 * 60;
        mm = mmf1 * 10 + mmf2;
      }
      else if (buffer_i == 6) //"DDHHMM"
      {
        //DDHHMM, 012345
        dd1 = buf_ddhhmm[0]; //read each first
        dd2 = buf_ddhhmm[1];
        hh1 = buf_ddhhmm[2];
        hh2 = buf_ddhhmm[3];
        mm1 = buf_ddhhmm[4];
        mm2 = buf_ddhhmm[5];

        ddf1 = ((double)dd1 - 48); //convert a char to a double
        ddf2 = ((double)dd2 - 48);
        hhf1 = ((double)hh1 - 48);
        hhf2 = ((double)hh2 - 48);
        mmf1 = ((double)mm1 - 48);
        mmf2 = ((double)mm2 - 48);

        dd = ddf1 * 10 * 24 * 60 + ddf2 * 24 * 60;
        hh = hhf1 * 10 * 60 + hhf2 * 60;
        mm = mmf1 * 10 + mmf2;
      }

      if (num_of_colons == 1 || num_of_colons == 2)
      {
        //SS, 01
        SS1 = buf_SS[0]; //read each first
        SS2 = buf_SS[1];

        SSf1 = ((double)SS1 - 48); //convert a char to a double
        SSf2 = ((double)SS2 - 48);

        SS = (SSf1 * 10 + SSf2) / 60;
      }

      if (num_of_colons == 2)
      {
        //sss, 012
        sss1 = buf_sss[0]; //read each first
        sss2 = buf_sss[1];
        sss3 = buf_sss[2];

        sssf1 = ((double)sss1 - 48); //convert a char to a double
        sssf2 = ((double)sss2 - 48);
        sssf3 = ((double)sss3 - 48);

        sss = (sssf1 * 100 + sssf2 * 10 + sssf3) / 1000;
      }

      global_minute = dd + hh + mm + SS + sss;
      double global_second = (dd + hh + mm + SS + sss) * 60.0;

      output_global_second.push_back(global_second);

      //initialize the parameters
      buffer_i = 0;
      buffer_k = 0;
      buffer_j = 0;
      num_of_colons = 0;
    }

    if (ch == ':')
    {
      num_of_colons += 1;
    }
  }

  return output_global_second;
}
int timestr2second(string time_str)
{ //hhmmss
  string hh = time_str.substr(0, 2);
  string mm = time_str.substr(2, 2);
  string ss = time_str.substr(5, 2);
  int hhi = stoi(hh);
  int mmi = stoi(mm);
  int ssi = stoi(ss);
  return hhi * 3600 + mmi * 60 + ssi;
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

    while (parser.ReadRecord()) // if this line contains [] mark, then we will also read field headers.
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

      parser_link.GetValueByFieldName("length", link.length);

      parser_link.GetValueByFieldName("free_speed", link.free_speed);

      link.FFTT_in_sec = link.length / (link.free_speed * 1000.0 / 3600.0);

      string allowed_uses;
      parser_link.GetValueByFieldName("allowed_uses", allowed_uses, false);

      //if (allowed_uses != 1)  // not allowed, skip this link in map matching process,  we have to comment out this line. to allow easy input for all mode.
      //	continue;  // if users need to select a specific network, they have to construct underlying network

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

      string geometry_str;
      parser_link.GetValueByFieldName("geometry", geometry_str);

      link.from_node_seq_no = g_internal_node_seq_no_map[link.from_node_id];
      link.to_node_seq_no = g_internal_node_seq_no_map[link.to_node_id];
      link.geometry = geometry_str;

      // overwrite when the field "geometry" exists
      CGeometry geometry(geometry_str);
      std::vector<CCoordinate> CoordinateVector;
      CoordinateVector = geometry.GetCoordinateList();

      link.distance = 0;
      GDPoint Point;
      GDPoint Point_next;

      if (CoordinateVector.size() >= 2)
      {
        for (int l = 0; l < CoordinateVector.size(); l++)
        {

          Point.x = CoordinateVector[l].X;
          Point.y = CoordinateVector[l].Y;
          //				GPSPoint.time_str = time_stamp;

          link.m_PointVector.push_back(Point);

          if (l < CoordinateVector.size() - 1) // consider shape points in each segment of a link
          {
            Point_next.x = CoordinateVector[l + 1].X;
            Point_next.y = CoordinateVector[l + 1].Y;

            link.distance += g_GetPoint2Point_Distance(&Point, &Point_next);
          }
        }
        link.distance = link.distance / (CoordinateVector.size() - 1); // take the average of sgement distance
      }

      link.link_seq_no = g_number_of_links++;

      g_internal_link_no_map[link.link_id] = link.link_seq_no;
      g_node_vector[link.from_node_seq_no].m_outgoing_link_seq_no_vector.push_back(link.link_seq_no);
      g_node_vector[link.from_node_seq_no].m_outgoing_link_seq_no_map[link.to_node_seq_no] = link.link_seq_no;
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
 

    gps_point_count = 0;
    if (gps_parser.OpenCSVFile("trace.csv", true))
    {
      cout << "reading trace.csv" << endl;

      double x, y;

      while (gps_parser.ReadRecord())
      {
        string agent_id;
        if (gps_parser.GetValueByFieldName("agent_id", agent_id) == false)
          continue;

        if (g_internal_agent_no_map.find(agent_id) == g_internal_agent_no_map.end())
        {

          g_internal_agent_no_map[agent_id] = g_internal_agent_no_map.size(); // assign the internal agent no as the current size of the map.
          CAgent agent;
          agent.agent_id = agent_id;
          agent.agent_no = g_agent_vector.size();
          g_agent_vector.push_back(agent);
        }

        gps_parser.GetValueByFieldName("x_coord", x, false);
        gps_parser.GetValueByFieldName("y_coord", y, false);
        int hh = 0;
        int mm = 0;
        int ss = 0;
        gps_parser.GetValueByFieldName("hh", hh);
        gps_parser.GetValueByFieldName("mm", mm);
        gps_parser.GetValueByFieldName("ss", ss);

        int trace_id = 0;
        gps_parser.GetValueByFieldName("trace_id", trace_id);

        int time_in_second;
        time_in_second = hh * 3600 + mm * 60 + ss;

        CGPSPoint GPSPoint;

        GPSPoint.trace_id = trace_id;
        GPSPoint.pt.x = x;
        GPSPoint.pt.y = y;
        GPSPoint.time_in_second = time_in_second;
        g_agent_vector[g_internal_agent_no_map[agent_id]].m_GPSPointVector.push_back(GPSPoint);
        gps_point_count++;
      }

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
  //int number_of_threads = omp_get_max_threads();
  int number_of_threads = 1;
  if (number_of_threads <= g_max_number_of_threads)
    return number_of_threads;
  else
    return g_max_number_of_threads;
}

void g_OutputAgentCSVFile()
{
  FILE* g_pFileAgent = nullptr;
  g_pFileAgent = fopen("agent.csv", "w");

  if (g_pFileAgent == NULL)
  {
    cout << "File agent.csv cannot be opened." << endl;
    g_Program_stop();
  }
  else
  {
    fprintf(g_pFileAgent, "agent_id,o_node_id,d_node_id,o_zone_id,d_zone_id,matching_link_from_node_id,matching_link_to_node_id,matching_link_id,node_sequence,geometry\n");

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

      if (p_agent->m_node_size > 1) // with feasible path
      {
        fprintf(g_pFileAgent, "\"LINESTRING (");

        for (int i = 0; i < p_agent->m_node_size - 1; i++)
        {
          int link_no = g_node_vector[p_agent->path_node_vector[i]].m_outgoing_link_seq_no_map[p_agent->path_node_vector[i + 1]];

          for (int gl = 0; gl < g_link_vector[link_no].m_PointVector.size() - 1; gl++) //-1 to skip the last GD point
          {
            fprintf(g_pFileAgent, "%f %f,", g_link_vector[link_no].m_PointVector[gl].x,
              g_link_vector[link_no].m_PointVector[gl].y);
          }
        }
        fprintf(g_pFileAgent, ")\"");
      }
      else
      {
        if (p_agent->matching_link_no >= 0)
        {
          fprintf(g_pFileAgent, "\"%s\",", g_link_vector[p_agent->matching_link_no].geometry.c_str());
        }
      }

      fprintf(g_pFileAgent, "\n");
    }

    fclose(g_pFileAgent);
  }
}

void g_OutputRouteCSVFile()
{

  FILE* g_pFileLinkRoute = nullptr;
  g_pFileLinkRoute = fopen("route.csv", "w");

  if (g_pFileLinkRoute == NULL)
  {
    cout << "File route.csv cannot be opened." << endl;
    g_Program_stop();
  }
  else
  {
    fprintf(g_pFileLinkRoute, "agent_id,from_node_id,to_node_id,timestamp,cumu_distance,hhmmss,trace_id,travel_time,delay,geometry\n");

    for (int a = 0; a < g_agent_vector.size(); a++)
    {
      CAgent* p_agent = &(g_agent_vector[a]);

      int travel_time_in_second;
      int timestamp_in_upstreamnode = -1;

      double cumulative_distance = 0;
      for (int i = 1; i < p_agent->m_node_size - 1; i++)
      {

        fprintf(g_pFileLinkRoute, "%s,", p_agent->agent_id.c_str());

        int from_node_id = g_node_vector[p_agent->path_node_vector[i]].node_id;
        int to_node_id = g_node_vector[p_agent->path_node_vector[i + 1]].node_id;
        fprintf(g_pFileLinkRoute, "%d,%d,", from_node_id, to_node_id);

        // timestamp

        int link_no = p_agent->path_link_vector[i];
        int prev_link_no = p_agent->path_link_vector[i-1];

        timestamp_in_upstreamnode = p_agent->path_node_matched_time_in_sec[i-1];

          fprintf(g_pFileLinkRoute, "%d,", p_agent->path_node_matched_time_in_sec[i]);

          cumulative_distance += g_link_vector[link_no].length;
          fprintf(g_pFileLinkRoute, "%.2f,", cumulative_distance);

          string timestamp_str = second2timestr(p_agent->path_node_matched_time_in_sec[i]);

          fprintf(g_pFileLinkRoute, "%s,", timestamp_str.c_str());

          travel_time_in_second = p_agent->path_node_matched_time_in_sec[i] - timestamp_in_upstreamnode;
          timestamp_in_upstreamnode = p_agent->path_node_matched_time_in_sec[i]; // recursive update

          int trace_id = p_agent->path_link_matched_trace_id[i];

          //trace id
          fprintf(g_pFileLinkRoute, "%d,", trace_id);

          //travel time
          fprintf(g_pFileLinkRoute, "%d,", max(0, travel_time_in_second));
          //delay
          int delay = max(0, travel_time_in_second - g_link_vector[link_no].FFTT_in_sec);
          fprintf(g_pFileLinkRoute, "%d,", delay);

          travel_time_in_second = max(1, travel_time_in_second);

          //update upstream node from the current link
          fprintf(g_pFileLinkRoute, "\"%s\"", g_link_vector[link_no].geometry.c_str());
          fprintf(g_pFileLinkRoute, "\n");
      }

    }
    

    fclose(g_pFileLinkRoute);
  }
}


bool g_LikelyRouteFinding()
{
  //int number_of_threads = g_number_of_CPU_threads();
  int number_of_threads = 1;
  g_pNetworkVector = new NetworkForSP[number_of_threads]; // create n copies of network, each for a subset of agents to use

  cout << "number of CPU threads = " << number_of_threads << endl;

  NetworkForSP* p_Network;

  for (int i = 0; i < number_of_threads; i++)
  {
    g_pNetworkVector[i].AllocateMemory(g_number_of_nodes, g_number_of_links);
    g_pNetworkVector[i].BuildGridSystem(); // called once
  }

  for (int a = 0; a < g_agent_vector.size(); a++) //
  {

    p_Network = &g_pNetworkVector[a % number_of_threads];

    p_Network->m_agent_vector.push_back(a);
  }

  //#pragma omp parallel for
  for (int thread_no = 0; thread_no < number_of_threads; thread_no++)
  {
    g_pNetworkVector[thread_no].find_path_for_agents_assigned_for_this_thread();
  }

//  g_OutputAgentCSVFile();
  g_OutputRouteCSVFile();

  cout << "End of Sequential Optimization Process. " << endl;

  return true;
}

//int main(int argc, TCHAR* argv[], TCHAR* envp[])
int main(int argc)
//void MapMatching4GMNS(int mode)
{
  clock_t start_t, end_t, total_t;
  
  g_ReadInputData();
  start_t = clock();
  g_LikelyRouteFinding();

  end_t = clock();
  total_t = (end_t - start_t);
  cout << "CPU Running Time = " << total_t / 1000.0 << " seconds" << endl;
  cout << "free memory.." << endl;
  cout << "done." << endl;

  g_node_vector.clear();
  g_link_vector.clear();
  g_agent_vector.clear();

  //return 1;
}