import os
import boto3
import numpy as np
import matplotlib.pyplot as plt
import pyart
from datetime import datetime, timedelta
from botocore import UNSIGNED
from botocore.config import Config
import pandas as pd
from geopy.distance import geodesic

# --- CONFIG ---
# We MUST specify the region (us-east-1) for public NOAA buckets.
# We also disable signing to ensure we don't accidentally use local AWS credentials.
s3 = boto3.client(
    "s3", 
    region_name="us-east-1", 
    config=Config(signature_version=UNSIGNED)
)
BUCKET_NAME = "unidata-nexrad-level2"

def get_closest_nexrad(lat, lon, station_csv="station_list/nexrad_sites.csv"):
    """Finds the closest NEXRAD station identifier."""
    if not os.path.exists(station_csv):
        # Fallback to a small default list if CSV missing (or add your PDF parsing logic here)
        return "KDVN" # Default to Davenport, IA for testing
    
    df = pd.read_csv(station_csv)
    # Simple distance calculation
    def calc_dist(row):
        # Note: CSV column names might vary based on your PDF parser
        site_lat = row.get('LATITUDE_N', row.get('lat', 0))
        site_lon = row.get('LONGITUDE_W', row.get('lon', 0))
        return geodesic((lat, lon), (site_lat, -abs(site_lon))).km

    df['dist'] = df.apply(calc_dist, axis=1)
    closest = df.sort_values('dist').iloc[0]
    # Ensure we get the 4-letter ID (e.g., KDVN)
    site_id = closest.get('ID', closest.get('SITE', ''))
    if len(site_id) == 3: 
        site_id = "K" + site_id
    return site_id

# In radar_utils.py

def download_scans_window(site_id, event_time, window_hours=2, output_dir="radar_cache"):
    """Downloads all scans +/- window_hours around the event."""
    start_time = event_time - timedelta(hours=window_hours)
    end_time = event_time + timedelta(hours=window_hours)
    
    os.makedirs(output_dir, exist_ok=True)
    downloaded_files = []

    # Iterate through days (in case window crosses midnight)
    current_day = start_time.date()
    while current_day <= end_time.date():
        prefix = f"{current_day.strftime('%Y/%m/%d')}/{site_id}/"
        try:
            resp = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
            if 'Contents' in resp:
                for obj in resp['Contents']:
                    key = obj['Key']
                    filename = key.split('/')[-1]

                    # --- ADD THIS CHECK ---
                    if filename.endswith("_MDM"):
                        continue
                    # ----------------------

                    # Parse filename time: KDVN20250712_224026_V06
                    try:
                        time_part = filename.split('_')[1] # 224026
                        date_part = filename.split('_')[0][-8:] # 20250712
                        file_dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
                        
                        if start_time <= file_dt <= end_time:
                            local_path = os.path.join(output_dir, filename)
                            if not os.path.exists(local_path):
                                print(f"Downloading {filename}...")
                                s3.download_file(BUCKET_NAME, key, local_path)
                            downloaded_files.append(local_path)
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error listing S3 objects: {e}")
            
        current_day += timedelta(days=1)
        
    return sorted(downloaded_files)

def generate_radar_image(file_path, output_image_path):
    """
    Reads a NEXRAD file, generates a transparent PNG of reflectivity,
    and returns the bounding box [West, South, East, North].
    """
    try:
        radar = pyart.io.read_nexrad_archive(file_path)
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return None

    # Create a display
    display = pyart.graph.RadarMapDisplay(radar)
    
    # Setup the figure (No axes, transparent background)
    fig = plt.figure(figsize=(6, 6), frameon=False)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)

    # Plot reflectivity
    # VMIN/VMAX controls the color scaling (standard NWS dBZ colors)
    display.plot_ppi_map('reflectivity', 0, vmin=-10, vmax=75,
                         colorbar_flag=False, title_flag=False,
                         resolution='10m', ax=ax, 
                         embellish=False,
                         raster=True) # raster=True helps with transparency

    # Save to PNG
    plt.savefig(output_image_path, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
    plt.close()

    # Get bounds for Pydeck (West, South, East, North)
    # Py-ART calculates these based on the range plotted
    # By default plot_ppi_map plots the full range of the radar
    
    # We need the exact extent of the plotting area to map it correctly
    # Use radar metadata
    lat = radar.latitude['data'][0]
    lon = radar.longitude['data'][0]
    
    # Rough approximation of radar range (usually ~230km or ~460km)
    # A safer way is to grab the limits from the display object if accessible, 
    # but Py-ART is tricky here. 
    # Let's use the explicit lat/lon min/max from the radar gate data.
    
    gate_lat = radar.gate_latitude['data']
    gate_lon = radar.gate_longitude['data']
    
    bounds = [
        float(np.min(gate_lon)), # West
        float(np.min(gate_lat)), # South
        float(np.max(gate_lon)), # East
        float(np.max(gate_lat))  # North
    ]
    
    return bounds