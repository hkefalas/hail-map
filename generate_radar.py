import glob
import os
import json
import pandas as pd
from datetime import datetime
from radar_utils import get_closest_nexrad, download_scans_window, generate_radar_image

# Settings
HAIL_REPORTS_DIR = "hail_reports" 
CACHE_DIR = "radar_images"
INDEX_PATH = os.path.join(CACHE_DIR, "radar_index.json")
os.makedirs(os.path.join(CACHE_DIR, "plots"), exist_ok=True)

def main():
    existing_metadata = []
    processed_keys = set() 

    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r") as f:
            existing_metadata = json.load(f)
            processed_keys = {(m['radar'], m['timestamp']) for m in existing_metadata}
    
    report_files = glob.glob(os.path.join(HAIL_REPORTS_DIR, "*.csv"))
    metadata_list = existing_metadata 

    for report_path in report_files:
        print(f"--- Processing: {os.path.basename(report_path)} ---")
        df = pd.read_csv(report_path)
        unique_events = df.drop_duplicates(subset=['Lat', 'Lon']).head(5) 

        for idx, row in unique_events.iterrows():
            try:
                event_date_str = os.path.basename(report_path).replace(".csv", "")
                time_str = str(row['Time']).zfill(4) 
                event_dt = datetime.strptime(f"{event_date_str} {time_str}", "%Y-%m-%d %H%M")
            except: continue

            radar_id = get_closest_nexrad(row['Lat'], row['Lon'])
            raw_output = f"{CACHE_DIR}/raw/{event_date_str}"
            files = download_scans_window(radar_id, event_dt, window_hours=2, output_dir=raw_output)
            
            for raw_file in files:
                fname = os.path.basename(raw_file)
                ts_part = fname.split('_')[1]
                ts_iso = datetime.strptime(f"{event_date_str} {ts_part}", "%Y-%m-%d %H%M%S").isoformat()

                if (radar_id, ts_iso) in processed_keys:
                    if os.path.exists(raw_file): os.remove(raw_file)
                    continue 

                img_path = os.path.join(CACHE_DIR, "plots", f"{fname}.png")
                bounds = generate_radar_image(raw_file, img_path)

                if bounds:
                    metadata_list.append({
                        "image_path": img_path,
                        "bounds": bounds,
                        "timestamp": ts_iso,
                        "radar": radar_id
                    })
                    processed_keys.add((radar_id, ts_iso))

                if os.path.exists(raw_file):
                    os.remove(raw_file) # Clean up raw data to save local space

    with open(INDEX_PATH, "w") as f:
        json.dump(metadata_list, f, indent=2)
    print("Static assets ready for GitHub.")

if __name__ == "__main__":
    main()