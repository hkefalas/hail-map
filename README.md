# Hail Risk Dashboard

A comprehensive data visualization tool that assesses hail risk across select US states (Missouri, Kansas, Iowa, Nebraska). This project combines US Census data, vehicle ownership statistics, and NOAA hail reports to calculate a **Hail Risk Score** for each Census tract. It also features an interactive dashboard with real-time NEXRAD radar imagery overlays.

## Features

- **Hail Risk Assessment**: Calculates a risk score based on hail frequency and car ownership density per Census tract.
- **Interactive Dashboard**: Built with Streamlit and PyDeck for high-performance geospatial visualizations.
- **Layered Visualizations**:
  - **Census Tracts**: Color-coded by Population Density, Car Ownership, Income, or Hail Risk.
  - **Hail Reports**: Scatterplot of daily hail events with size and location data.
  - **Radar Overlay**: Transparent NEXRAD radar reflectivity overlays for historical hail events.
- **Data Pipeline**: Automated pipeline to download, clean, merge, and process multi-source data.
- **Radar Integration**: Fetches Level 2 NEXRAD data from AWS S3, generates imagery using Py-ART, and creates animations.

## Repository Structure

```
├── census_data/         # Contains shapefiles and CSVs for Census/Vehicle/Income data
├── hail_reports/        # Downloaded daily hail reports (CSV)
├── processed_data/      # Output directory for processed GeoJSON files
├── radar_images/        # Generated radar plots and metadata index
├── station_list/        # Metadata for NEXRAD radar sites
├── config.py            # Configuration for paths, states, and layers
├── download_hail_report.py # Script to fetch NOAA hail data
├── generate_radar.py    # Script to generate radar images from NEXRAD data
├── load_data.py         # Helper functions to load raw data
├── main_data.py         # Main orchestration script for the data pipeline
├── process_data.py      # Logic for merging data and calculating risk scores
├── radar_utils.py       # Utilities for AWS S3 download and Py-ART plotting
├── streamlit_app.py     # The main Streamlit dashboard application
├── utils.py             # General utility functions (logging, file I/O)
└── requirements.txt     # Python dependencies
```

## Prerequisites

- Python 3.8+
- Internet connection (for fetching NOAA reports and AWS radar data)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    pip install -r requirements.txt
    ```

    *Note: This project relies on `arm_pyart`, `xradar`, and `cartopy`, which may have system-level dependencies (like PROJ, GEOS). If pip installation fails, consider using Conda.*

## Usage

To fully utilize the dashboard, you need to run the data pipeline and (optionally) the radar generator before launching the app.

### 1. Run the Data Pipeline
This step downloads the latest hail reports, loads census/vehicle data, calculates risk scores, and saves the results as GeoJSON files in `processed_data/`.

```bash
python main_data.py
```

### 2. Generate Radar Imagery (Optional)
To enable the radar overlay feature, run this script. It identifies hail events, downloads relevant NEXRAD scans from AWS, and generates visualization plots.

```bash
python generate_radar.py
```
*Note: This process can take time depending on the number of hail events and internet speed.*

### 3. Launch the Dashboard
Start the Streamlit application to explore the data.

```bash
streamlit run streamlit_app.py
```

## Configuration

The `config.py` file allows you to customize various aspects of the project:
- **STATES**: Add or remove states (requires corresponding shapefiles and CSVs in `census_data/`).
- **LAYER_OPTIONS**: Define which data fields are available for visualization.
- **Paths & URLs**: Update data sources or directory structures.

## Data Sources

- **Hail Reports**: [NOAA Storm Prediction Center](https://www.spc.noaa.gov/climo/reports/)
- **Radar Data**: [NOAA NEXRAD Level 2 Data on AWS S3](https://registry.opendata.aws/noaa-nexrad/)
- **Census Data**: US Census Bureau (TIGER/Line Shapefiles, American Community Survey)

## License

[MIT License](LICENSE) (Assuming standard open-source terms, please verify)
