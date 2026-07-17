# @author       Jiawei Lu (jiaweil9@asu.edu)
# @time         2021/4/29 12:11
# @desc         [script description]
'''
    Download and format trace data directly from OpenStreetMap** 
    python get_gps_trace.py*
    Note: If you set up a network that is wider, the more trace information you get, and the longer you download and format it.
'''
from urllib.request import urlopen
import multiprocessing as mp
import xml.etree.cElementTree as ET
import re
import numpy as np
import pandas as pd


# Boundary Box
min_lon = -114.00   # -112.7063
min_lat = 33.40  # 34.0613
max_lon = -110.13   # -112.4725
max_lat = 35.81   # 34.2548

processors = 20
output_xml = False

url_template = 'https://api.openstreetmap.org/api/0.6/trackpoints?bbox={},{},{},{}&page={}'
ns_pattern = re.compile(r' xmlns="(.*)"')


def getPageData(bbox, page):
    min_lon_, min_lat_, max_lon_, max_lat_ = bbox
    vehicle_trace_list_page = []

    request_url = url_template.format(min_lon_, min_lat_, max_lon_, max_lat_, page)
    req = urlopen(request_url)
    res = req.read().decode()

    res_nons = re.sub(ns_pattern, '', res, count=1)

    tree = ET.ElementTree(ET.fromstring(res_nons))
    root = tree.getroot()

    for trk in root:
        trkseg = trk.find('trkseg')
        if trkseg is None: continue
        gps_points_list_veh = []
        for trkpt in trkseg:
            pttime = trkpt.find('time')
            if pttime is None:
                # untrackable
                break
            time_stamp = pttime.text
            lat, lon = trkpt.attrib['lat'], trkpt.attrib['lon']
            gps_points_list_veh.append((time_stamp, lon, lat))

        if gps_points_list_veh:
            vehicle_trace_list_page.append(gps_points_list_veh)

    file_name = f'download_{min_lon_}-{min_lat_}-{max_lon_}-{max_lat_}_{page}.xml'
    if output_xml:
        with open(file_name, 'w',encoding='utf-8') as fin:
            fin.write(res_nons)

    return vehicle_trace_list_page


def getRegionData(bbox):
    print(f'getting gps data on subregion {bbox}')
    vehicle_trace_list_region = []
    page = 0

    while True:
        vehicle_trace_list_page = getPageData(bbox,page)
        if vehicle_trace_list_page:
            vehicle_trace_list_region += vehicle_trace_list_page
        else:
            break
        page += 1

    return vehicle_trace_list_region


def downloadGPSData():
    num_of_lon_inters = int(np.ceil((max_lon - min_lon) / 0.49))
    num_of_lat_inters = int(np.ceil((max_lat - min_lat) / 0.49))
    lons = np.linspace(min_lon, max_lon, num_of_lon_inters+1, endpoint=True).round(7)
    lats = np.linspace(min_lat, max_lat, num_of_lat_inters+1, endpoint=True).round(7)
    sub_bbox_list = [(lons[m],lats[n],lons[m+1],lats[n+1]) for m in range(num_of_lon_inters) for n in range(num_of_lat_inters)]
    print(f'number of subregions: {len(sub_bbox_list)}')

    p = mp.Pool(processes=processors)
    vehicle_trace_list_regions = p.map(getRegionData, sub_bbox_list)
    vehicle_trace_list_ = []
    vehicle_no = 0
    for vehicle_trace_list_region in vehicle_trace_list_regions:
        for vehicle_trace in vehicle_trace_list_region:
            for trace_point in vehicle_trace:
                vehicle_trace_list_.append((vehicle_no, *trace_point))
            vehicle_no += 1


    # vehicle_trace_list = []
    # for sub_bbox in sub_bbox_list:
    #     vehicle_trace_list_region = getRegionData(sub_bbox)
    #     vehicle_trace_list += vehicle_trace_list_region
    #
    # vehicle_trace_list_ = []
    # for vehicle_no, vehicle_trace in enumerate(vehicle_trace_list):
    #     for trace_point in vehicle_trace:
    #         vehicle_trace_list_.append((vehicle_no, *trace_point))


    vehicle_trace_df = pd.DataFrame(vehicle_trace_list_, columns=['agent_id','time','lon','lat'])
    vehicle_trace_df.to_csv('osm_gps.csv', index=False)



if __name__ == '__main__':
    downloadGPSData()


