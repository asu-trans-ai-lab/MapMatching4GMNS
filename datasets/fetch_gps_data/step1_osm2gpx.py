# -*- coding: utf-8 -*-
"""
Created on Thu Nov 28 09:12:09 2024

@author: xzhou
"""

import requests

# Points A and B
point_a = (33.3968345, -111.8975069)  # Latitude, Longitude
point_b = (33.4161936, -111.934669)  # Latitude, Longitude

# Calculate bounding box
min_lat = min(point_a[0], point_b[0])
max_lat = max(point_a[0], point_b[0])
min_lon = min(point_a[1], point_b[1])
max_lon = max(point_a[1], point_b[1])

# Manual link generation
bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
page = 0  # Start with page 0
url = f"https://api.openstreetmap.org/api/0.6/trackpoints?bbox={bbox}&page={page}"

# Download the .gpx file
output_file = "tracks.gpx"
print(f"Downloading GPS tracks from: {url}")
response = requests.get(url)

if response.status_code == 200:
    with open(output_file, "wb") as file:
        file.write(response.content)
    print(f"GPS tracks saved to {output_file}")
else:
    print(f"Failed to download GPS tracks. HTTP Status Code: {response.status_code}")
