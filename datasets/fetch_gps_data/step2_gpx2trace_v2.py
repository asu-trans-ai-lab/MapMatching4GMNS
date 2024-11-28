import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # For local timezone handling
import math

# Input GPX file and output CSV file paths
input_gpx = "tracks.gpx"  # Replace with the path to your GPX file
output_csv = "trace.csv"  # Replace with the desired output CSV file path

# Initialize data storage
data = []
agent_id_map = {}  # Map to assign sequential agent IDs
current_agent_id = 1  # Start agent_id from 1

# Approximate Earth radius in miles
EARTH_RADIUS_MI = 3958.8

# Define your local timezone
local_timezone = ZoneInfo("America/Los_Angeles")  # Replace with your desired timezone

def get_namespace(element):
    """Extract the namespace from the root element."""
    if element.tag.startswith("{"):
        return element.tag.split("}")[0] + "}"
    return ""

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth's surface."""
    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_MI * c

def calculate_speed_mph(prev_point, curr_point):
    """Calculate speed in miles per hour."""
    if not prev_point:
        return None  # No previous point to compare

    # Extract coordinates
    prev_lat, prev_lon = prev_point['y_coord'], prev_point['x_coord']
    curr_lat, curr_lon = curr_point['y_coord'], curr_point['x_coord']

    # Calculate distance in miles
    distance_miles = haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)

    # Calculate time difference in hours
    prev_time = prev_point['timestamp']
    curr_time = curr_point['timestamp']
    time_diff_hours = (curr_time - prev_time).total_seconds() / 3600

    # Avoid division by zero
    if time_diff_hours > 0:
        return distance_miles / time_diff_hours
    return None

# Parse the GPX file
try:
    print(f"Parsing {input_gpx}...")
    tree = ET.parse(input_gpx)
    root = tree.getroot()

    # Dynamically detect namespace
    namespace = get_namespace(root)
    print(f"Detected namespace: '{namespace}'")

    trace_no = 0  # Initialize trace number
    prev_point = None  # Store the previous data point for speed calculation
    for trk_index, trk in enumerate(root.findall(f"{namespace}trk")):
        # Extract trip_info from the <url> tag
        url_elem = trk.find(f"{namespace}url")
        trip_info = url_elem.text.strip() if url_elem is not None else f"Track_{trk_index + 1}"

        # Assign a unique agent_id for this trip_info
        if trip_info not in agent_id_map:
            agent_id_map[trip_info] = current_agent_id
            print(f"Processing new trip_info: {trip_info} -> assigned agent_id: {current_agent_id}")
            current_agent_id += 1

        agent_id = agent_id_map[trip_info]

        # Initialize trip metrics
        total_distance_miles = 0
        trip_start_time = None
        trip_end_time = None

        for trkseg_index, trkseg in enumerate(trk.findall(f"{namespace}trkseg")):
            for trkpt_index, trkpt in enumerate(trkseg.findall(f"{namespace}trkpt")):
                lat = trkpt.attrib.get('lat')
                lon = trkpt.attrib.get('lon')
                time_elem = trkpt.find(f"{namespace}time")
                time_text = time_elem.text if time_elem is not None else None

                # Convert time to local timezone-aware datetime object
                utc_timestamp = datetime.fromisoformat(time_text.replace("Z", "+00:00")).astimezone(timezone.utc)
                local_timestamp = utc_timestamp.astimezone(local_timezone)

                # Create the current data point
                curr_point = {
                    "agent_id": agent_id,
                    "x_coord": float(lon) if lon else None,
                    "y_coord": float(lat) if lat else None,
                    "trace_no": trace_no,
                    "trace_id": trace_no,  # Assuming trace_no = trace_id
                    "o_node_id": None,  # Origin node ID placeholder
                    "d_node_id": None,  # Destination node ID placeholder
                    "trip_info": trip_info,
                    "timestamp": utc_timestamp,
                    "local_timestamp": local_timestamp,  # Add local timestamp
                }

                # Calculate speed in mph
                curr_point["speed_mph"] = calculate_speed_mph(prev_point, curr_point)

                # Update trip metrics
                if prev_point:
                    total_distance_miles += haversine_distance(
                        prev_point["y_coord"], prev_point["x_coord"],
                        curr_point["y_coord"], curr_point["x_coord"]
                    )
                if not trip_start_time:
                    trip_start_time = curr_point["timestamp"]
                trip_end_time = curr_point["timestamp"]

                prev_point = curr_point  # Update previous point

                # Append the data
                data.append(curr_point)
                trace_no += 1

        # Compute total trip metrics
        total_time_hours = (trip_end_time - trip_start_time).total_seconds() / 3600 if trip_start_time and trip_end_time else 0
        avg_moving_speed_mph = total_distance_miles / total_time_hours if total_time_hours > 0 else 0

        # Log trip metrics
        print(f"Trip Info: {trip_info}")
        print(f"  Total Travel Time: {total_time_hours:.2f} hours")
        print(f"  Total Travel Distance: {total_distance_miles:.2f} miles")
        print(f"  Average Moving Speed: {avg_moving_speed_mph:.2f} mph")

        # Add trip metrics to the first record of this trip in the CSV
        if data:
            data[-trace_no]["total_travel_time_hours"] = total_time_hours
            data[-trace_no]["total_travel_distance_miles"] = total_distance_miles
            data[-trace_no]["avg_moving_speed_mph"] = avg_moving_speed_mph

    # Save to CSV
    if data:
        print(f"Writing data to {output_csv}...")
        df = pd.DataFrame(data, columns=[
            "agent_id", "x_coord", "y_coord", "trace_no", "trace_id", "o_node_id", "d_node_id", 
            "trip_info", "timestamp", "local_timestamp", "speed_mph",
            "total_travel_time_hours", "total_travel_distance_miles", "avg_moving_speed_mph"
        ])
        df.to_csv(output_csv, index=False)
        print(f"Data successfully saved to {output_csv}.")
    else:
        print("No data found in the GPX file.")

except FileNotFoundError:
    print(f"Error: {input_gpx} not found. Ensure the file exists.")
except ET.ParseError as e:
    print(f"Error parsing {input_gpx}: {e}")
