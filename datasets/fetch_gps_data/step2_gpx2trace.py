import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timezone
from geopy.distance import geodesic  # For distance calculation

# Input GPX file and output CSV file paths
input_gpx = "tracks.gpx"  # Replace with the path to your GPX file
output_csv = "trace.csv"  # Replace with the desired output CSV file path

# Initialize data storage
data = []
agent_id_map = {}  # Map to assign sequential agent IDs
current_agent_id = 1  # Start agent_id from 1

def get_namespace(element):
    """Extract the namespace from the root element."""
    if element.tag.startswith("{"):
        return element.tag.split("}")[0] + "}"
    return ""

def calculate_speed_mph(prev_point, curr_point):
    """Calculate speed in miles per hour."""
    if not prev_point:
        return None  # No previous point to compare

    # Calculate distance in miles
    prev_coords = (prev_point['y_coord'], prev_point['x_coord'])
    curr_coords = (curr_point['y_coord'], curr_point['x_coord'])
    distance_miles = geodesic(prev_coords, curr_coords).miles

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

        for trkseg_index, trkseg in enumerate(trk.findall(f"{namespace}trkseg")):
            for trkpt_index, trkpt in enumerate(trkseg.findall(f"{namespace}trkpt")):
                lat = trkpt.attrib.get('lat')
                lon = trkpt.attrib.get('lon')
                time_elem = trkpt.find(f"{namespace}time")
                time_text = time_elem.text if time_elem is not None else None

                # Convert time to local timezone-aware datetime object
                timestamp = datetime.fromisoformat(time_text.replace("Z", "+00:00")).astimezone(timezone.utc)

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
                    "timestamp": timestamp,
                }

                # Calculate speed in mph
                curr_point["speed_mph"] = calculate_speed_mph(prev_point, curr_point)
                prev_point = curr_point  # Update previous point

                # Append the data
                data.append(curr_point)
                trace_no += 1

    # Save to CSV
    if data:
        print(f"Writing data to {output_csv}...")
        df = pd.DataFrame(data, columns=[
            "agent_id", "x_coord", "y_coord", "trace_no", "trace_id", "o_node_id", "d_node_id", "trip_info", "timestamp", "speed_mph"
        ])
        df.to_csv(output_csv, index=False)
        print(f"Data successfully saved to {output_csv}.")
    else:
        print("No data found in the GPX file.")

except FileNotFoundError:
    print(f"Error: {input_gpx} not found. Ensure the file exists.")
except ET.ParseError as e:
    print(f"Error parsing {input_gpx}: {e}")
