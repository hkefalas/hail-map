import streamlit as st
import pandas as pd
import pydeck as pdk
import os
import json
import time
from dateutil import parser
from datetime import datetime, timedelta
from config import STATES, LAYER_OPTIONS, PROCESSED_DATA_DIR, HAIL_REPORTS_DIR
from utils import setup_logging, load_geojson

# Setup logger
logger = setup_logging()

# --- UI Controls ---
st.title("Hail Risk Dashboard")

# Use keys from the STATES dictionary for the dropdown
state_options = list(STATES.keys())
selected_state = st.selectbox("Choose a state:", state_options, index=0)

# Use keys from LAYER_OPTIONS for the layer selection
selected_layer = st.selectbox("Select layer to visualize:", list(LAYER_OPTIONS.keys()), index=0)

# --- Hail Controls ---
days_to_look_back = st.slider("Hail History (Days):", min_value=1, max_value=7, value=1)

# --- Radar Layer Logic (Sidebar) ---
st.sidebar.markdown("### Radar Overlay")
show_radar = st.sidebar.checkbox("Show Radar Layer", value=False)

radar_layer = None
radar_time_text = ""

if show_radar:
    index_path = "radar_images/radar_index.json"
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            radar_meta = json.load(f)
        
        if radar_meta:
            # 1. Create a Time Slider based on available images
            radar_meta.sort(key=lambda x: x['timestamp'])
            
            # Get min/max times for slider
            min_time = parser.parse(radar_meta[0]['timestamp'])
            max_time = parser.parse(radar_meta[-1]['timestamp'])
            
            # Slider
            selected_time = st.slider(
                "Radar Time",
                min_value=min_time,
                max_value=max_time,
                value=min_time,
                format="HH:mm"
            )
            
            # 2. Find the image closest to selected time
            closest_img = min(radar_meta, key=lambda x: abs(parser.parse(x['timestamp']) - selected_time))
            
            radar_time_text = f"Radar: {closest_img['radar']} @ {parser.parse(closest_img['timestamp']).strftime('%H:%M')}"
            st.caption(radar_time_text)

            # 3. Create BitmapLayer
            radar_layer = pdk.Layer(
                "BitmapLayer",
                data=None, # BitmapLayer doesn't use 'data' list like GeoJsonLayer
                image=closest_img['image_path'],
                bounds=closest_img['bounds'], # [West, South, East, North]
                opacity=0.6,
                desaturate=0,
                transparent_color=[0, 0, 0, 0] 
            )
        else:
            st.warning("Radar index is empty.")
    else:
        st.warning("No generated radar images found. Run 'generate_radar.py' first.")


# ==========================================
# 1. LOAD DATA (Moved UP before Map Rendering)
# ==========================================

# --- Load Hail Data (Multi-Day) ---
hail_dfs = []
today = datetime.today()

for i in range(days_to_look_back):
    target_date = today - timedelta(days=i)
    date_str = target_date.strftime("%Y-%m-%d")
    file_path = os.path.join(HAIL_REPORTS_DIR, f"{date_str}.csv")
    
    if os.path.exists(file_path):
        try:
            daily_df = pd.read_csv(file_path)
            daily_df["Date"] = date_str
            hail_dfs.append(daily_df)
        except Exception as e:
            logger.error(f"Error reading hail data for {date_str}: {e}")

if hail_dfs:
    hail_df = pd.concat(hail_dfs, ignore_index=True)
    hail_df["Size_Inch"] = hail_df["Size"] / 100
    logger.info(f"Loaded {len(hail_df)} hail reports from the last {days_to_look_back} days.")
else:
    hail_df = pd.DataFrame()
    logger.warning(f"No hail reports found for the last {days_to_look_back} days.")

# --- Hail Data Table ---
if not hail_df.empty:
    with st.expander(f"View Raw Hail Reports ({len(hail_df)} records)", expanded=False):
        display_cols = ["Date", "Time", "Location", "State", "Size_Inch", "Comments"]
        cols_to_show = [c for c in display_cols if c in hail_df.columns]
        hail_df = hail_df.sort_values(by=["Date", "Time"], ascending=[False, False])
        st.dataframe(hail_df[cols_to_show], hide_index=True, width="stretch")
else:
    st.info("No hail reports available for the selected date range.")

# --- Load GeoJSON Data ---
geojson_filename = f"gdf_{selected_state}_with_hail_risk.geojson"
geojson_path = os.path.join(PROCESSED_DATA_DIR, geojson_filename)

data = None # Initialize variable
if not os.path.exists(geojson_path):
    st.warning(f"Processed data for {selected_state} not found at {geojson_path}.")
    st.warning("Please run the data pipeline first by executing 'python pipeline/main.py' in your terminal.")
    st.stop()

try:
    gdf = load_geojson(geojson_path, logger)
    data = json.loads(gdf.to_json())
except Exception as e:
    st.error(f"An error occurred while loading the data for {selected_state}: {e}")
    st.stop()


# ==========================================
# 2. DEFINE LAYERS (Now that data is loaded)
# ==========================================
layers_to_render = []

# --- A. Census Tracts Layer (Polygon) ---
if data:
    # Transform Data (Colors)
    field_to_visualize = LAYER_OPTIONS[selected_layer]

    def get_color(value, layer):
        color = [200, 200, 200, 100]
        if pd.isna(value): return color

        if layer == "car_ownership_density":
            intensity = min(1, value / 150)
            red = int(255 * intensity)
            green = int(255 * (1 - intensity))
            color = [red, green, 0, 150]
        elif layer == "population_density":
            intensity = min(1, value / 1000)
            blue = int(100 + 155 * intensity)
            color = [0, 0, blue, 150]
        elif layer in ["median_income", "per_capita_income"]:
            cap = 100000 if layer == "median_income" else 75000
            intensity = min(1, value / cap)
            purple = int(100 + 155 * intensity)
            color = [purple, 0, purple, 150]
        elif layer == "hail_risk_score":
            intensity = min(1, value / 500)
            red = 255
            green = int(255 * (1 - intensity))
            color = [red, green, 0, 160]
        return color

    for feature in data["features"]:
        props = feature["properties"]
        value = props.get(field_to_visualize)
        props["fill_color"] = get_color(value, field_to_visualize)
        
        if value is None:
            formatted_value = "N/A"
        else:
            formatted_value = f"{value:,.2f}"
        props["tooltip_text"] = f"{selected_layer}: {formatted_value}"

    polygon_layer = pdk.Layer(
        "GeoJsonLayer",
        data=data,
        get_fill_color="properties.fill_color",
        pickable=True,
        auto_highlight=True,
        stroked=True,
        get_line_color=[0, 0, 0, 50],
        line_width_min_pixels=1,
    )
    layers_to_render.append(polygon_layer)

# --- B. Hail Layer (Scatterplot) ---
if not hail_df.empty:
    hail_layer = pdk.Layer(
        "ScatterplotLayer",
        data=hail_df,
        get_position=['Lon', 'Lat'],
        get_color=[255, 0, 0, 200],
        get_radius="Size * 25",
        pickable=True,
        opacity=0.8,
        stroked=True,
        filled=True,
        radius_min_pixels=3,
        radius_max_pixels=30,
        get_line_color=[0, 0, 0, 200]
    )
    layers_to_render.append(hail_layer)

# --- C. Radar Layer (Bitmap) ---
if radar_layer:
    layers_to_render.append(radar_layer)

# ... (Keep all your data loading and Polygon/Hail layer definitions exactly as they are) ...

# ==========================================
# 3. RADAR & ANIMATION LOGIC
# ==========================================
radar_layer = None
radar_meta = []

# Load Radar Metadata if checked
if show_radar:
    index_path = "radar_images/radar_index.json"
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            radar_meta = json.load(f)
            # Ensure sorted by time
            radar_meta.sort(key=lambda x: x['timestamp'])

# --- Sidebar Controls ---
if show_radar and radar_meta:
    # 1. Slider for Static View
    min_time = parser.parse(radar_meta[0]['timestamp'])
    max_time = parser.parse(radar_meta[-1]['timestamp'])
    
    selected_time = st.sidebar.slider(
        "Radar Time",
        min_value=min_time,
        max_value=max_time,
        value=min_time,
        format="MM/DD HH:mm"
    )

    # 2. Play Button
    start_animation = st.sidebar.button("▶️ Play Animation")
    
    # Logic for Static Layer (linked to slider)
    if not start_animation:
        # Find closest image to slider
        closest_img = min(radar_meta, key=lambda x: abs(parser.parse(x['timestamp']) - selected_time))
        st.sidebar.caption(f"Showing: {closest_img['radar']} @ {parser.parse(closest_img['timestamp']).strftime('%H:%M')}")
        
        radar_layer = pdk.Layer(
            "BitmapLayer",
            image=closest_img['image_path'],
            bounds=closest_img['bounds'],
            opacity=0.6,
            desaturate=0,
            transparent_color=[0, 0, 0, 0]
        )
        layers_to_render.append(radar_layer)
elif show_radar:
    st.sidebar.warning("No radar index found. Run 'generate_radar.py'.")

# ==========================================
# 4. RENDER MAP
# ==========================================
lat, lon = STATES[selected_state]["center"]
view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=6, pitch=30)

# Create a placeholder. This allows us to overwrite the map during animation.
map_placeholder = st.empty()

# --- Animation Loop ---
if show_radar and 'start_animation' in locals() and start_animation:
    # We loop through EVERY frame in the metadata
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    for i, frame in enumerate(radar_meta):
        # Update Status
        frame_time = parser.parse(frame['timestamp'])
        status_text.text(f"Playing: {frame_time.strftime('%H:%M')}")
        progress_bar.progress((i + 1) / len(radar_meta))
        
        # 1. Create Dynamic Radar Layer for this frame
        anim_radar_layer = pdk.Layer(
            "BitmapLayer",
            image=frame['image_path'],
            bounds=frame['bounds'],
            opacity=0.6,
            desaturate=0,
            transparent_color=[0, 0, 0, 0]
        )
        
        # 2. Combine with Base Layers (Polygon/Hail)
        # Note: We must exclude any static radar layer if it exists
        current_layers = [l for l in layers_to_render if not isinstance(l, pdk.Layer) or l.type != "BitmapLayer"]
        current_layers.append(anim_radar_layer)
        
        # 3. Build Deck
        r = pdk.Deck(
            layers=current_layers,
            initial_view_state=view_state,
            tooltip={"html": "{tooltip_text}"} # Simplified tooltip during animation for performance
        )
        
        # 4. Update the Placeholder
        map_placeholder.pydeck_chart(r, width='stretch')
        
        # 5. Control Speed (0.2s = 5 frames per second)
        time.sleep(0.2)
    
    status_text.text("Finished!")
    # Optional: Rerun to snap back to slider state
    # st.rerun() 

# --- Static Render (Default) ---
else:
    r = pdk.Deck(
        layers=layers_to_render,
        initial_view_state=view_state,
        tooltip={
            "html": """
                <div style="font-family: sans-serif; font-size: 12px; color: white;">
                    <b>{Location}</b><br>
                    Date: {Date}<br>  Time: {Time}<br>
                    Size: {Size_Inch} in.<br>
                    <i>{Comments}</i>
                    
                    {tooltip_text}
                </div>
            """,
            "style": {"backgroundColor": "#333", "color": "white"}
        }
    )
    map_placeholder.pydeck_chart(r, width='stretch')